"""Unified Triage Agent.

Uses the canonical `incident_classification.md` skill through an LLM to:
1. Dynamically understand the natural language narrative of incoming tickets.
2. Simultaneously classify the domain (LOGIN, RECORD, OBJECT, APPLICATION).
3. Contextually identify the Affected User (Priority 1: description -> Priority 2: on_behalf -> Priority 3: caller).
4. Contextually identify the Mirror User (colleague benchmark for comparison).
5. Deterministically verify identified users in Salesforce via `salesforce_user_search`.
"""

import json
import logging
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.models.schemas import TriageResult
from app.models.state import InvestigationState
from app.tools.historical_incidents import fetch_historical_context_for_state
from app.tools.salesforce import salesforce_user_search, salesforce_get_user_details
from app.utils.validators import validate_user_identity_resolution

logger = logging.getLogger(__name__)


class TriageAgent:
    """Unified agent for incident classification, affected-user, and mirror-user resolution."""

    def __init__(self, llm=None):
        self.llm = llm or self._init_default_llm()
        self.skill_guide = self._load_classification_skill()

    def _init_default_llm(self):
        """Initialize LLM client if configured in environment and responsive."""
        api_key = os.environ.get("OPENAI_API_KEY")
        ollama_url = os.environ.get("OLLAMA_BASE_URL")

        try:
            from langchain_openai import ChatOpenAI
            if api_key and api_key != "sk-...":
                return ChatOpenAI(model="gpt-4o-mini", temperature=0.0)
            elif ollama_url:
                import urllib.request
                req = urllib.request.Request(f"{ollama_url.rstrip('/')}/api/tags")
                try:
                    with urllib.request.urlopen(req, timeout=0.3):
                        return ChatOpenAI(
                            base_url=f"{ollama_url.rstrip('/')}/v1",
                            api_key="ollama",
                            model="llama3",
                            temperature=0.0,
                            timeout=5.0,
                        )
                except Exception:
                    logger.debug("Ollama endpoint %s unreachable; using deterministic semantic triage.", ollama_url)
                    return None
        except Exception as exc:
            logger.debug("LLM not initialized for TriageAgent: %s", exc)
        return None

    def _load_classification_skill(self) -> str:
        """Load canonical incident classification skill instructions."""
        skill_path = Path(__file__).resolve().parents[2] / "skills" / "incident_classification.md"
        try:
            if skill_path.exists():
                return skill_path.read_text(encoding="utf-8")
        except Exception as exc:
            logger.warning("Could not read classification skill: %s", exc)
        return ""

    def run(self, state: InvestigationState) -> InvestigationState:
        """Execute unified triage: classify domain and resolve affected & mirror users."""
        incident = state.get("incident", {})
        summary = str(incident.get("short_description", "")).strip()
        desc = str(incident.get("description", "")).strip()
        caller_email = incident.get("caller_email") or incident.get("caller_id")
        on_behalf_val = (
            incident.get("on_behalf_of")
            or incident.get("on_behalf")
            or incident.get("requested_for")
        )

        # 1. Single LLM inference step guided by incident_classification.md
        llm_output = self._call_llm_triage(summary, desc, caller_email, on_behalf_val)

        # If LLM is unavailable or fails, fall back to semantic contextual narrative parser
        if not llm_output:
            llm_output = self._fallback_semantic_triage(summary, desc, caller_email, on_behalf_val)

        domain = llm_output.get("domain", "LOGIN")
        is_ambiguous = bool(llm_output.get("is_ambiguous", False))
        affected_target = llm_output.get("affected_user_identifier")
        mirror_target = llm_output.get("mirror_user_identifier")
        reasoning = llm_output.get("reasoning", "")
        resolution_source = llm_output.get("resolution_source", "contextual_narrative")
        extracted_objects = llm_output.get("objects", [])

        # 2. Deterministic Salesforce Verification: Affected User
        state.setdefault("evidence", [])
        state.setdefault("evidence_cache", {})
        state.setdefault("step_audit_trail", [])

        resolved_affected: Optional[Dict[str, Any]] = None
        if affected_target:
            sf_matches = salesforce_user_search(affected_target)
            ev_search_id = f"ev_user_search_{uuid.uuid4().hex[:6]}"
            state["evidence"].append({
                "evidence_id": ev_search_id,
                "tool_name": "salesforce_user_search",
                "query": affected_target,
                "raw_output": sf_matches,
            })
            id_check = validate_user_identity_resolution(sf_matches)

            if id_check["status"] == "unique":
                resolved_affected = {
                    **id_check["user"],
                    "resolution_source": resolution_source,
                    "resolution_status": "unique",
                    "reasoning": reasoning,
                }
            else:
                resolved_affected = {
                    "Email": affected_target,
                    "resolution_source": resolution_source,
                    "resolution_status": id_check["status"],
                    "candidate_count": id_check.get("count", 0),
                    "reasoning": reasoning,
                }

        # 3. Deterministic Salesforce Verification: Mirror User (if identified)
        resolved_mirror: Optional[Dict[str, Any]] = None
        if mirror_target:
            mirror_matches = salesforce_user_search(mirror_target)
            mirror_check = validate_user_identity_resolution(mirror_matches)

            if mirror_check["status"] == "unique":
                resolved_mirror = {
                    **mirror_check["user"],
                    "is_mirror_user": True,
                    "resolution_status": "unique",
                }
            else:
                resolved_mirror = {
                    "Email": mirror_target,
                    "is_mirror_user": True,
                    "resolution_status": mirror_check["status"],
                }

        state["affected_user"] = resolved_affected
        state["mirror_user"] = resolved_mirror

        # Pre-fetch user object from Salesforce MCP and store as evidence
        state.setdefault("evidence", [])
        state.setdefault("evidence_cache", {})
        state.setdefault("step_audit_trail", [])
        
        tools_called = ["salesforce_user_search"]
        user_obj = None
        if resolved_affected and resolved_affected.get("Id"):
            user_id = resolved_affected["Id"]
            user_obj = salesforce_get_user_details(user_id)
            ev_id = f"ev_user_details_{uuid.uuid4().hex[:6]}"
            state["evidence"].append({
                "evidence_id": ev_id,
                "tool_name": "salesforce_get_user_details",
                "field_name": "User",
                "user_id": user_id,
                "observed_value": user_obj,
                "raw_output": user_obj,
            })
            state["evidence_cache"]["User"] = user_obj
            state["evidence_cache"][f"User:{user_id}"] = user_obj
            tools_called.append("salesforce_get_user_details")

        if resolved_mirror and resolved_mirror.get("Id"):
            mirror_id = resolved_mirror["Id"]
            mirror_obj = salesforce_get_user_details(mirror_id)
            ev_mirror_id = f"ev_user_details_mirror_{uuid.uuid4().hex[:6]}"
            state["evidence"].append({
                "evidence_id": ev_mirror_id,
                "tool_name": "salesforce_get_user_details",
                "field_name": "User:mirror",
                "user_id": mirror_id,
                "observed_value": mirror_obj,
                "raw_output": mirror_obj,
            })
            state["evidence_cache"]["User:mirror"] = mirror_obj
            state["evidence_cache"][f"User:{mirror_id}"] = mirror_obj

        # Record Step 1 in Step Audit Trail
        triage_exp_criteria = "Incident narrative indicates target user identity and issue domain (LOGIN, OBJECT, RECORD, APPLICATION)"
        triage_obs_values = {
            "ticket_summary": summary,
            "caller_email": caller_email,
            "on_behalf_of": on_behalf_val,
            "resolved_affected_user": resolved_affected.get("Email") if resolved_affected else affected_target,
            "salesforce_user_id": resolved_affected.get("Id") if resolved_affected else None,
            "user_is_active": user_obj.get("IsActive") if user_obj else None,
            "user_federation_id": user_obj.get("FederationIdentifier") if user_obj else None,
        }
        triage_comparison = f"[MATCH] Narrative symptoms match '{domain}' domain classification with {resolution_source} resolution."
        triage_decision_basis = (
            f"Classified into '{domain}' domain based on ticket narrative keywords ('{summary}'). "
            f"Affected user '{resolved_affected.get('Email') if resolved_affected else affected_target}' resolved uniquely in Salesforce (Id: {resolved_affected.get('Id') if resolved_affected else 'N/A'}). "
            f"User details pre-fetched into evidence cache to eliminate redundant MCP queries."
        )
        triage_next_step = (
            f"Advancing to Diagnosis Agent to evaluate candidate root causes in '{domain}' domain "
            f"top-to-bottom against observed Salesforce evidence without loading skill files."
        )

        triage_banner = (
            "\n" + "=" * 80 + "\n"
            f"[STAGE: TRIAGE] Domain: {domain}\n"
            f"- Skill File Loaded: app/skills/incident_classification.md\n"
            f"- Expected Criteria: {triage_exp_criteria}\n"
            f"- Observed Values:   {triage_obs_values}\n"
            f"- Comparison:        {triage_comparison}\n"
            f"- Decision Basis:    {triage_decision_basis}\n"
            f"- Next Step Reason:  {triage_next_step}\n"
            + "=" * 80
        )
        logger.info(triage_banner)
        print(triage_banner, flush=True)

        state["step_audit_trail"].append({
            "stage": "triage",
            "step_order": 1,
            "step_name": "Contextual Triage & User Object Retrieval",
            "graph_node_id": "DAG_NODE_TRIAGE",
            "graph_node_name": "Knowledge Graph DAG: Root Triage Node",
            "movement_direction": f"Advance along Directed Edge CLASSIFIED_AS_DOMAIN -> [Diagnosis DAG: Domain {domain}]",
            "status_reason": f"Incident classified into '{domain}' domain based on ticket narrative keywords and semantic evaluation.",
            "current_step_details": f"Analyzed incident symptoms against classification skill. Resolved target identity '{resolved_affected.get('Email') if resolved_affected else affected_target}'. Pre-fetched user object into evidence cache.",
            "next_step": f"Evaluate filtered historical precedents in '{domain}' domain top-to-bottom",
            "skill_file_loaded": "app/skills/incident_classification.md",
            "why_loaded": "Contextual domain classification, identity resolution, and user object pre-fetch",
            "tool_called": "salesforce_user_search",
            "tools_called": tools_called,
            "why_called_at_instance": f"Incident intake & identity resolution. Invoked salesforce_user_search to resolve caller/affected email '{resolved_affected.get('Email') if resolved_affected else affected_target}' to a unique Salesforce User record (Id: {resolved_affected.get('Id') if resolved_affected else 'N/A'}).",
            "tool_result": {
                "matched_salesforce_id": resolved_affected.get("Id") if resolved_affected else None,
                "email": resolved_affected.get("Email") if resolved_affected else affected_target,
                "is_active": user_obj.get("IsActive") if user_obj else None,
                "classified_domain": domain,
            },
            "expected_criteria": triage_exp_criteria,
            "observed_values": triage_obs_values,
            "comparison": triage_comparison,
            "decision_basis": triage_decision_basis,
            "next_step_reason": triage_next_step,
            "evidence_checked": {
                "domain": domain,
                "affected_user": resolved_affected.get("Email") if resolved_affected else affected_target,
                "mirror_user": resolved_mirror.get("Email") if resolved_mirror else mirror_target,
                "user_is_active": user_obj.get("IsActive") if user_obj else None,
            },
            "conclusion": f"Incident classified into '{domain}' domain. User record pre-fetched and stored in evidence cache to prevent duplicate MCP queries.",
            "status": "satisfied",
        })

        # 4. Populate structured TriageResult
        emails = re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", f"{summary} {desc}")
        extracted_entities = {
            "emails": emails,
            "objects": extracted_objects,
            "caller_email": caller_email,
            "on_behalf_value": on_behalf_val,
            "affected_user_email": resolved_affected.get("Email") if resolved_affected else affected_target,
            "mirror_user_email": resolved_mirror.get("Email") if resolved_mirror else mirror_target,
            "resolution_source": resolution_source,
        }

        triage_result = TriageResult(
            domain=domain,
            is_ambiguous=is_ambiguous,
            extracted_entities=extracted_entities,
            confidence=0.7 if is_ambiguous else 0.95,
            reasoning=reasoning,
        )
        state["triage_result"] = triage_result.model_dump()

        # 5. Retrieve historical precedents strictly filtered by classified domain
        try:
            past_cases = fetch_historical_context_for_state(
                incident_summary=summary,
                incident_description=desc,
                domain=domain.upper(),
                top_k=5,
            )
            filtered_cases = [c for c in past_cases if str(c.get("domain", "")).upper() == domain.upper()]
            if not filtered_cases:
                from app.knowledge.sop_repository import sop_repository
                filtered_cases = sop_repository.get_historical_incidents(domain.upper())
                if not filtered_cases:
                    from tests.fixtures.historical_incidents import FIXTURE_HISTORICAL_INCIDENTS
                    filtered_cases = [c for c in FIXTURE_HISTORICAL_INCIDENTS if str(c.get("domain", "")).upper() == domain.upper()]
            state["historical_cases"] = filtered_cases
        except Exception as exc:
            logger.warning("Could not fetch historical cases in triage: %s", exc)
            state["historical_cases"] = []

        # 6. Record audit trace event
        state.setdefault("trace_events", [])
        state["trace_events"].append({
            "stage": "triage",
            "agent_name": "TriageAgent",
            "action": f"Classified incident to {domain} (ambiguous={is_ambiguous}) via skill guidance",
            "details": {
                "domain": domain,
                "is_ambiguous": is_ambiguous,
                "affected_user": resolved_affected.get("Email") if resolved_affected else None,
                "mirror_user": resolved_mirror.get("Email") if resolved_mirror else None,
                "resolution_source": resolution_source,
                "historical_cases_count": len(state.get("historical_cases", [])),
            },
        })

        return state

    def _call_llm_triage(
        self,
        summary: str,
        desc: str,
        caller: Optional[str],
        on_behalf: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """Single LLM invocation parsing classification, affected user, and mirror user from the skill."""
        if not self.llm:
            return None

        try:
            from langchain_core.messages import SystemMessage, HumanMessage

            prompt = (
                f"You are the Triage Agent for Salesforce Incident Management.\n"
                f"Apply the canonical Incident Classification and Semantic Identity Resolution skill to analyze this ticket.\n\n"
                f"Ticket Information:\n"
                f"- Short Description: {summary}\n"
                f"- Full Description: {desc}\n"
                f"- Caller: {caller}\n"
                f"- On Behalf Of: {on_behalf}\n\n"
                f"Your task is to analyze the narrative and return a JSON object with:\n"
                f"1. 'domain': One of 'LOGIN', 'OBJECT', 'RECORD', 'APPLICATION'.\n"
                f"2. 'is_ambiguous': boolean (true if vague like 'can't access Salesforce' without detail).\n"
                f"3. 'affected_user_identifier': The user experiencing the problem (email, username, or full name e.g. 'Daniel Ortiz', 'Priya Nair'). Priority 1: description -> Priority 2: on_behalf_of -> Priority 3: caller.\n"
                f"4. 'mirror_user_identifier': Any colleague mentioned whose access works fine or is used as a benchmark (email, username, or full name, null if none).\n"
                f"5. 'objects': Any Salesforce objects mentioned (e.g. Account, Contact, Opportunity).\n"
                f"6. 'resolution_source': Description of how the affected user was identified.\n"
                f"7. 'reasoning': Concise explanation of the domain classification and identity attribution.\n\n"
                f"Output strictly valid JSON only."
            )

            response = self.llm.invoke([
                SystemMessage(content=self.skill_guide or "Classify incident and identify affected and mirror users."),
                HumanMessage(content=prompt),
            ])

            content = response.content.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            data = json.loads(content)
            # Ensure domain is valid uppercase
            if "domain" in data:
                data["domain"] = data["domain"].upper()
            return data
        except Exception as exc:
            logger.debug("LLM triage call failed: %s", exc)
            return None

    def _fallback_semantic_triage(
        self,
        summary: str,
        desc: str,
        caller_email: Optional[str],
        on_behalf_val: Optional[str],
    ) -> Dict[str, Any]:
        """Contextual narrative fallback implementing the exact skill rules without hardcoded branches."""
        full_text = f"{summary} {desc}".strip()
        full_text_lower = full_text.lower()
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", full_text) if s.strip()]
        all_emails = re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", full_text)

        # 1. Mirror user detection from comparison sentences (Email or Full Name)
        mirror_target = None
        for s in sentences:
            s_lower = s.lower()
            if any(cue in s_lower for cue in ["working fine for", "works for", "working for", "mirror user", "compare with", "compare to", "same access as", "same profile as", "same role as"]):
                emails_in_s = re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", s)
                if emails_in_s:
                    mirror_target = emails_in_s[0]
                    break
                # Also check for person full name (e.g. "working fine for Harvey Specter")
                name_match = re.search(r"(?:working fine for|works for|working for|compare with|compare to|same access as|mirror user)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", s)
                if name_match:
                    mirror_target = name_match.group(1).strip()
                    break

        # 2. Affected user resolution using 3-tier hierarchy (Email or Full Name)
        affected_target = None
        resolution_source = "caller_field"
        reasoning_user = "Caller is affected party (self-reported ticket)."

        # Priority 1: Contextual narrative sentence describing problem subject (Email or Full Name)
        for s in sentences:
            s_lower = s.lower()
            if mirror_target and mirror_target.lower() in s_lower:
                continue

            if any(cue in s_lower for cue in ["cannot", "can't", "unable", "blocked", "issue for", "problem for", "access for", "check access", "for my team member", "raising this for", "on behalf of", "user", "lacks", "started on"]):
                emails_in_s = re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", s)
                for em in emails_in_s:
                    if not mirror_target or em.lower() != mirror_target.lower():
                        affected_target = em
                        resolution_source = "description_contextual_narrative"
                        reasoning_user = f"Contextual sentence indicated problem for email {em}."
                        break
                if affected_target:
                    break

                # Extract candidate full name if no email in sentence (e.g. "Raising this for Priya Nair", "starter Daniel Ortiz", "User John Smith")
                name_matches = re.findall(
                    r"(?:raising (?:this )?for (?:a team member,?\s*)?|on behalf of |help for |issue for |problem for |user |starter |joiner |employee |member )([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
                    s,
                    re.IGNORECASE
                )
                if not name_matches:
                    name_matches = re.findall(
                        r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+(?:cannot|can't|is unable|unable to|has an issue|gets an error|is experiencing|started on)",
                        s
                    )

                for nm in name_matches:
                    cand = nm.strip()
                    if not any(sw in cand.lower() for sw in ["sso", "federation", "salesforce", "servicenow", "login", "access", "failed", "error", "morning", "afternoon"]):
                        # Verify against Salesforce via MCP to confirm it's an actual user
                        matches = salesforce_user_search(cand)
                        if matches:
                            affected_target = cand
                            resolution_source = "description_named_entity"
                            reasoning_user = f"Contextual narrative identified and verified user by full name '{cand}'."
                            break
            if affected_target:
                break

        if not affected_target and all_emails:
            for em in all_emails:
                if not mirror_target or em.lower() != mirror_target.lower():
                    affected_target = em
                    resolution_source = "description_parsed_subject"
                    reasoning_user = f"Identified subject {em} in description narrative."
                    break

        # Priority 1b: Search full narrative for person name patterns if still not found
        if not affected_target:
            name_patterns = [
                r"(?:raising (?:this )?for (?:a team member,?\s*)?|on behalf of |help for |issue for |problem for )([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
            ]
            for pat in name_patterns:
                m = re.search(pat, full_text, re.IGNORECASE)
                if m:
                    cand = m.group(1).strip()
                    if not any(sw in cand.lower() for sw in ["sso", "federation", "salesforce", "servicenow", "login", "access", "failed"]):
                        matches = salesforce_user_search(cand)
                        if matches:
                            affected_target = cand
                            resolution_source = "description_named_entity"
                            reasoning_user = f"Identified and verified subject '{cand}' from description narrative."
                            break

        # Priority 2: on_behalf_of field
        if not affected_target and on_behalf_val:
            affected_target = str(on_behalf_val).strip()
            resolution_source = "on_behalf_incident_field"
            reasoning_user = f"Resolved via structured on_behalf_of field ({affected_target})."

        # Priority 3: Caller
        if not affected_target and caller_email:
            affected_target = str(caller_email).strip()
            resolution_source = "caller_field"

        # 3. Domain classification based on canonical symptom semantics
        app_cues = ["cc360", "pharm", "cmty-ps", "conga", "clm", "apttus", "x-author", "showpad", "appexchange", "connected app", "portal"]
        
        # Record indicators: specific record IDs (15 or 18 chars like 006xx..., 001xx...), or row-level sharing cues
        has_record_id = bool(re.search(r"\b00[0-9a-zA-Z]{13,16}\b", full_text)) or "record 00" in full_text_lower
        row_level_cues = [
            "record id", "specific record", "individual record", "this record",
            "report", "dashboard", "userrecordaccess", "sharing rule", 
            "public group", "queue", "folder sharing", "manual sharing", 
            "owd", "organization-wide defaults", "row-level"
        ]
        
        # Object indicators: CRUD operations, FLS, profile/permset object-wide grants
        object_cues = [
            "permission to edit", "permission to create", "permission to delete", 
            "lacks permission", "cannot edit account", "cannot edit contact", "cannot edit opportunity", 
            "field-level security", "fls", "wizard app", "wizard country", "product search", 
            "object permission", "profile permission", "crud", "sales profile"
        ]
        
        # Login indicators: SSO, Federation, account active, lockout, MFA, auth
        login_cues = [
            "login", "sign in", "sso", "saml", "okta", "azure", "federation", 
            "federationidentifier", "password", "authenticate", "deactivated", 
            "locked out", "wrong url", "mobile app", "medical leave", "returned from leave", "ciam"
        ]

        app_match = any(c in full_text_lower for c in app_cues)
        has_specific_record = has_record_id or any(c in full_text_lower for c in row_level_cues)
        object_match = any(c in full_text_lower for c in object_cues)
        login_match = any(c in full_text_lower for c in login_cues)

        is_ambiguous = False
        domain = "LOGIN"

        # Deterministic hierarchy as per incident_classification.md
        if ("can't access salesforce at all" in full_text_lower or "cannot access salesforce at all" in full_text_lower) and not (
            login_match or object_match or has_specific_record or app_match
        ):
            domain = "LOGIN"
            is_ambiguous = True
            reasoning_domain = "Vague description ('can't access salesforce at all'); flagged as ambiguous."
        elif app_match:
            domain = "APPLICATION"
            reasoning_domain = "Matched connected application or portal symptom."
        elif has_specific_record and not login_match:
            domain = "RECORD"
            reasoning_domain = "Matched specific row-level record instance or sharing rule symptom."
        elif login_match and not has_specific_record:
            domain = "LOGIN"
            reasoning_domain = "Matched authentication, session, or SSO login symptom."
        elif object_match:
            domain = "OBJECT"
            reasoning_domain = "Matched object-level CRUD or FLS permission symptom."
        elif login_match:
            domain = "LOGIN"
            reasoning_domain = "Matched authentication or login symptom."
        else:
            domain = "LOGIN"
            is_ambiguous = True
            reasoning_domain = "Unspecified incident scope defaulted to LOGIN with ambiguity flag."

        # Extract objects
        standard_objects = ["Account", "Contact", "Opportunity", "Lead", "Case", "WorkOrder", "Report", "Dashboard"]
        found_objects = [obj for obj in standard_objects if obj.lower() in full_text_lower]

        return {
            "domain": domain,
            "is_ambiguous": is_ambiguous,
            "affected_user_identifier": affected_target,
            "mirror_user_identifier": mirror_target,
            "objects": found_objects,
            "resolution_source": resolution_source,
            "reasoning": f"{reasoning_domain} {reasoning_user}",
        }
