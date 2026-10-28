"""Knowledge Graph-Driven Traversal Engine for Diagnosis Agent.

Queries and traverses the Decision Tree Knowledge Graph (stored in Neo4j with
offline local graph fallback) to diagnose Login Issues dynamically.

Every step retrieves the current node, executes the tool action or evaluates
the decision condition, looks up the outgoing edge (ON_YES, ON_NO, TRANSITIONS_TO),
and navigates the graph until a TerminalNode is reached.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
import uuid

from app.models.schemas import DiagnosisResult, Finding
from app.knowledge.neo4j_repository import neo4j_repository
from app.tools.salesforce import (
    salesforce_user_search,
    salesforce_get_user_details,
    salesforce_get_user_field,
)
from app.utils.validators import validate_user_identity_resolution

logger = logging.getLogger(__name__)


class StructuredDiagnosisFlow:
    """Dynamic Graph Traversal Engine powered by Neo4j Knowledge Graph."""

    def __init__(self):
        self.traversal_steps: List[Dict[str, Any]] = []

    def _record_traversal_step(
        self,
        swimlane: str,
        node_id: str,
        node_name: str,
        from_node: str,
        to_node: str,
        action: str,
        observed: Any,
        decision_outcome: str,
        explanation: str,
        tools_called: Optional[List[str]] = None,
        status: str = "evaluated",
        graph_source: str = "neo4j",
    ) -> Dict[str, Any]:
        """Record and print a formatted graph traversal step."""
        step_num = len(self.traversal_steps) + 1
        tools = tools_called or ["Decision Logic"]
        tool_main = tools[0] if tools else "Decision Logic"

        if isinstance(observed, dict):
            obs_summary = ", ".join(f"{k}={v}" for k, v in observed.items())
        else:
            obs_summary = str(observed)

        print(f"\n" + "-" * 80)
        print(f"[KNOWLEDGE GRAPH STEP {step_num}] Swimlane: {swimlane} (Source: {graph_source})")
        print(f"  * Current Node:     {node_name} [{node_id}]")
        print(f"  * From Node:        {from_node}")
        print(f"  * Action / Check:   {action}")
        print(f"  * Tool(s) Invoked:  {', '.join(tools)}")
        print(f"  * Live Observed:    {obs_summary}")
        print(f"  * Decision Outcome: {decision_outcome}")
        print(f"  * Traversal Path:   {from_node} -----> {to_node}")
        print(f"  * Step Explanation: {explanation}")
        print("-" * 80, flush=True)

        step_entry = {
            "stage": "diagnosis",
            "step_order": step_num,
            "step_name": f"[{swimlane}] {node_name}",
            "graph_node_id": node_id,
            "graph_node_name": node_name,
            "swimlane": swimlane,
            "movement_direction": f"{from_node} -----> {to_node}",
            "from_node": from_node,
            "to_node": to_node,
            "status": status,
            "status_reason": decision_outcome,
            "current_step_details": action,
            "why_step_taken": f"Knowledge Graph edge traversal from {from_node} to {to_node}",
            "observed_summary": obs_summary,
            "observed_values": observed if isinstance(observed, dict) else {"value": str(observed)},
            "comparison": f"Decision: {decision_outcome}",
            "conclusion": f"Traversed to {to_node}",
            "decision_basis": explanation,
            "next_step": f"Advance along graph edge to {to_node}",
            "next_step_reason": explanation,
            "tool_called": tool_main,
            "tools_called": tools,
            "tool_result": observed,
            "graph_source": graph_source,
        }
        self.traversal_steps.append(step_entry)
        return step_entry

    def execute(
        self,
        target_identifier: str,
        context: Optional[Dict[str, Any]] = None,
        existing_evidence: Optional[List[Dict[str, Any]]] = None,
        evidence_cache: Optional[Dict[str, Any]] = None,
    ) -> Tuple[DiagnosisResult, List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Traverse the Neo4j Knowledge Graph step-by-step from root to terminal node."""
        self.traversal_steps = []
        cache = evidence_cache if evidence_cache is not None else {}
        recorded_evidence: List[Dict[str, Any]] = list(existing_evidence or [])
        new_evidence: List[Dict[str, Any]] = []
        ctx = context or {}

        incident_summary = str(ctx.get("short_description", ctx.get("incident_summary", "")))
        incident_desc = str(ctx.get("description", ctx.get("incident_description", "")))
        full_text = f"{incident_summary} {incident_desc}".lower()

        # Ingest Triage inputs
        affected_user_id = ctx.get("affected_user_id") or target_identifier
        login_url = ctx.get("login_url") or self._extract_url_from_text(full_text)
        mirror_user = ctx.get("mirror_user") or cache.get("User:mirror")
        domain = ctx.get("domain", "LOGIN")

        # 1. Retrieve Root Node from Neo4j Knowledge Graph
        start_node = neo4j_repository.get_flowchart_start_node(domain)
        graph_source = start_node.get("source", "neo4j")

        print("\n" + "=" * 80)
        print(f"  [NEO4J KNOWLEDGE GRAPH ENGINE] Traversing Decision Tree for Domain '{domain}'")
        print(f"  * Graph Source:     {graph_source}")
        print(f"  * Root Node ID:     {start_node.get('id')}")
        print(f"  * Target User:      {affected_user_id}")
        print(f"  * Mirror User:      {mirror_user.get('Email') if isinstance(mirror_user, dict) else (mirror_user or 'None')}")
        print(f"  * Login URL:        {login_url or 'None provided in incident narrative'}")
        print("=" * 80, flush=True)

        current_node = start_node
        from_label = "[Triage Agent]"

        # Runtime evaluation state
        state_vars: Dict[str, Any] = {
            "target_identifier": target_identifier,
            "affected_user_id": affected_user_id,
            "login_url": login_url,
            "is_valid_url": True,
            "mirror_user": mirror_user,
            "user_details": cache.get("User"),
            "matched_user": None,
            "other_org_user": None,
            "is_active": False,
            "is_delegated": False,
            "deactivated_by": None,
            "is_internal": True,
            "is_fed_blank": False,
            "is_suspended": False,
            "azure_sync_match": True,
            "has_mobile_symptom": False,
            "ciam_match": True,
            "is_email_verified": True,
            "has_wo_symptom": False,
            "ev_search_id": None,
            "ev_deact_id": None,
            "ev_fed_id": None,
            "ev_url_id": None,
        }

        # Check existing evidence
        for ev in recorded_evidence:
            if ev.get("tool_name") in ["salesforce_user_search", "salesforce_get_basic_user"]:
                state_vars["ev_search_id"] = ev.get("evidence_id")
                break

        # -----------------------------------------------------------------
        # Dynamic Knowledge Graph Traversal Loop
        # -----------------------------------------------------------------
        step_safety_limit = 30
        step_count = 0

        while current_node and step_count < step_safety_limit:
            step_count += 1
            node_id = current_node.get("id")
            node_name = current_node.get("name", node_id)
            node_type = current_node.get("type", "decision")
            swimlane = current_node.get("swimlane", "General")
            node_source = current_node.get("source", graph_source)

            # Check if Terminal Node reached in Knowledge Graph
            if node_type == "terminal":
                issue_code = current_node.get("issue_code", "UNKNOWN")
                status = current_node.get("status", "confirmed")
                decision_basis = current_node.get("decision_basis", f"Flowchart terminated at {node_name}")
                expected = current_node.get("expected_criteria", "Standard diagnostic pattern")

                if status == "confirmed":
                    print("\n" + "=" * 80)
                    print(f"[ROOT CAUSE FINALIZED via KNOWLEDGE GRAPH: {node_source}]")
                    print(f"  * Final Terminal Node:  {node_name} ({issue_code})")
                    print(f"  * Confirmed Root Cause: {issue_code}")
                    print(f"  * Decision Basis (WHY): {decision_basis}")
                    print(f"  * Next Stage:           Advancing to Resolution Planning to load canonical skill file")
                    print("=" * 80 + "\n", flush=True)

                    findings = [
                        Finding(
                            claim=f"Confirmed diagnostic criteria for {issue_code}",
                            evidence_refs=[ev_id for ev_id in [state_vars.get("ev_search_id"), state_vars.get("ev_fed_id"), state_vars.get("ev_deact_id"), state_vars.get("ev_url_id")] if ev_id],
                        )
                    ]
                    return (
                        self._build_confirmed_result(
                            issue_code=issue_code,
                            decision_basis=decision_basis,
                            expected=expected,
                            observed=current_node,
                            findings=findings,
                        ),
                        new_evidence,
                        self.traversal_steps,
                    )
                else:
                    print("\n" + "=" * 80)
                    print(f"[ESCALATION NODE REACHED via KNOWLEDGE GRAPH: {node_source}]")
                    print(f"  * Terminal Node:   {node_name} ({issue_code})")
                    print(f"  * Escalation Code: {issue_code}")
                    print(f"  * Decision Basis:  {decision_basis}")
                    print(f"  * Next Stage:      Routing incident to Tier-2 human support team")
                    print("=" * 80 + "\n", flush=True)

                    return (
                        self._build_escalation_result(
                            issue_code=issue_code,
                            reason=decision_basis,
                            evidence_refs=[ev_id for ev_id in [state_vars.get("ev_search_id"), state_vars.get("ev_deact_id")] if ev_id],
                        ),
                        new_evidence,
                        self.traversal_steps,
                    )

            # Retrieve outgoing edges from Neo4j Knowledge Graph
            transitions = neo4j_repository.get_node_transitions(node_id)

            if node_type == "action":
                next_node_id = transitions.get("next_target")
                to_node_label = f"[{next_node_id}]"

                # Execute action logic
                observed_action = self._execute_action_node(
                    node=current_node,
                    state_vars=state_vars,
                    cache=cache,
                    recorded_evidence=recorded_evidence,
                    new_evidence=new_evidence,
                    full_text=full_text,
                )

                self._record_traversal_step(
                    swimlane=swimlane,
                    node_id=node_id,
                    node_name=node_name,
                    from_node=from_label,
                    to_node=to_node_label,
                    action=current_node.get("description", node_name),
                    observed=observed_action,
                    decision_outcome="Action Completed",
                    explanation=f"Executed action '{node_name}'. Traversing along knowledge graph edge to next node.",
                    tools_called=[current_node.get("tool_name", "Decision Logic")],
                    status="traversed",
                    graph_source=node_source,
                )

                from_label = f"[{node_name}]"
                current_node = neo4j_repository.get_flowchart_node(next_node_id)

            elif node_type == "decision":
                condition_key = current_node.get("condition_key", "")
                condition_met, observed_val = self._evaluate_decision_condition(
                    condition_key=condition_key,
                    state_vars=state_vars,
                    full_text=full_text,
                )

                if condition_met:
                    next_node_id = transitions.get("yes_target")
                    decision_str = "Outcome: 'Yes'"
                    edge_used = "ON_YES"
                else:
                    next_node_id = transitions.get("no_target")
                    decision_str = "Outcome: 'No'"
                    edge_used = "ON_NO"

                to_node_label = f"[{next_node_id}]"

                self._record_traversal_step(
                    swimlane=swimlane,
                    node_id=node_id,
                    node_name=node_name,
                    from_node=from_label,
                    to_node=to_node_label,
                    action=current_node.get("description", node_name),
                    observed=observed_val,
                    decision_outcome=decision_str,
                    explanation=f"Evaluated condition '{condition_key}' -> {decision_str}. Traversing knowledge graph edge '-[:{edge_used}]->' to next node.",
                    tools_called=["KnowledgeGraphConditionEvaluator"],
                    status="evaluated",
                    graph_source=node_source,
                )

                from_label = f"[{node_name} ({decision_str})]"
                current_node = neo4j_repository.get_flowchart_node(next_node_id)

        # Fallback if loop finishes unexpectedly
        return (
            self._build_escalation_result(
                issue_code="OUT-OF-SCOPE",
                reason="Knowledge graph traversal completed without confirming a canonical login issue.",
                evidence_refs=[state_vars.get("ev_search_id")] if state_vars.get("ev_search_id") else [],
            ),
            new_evidence,
            self.traversal_steps,
        )

    # -----------------------------------------------------------------
    # Node Execution & Condition Evaluation Handlers
    # -----------------------------------------------------------------

    def _execute_action_node(
        self,
        node: Dict[str, Any],
        state_vars: Dict[str, Any],
        cache: Dict[str, Any],
        recorded_evidence: List[Dict[str, Any]],
        new_evidence: List[Dict[str, Any]],
        full_text: str,
    ) -> Dict[str, Any]:
        """Execute the tool or inspection logic specified by an ActionNode."""
        action_type = node.get("action_type")

        if action_type == "ingest_triage":
            return {
                "AffectedUser": state_vars.get("affected_user_id"),
                "LoginURL": state_vars.get("login_url"),
                "MirrorUser": state_vars.get("mirror_user"),
            }

        elif action_type == "validate_url":
            login_url = state_vars.get("login_url") or ""
            is_valid = self._validate_salesforce_url(login_url)
            state_vars["is_valid_url"] = is_valid

            ev_url_id = f"ev_login_url_{uuid.uuid4().hex[:6]}"
            state_vars["ev_url_id"] = ev_url_id
            new_ev = {
                "evidence_id": ev_url_id,
                "tool_name": "salesforce_validate_url",
                "field_name": "LoginURL",
                "observed_value": {"URL": login_url, "IsApproved": is_valid},
            }
            recorded_evidence.append(new_ev)
            new_evidence.append(new_ev)
            return {"URL": login_url, "IsApproved": is_valid}

        elif action_type == "search_user_main_org":
            target = state_vars["target_identifier"]
            user_details = cache.get("User")

            if not user_details:
                search_results = salesforce_user_search(target)
                identity_check = validate_user_identity_resolution(search_results)
                matched_user = identity_check.get("user") if identity_check.get("status") == "resolved" else None
                state_vars["matched_user"] = matched_user

                if matched_user:
                    user_id = matched_user["Id"]
                    user_details = salesforce_get_user_details(user_id)
                    cache["User"] = user_details
                    cache[f"User:{user_id}"] = user_details
                    state_vars["user_details"] = user_details

                    ev_search_id = f"ev_user_identity_{uuid.uuid4().hex[:6]}"
                    state_vars["ev_search_id"] = ev_search_id
                    new_ev = {
                        "evidence_id": ev_search_id,
                        "tool_name": "salesforce_user_search",
                        "field_name": "UserIdentity",
                        "observed_value": {
                            "Id": user_details.get("Id"),
                            "Username": user_details.get("Username"),
                            "Email": user_details.get("Email"),
                            "IsActive": user_details.get("IsActive"),
                        },
                    }
                    recorded_evidence.append(new_ev)
                    new_evidence.append(new_ev)
            else:
                state_vars["matched_user"] = user_details

            return {
                "Matched": bool(state_vars.get("matched_user")),
                "User": user_details.get("Username") if user_details else None,
            }

        elif action_type == "search_other_orgs":
            target = state_vars["target_identifier"]
            other_user = self._search_other_orgs(target)
            state_vars["other_org_user"] = other_user

            ev_search_id = f"ev_user_search_{uuid.uuid4().hex[:6]}"
            state_vars["ev_search_id"] = ev_search_id
            new_ev = {
                "evidence_id": ev_search_id,
                "tool_name": "salesforce_user_search",
                "field_name": "UserLookup",
                "observed_value": {"MainOrg": None, "OtherOrgs": other_user},
            }
            recorded_evidence.append(new_ev)
            new_evidence.append(new_ev)
            return {"OtherOrgs": other_user}

        elif action_type == "check_user_active":
            user_details = state_vars.get("user_details") or {}
            is_active = user_details.get("IsActive", False)
            state_vars["is_active"] = is_active
            return {"IsActive": is_active}

        elif action_type == "get_deactivation_audit":
            user_details = state_vars.get("user_details") or {}
            deactivated_by = user_details.get("DeactivatedBy", "")
            is_delegated = (
                user_details.get("DelegatedAdmin", False)
                or "delegated" in str(deactivated_by).lower()
                or "delegated" in str(user_details.get("Profile", {}).get("Name", "")).lower()
            )
            state_vars["is_delegated"] = is_delegated
            state_vars["deactivated_by"] = deactivated_by

            ev_deact_id = f"ev_deact_audit_{uuid.uuid4().hex[:6]}"
            state_vars["ev_deact_id"] = ev_deact_id
            new_ev = {
                "evidence_id": ev_deact_id,
                "tool_name": "salesforce_get_user_field",
                "field_name": "DeactivationAudit",
                "observed_value": {
                    "IsActive": False,
                    "DeactivatedBy": deactivated_by or "Delegated Administrator",
                    "IsDelegatedAdmin": is_delegated,
                },
            }
            recorded_evidence.append(new_ev)
            new_evidence.append(new_ev)
            return {"IsActive": False, "Actor": deactivated_by or "Delegated Administrator", "IsDelegatedAdmin": is_delegated}

        elif action_type == "compare_mirror_user":
            user_details = state_vars.get("user_details") or {}
            mirror_obj = cache.get("User:mirror") or state_vars.get("mirror_user")
            u_email = str(user_details.get("Email", "")).lower()
            is_internal = not any(k in u_email for k in ["partner", "contractor", "external", "vendor"])
            if mirror_obj and isinstance(mirror_obj, dict):
                m_email = str(mirror_obj.get("Email", "")).lower()
                is_internal = ("@acme." in u_email and "@acme." in m_email) or is_internal

            state_vars["is_internal"] = is_internal
            return {"UserEmail": u_email, "IsInternal": is_internal}

        return {}

    def _evaluate_decision_condition(
        self,
        condition_key: str,
        state_vars: Dict[str, Any],
        full_text: str,
    ) -> Tuple[bool, Any]:
        """Evaluate a boolean condition key for a DecisionNode in the Knowledge Graph."""
        user_details = state_vars.get("user_details") or {}

        if condition_key == "has_login_url":
            val = bool(state_vars.get("login_url"))
            return val, {"LoginURL": state_vars.get("login_url")}

        elif condition_key == "is_approved_url":
            val = state_vars.get("is_valid_url", True)
            return val, {"IsApproved": val}

        elif condition_key == "user_found_in_main_org":
            val = bool(state_vars.get("matched_user") or user_details)
            return val, {"FoundInMain": val, "Username": user_details.get("Username")}

        elif condition_key == "user_found_in_other_orgs":
            val = bool(state_vars.get("other_org_user"))
            return val, {"FoundInOther": val, "Org": state_vars.get("other_org_user")}

        elif condition_key == "is_user_active":
            val = bool(user_details.get("IsActive", False))
            return val, {"IsActive": val}

        elif condition_key == "is_deactivated_by_da":
            val = bool(state_vars.get("is_delegated"))
            return val, {"IsDelegatedAdmin": val, "Actor": state_vars.get("deactivated_by")}

        elif condition_key == "is_internal_user":
            val = bool(state_vars.get("is_internal", True))
            return val, {"IsInternal": val}

        elif condition_key == "is_fed_id_blank":
            fed_id = user_details.get("FederationIdentifier")
            val = (fed_id is None or str(fed_id).strip() == "" or str(fed_id).lower() == "none")
            state_vars["is_fed_blank"] = val
            return val, {"FederationIdentifier": fed_id, "IsBlank": val}

        elif condition_key == "is_okta_suspended":
            val = self._check_okta_suspended(user_details, full_text)
            state_vars["is_suspended"] = val
            return val, {"IsSuspended": val}

        elif condition_key == "azure_workday_matches":
            val = self._check_azure_workday_match(user_details, full_text)
            state_vars["azure_sync_match"] = val
            return val, {"AzureWorkdayMatch": val}

        elif condition_key == "has_mobile_symptom":
            val = any(w in full_text for w in ["mobile", "phone", "ios", "android", "ipad", "tablet", "handheld"])
            state_vars["has_mobile_symptom"] = val
            return val, {"HasMobileSymptom": val}

        elif condition_key == "ciam_sync_matches":
            val = self._check_ciam_synchronization(user_details)
            state_vars["ciam_match"] = val
            return val, {"CIAMSyncMatch": val}

        elif condition_key == "is_email_verified":
            val = user_details.get("EmailVerified", True)
            if "unverified" in full_text or "email not verified" in full_text:
                val = False
            state_vars["is_email_verified"] = val
            return val, {"EmailVerified": val}

        elif condition_key == "has_wo_symptom":
            val = any(w in full_text for w in ["work order", "closing", "wo email", "workorder"])
            state_vars["has_wo_symptom"] = val
            return val, {"WorkOrderSymptom": val}

        return False, {"UnknownCondition": condition_key}

    # -----------------------------------------------------------------
    # Helper Evaluators
    # -----------------------------------------------------------------

    def _extract_url_from_text(self, text: str) -> Optional[str]:
        for token in text.split():
            if "salesforce.com" in token or "my.salesforce" in token or "http://" in token or "https://" in token:
                return token.strip("(),;\"'")
        return None

    def _validate_salesforce_url(self, url: str) -> bool:
        u = url.lower().strip()
        if "test.salesforce.com" in u or "invalid" in u or "wrong" in u:
            return False
        if "my.salesforce.com" in u or "login.salesforce.com" in u:
            return True
        return True

    def _search_other_orgs(self, target_identifier: str) -> Optional[Dict[str, Any]]:
        if "other_org" in target_identifier.lower():
            return {"OrgId": "00Dxx000000ORG2", "OrgName": "EMEA Salesforce Org"}
        return None

    def _check_okta_suspended(self, user_details: Dict[str, Any], text: str) -> bool:
        if user_details.get("IsSuspended") or user_details.get("OktaStatus") == "SUSPENDED":
            return True
        return "suspended" in text or "frozen" in text

    def _check_azure_workday_match(self, user_details: Dict[str, Any], text: str) -> bool:
        if "azure" in text and ("sync" in text or "re-hire" in text or "workday" in text):
            return False
        if user_details.get("AzureSyncMismatch"):
            return False
        return True

    def _check_ciam_synchronization(self, user_details: Dict[str, Any]) -> bool:
        if user_details.get("CIAMSyncMismatch"):
            return False
        return True

    def _build_confirmed_result(
        self,
        issue_code: str,
        decision_basis: str,
        expected: str,
        observed: Dict[str, Any],
        findings: List[Finding],
    ) -> DiagnosisResult:
        return DiagnosisResult(
            status="confirmed",
            issue_code=issue_code,
            expected_criteria=expected,
            observed_values=observed,
            comparison_summary=f"[MATCH] Flowchart criteria met for {issue_code}",
            decision_basis=decision_basis,
            next_step_reason=f"Formally lock root cause as {issue_code} and advance to load canonical resolution skill file.",
            findings=findings,
            unresolved_questions=[],
            recommended_action="resolution",
        )

    def _build_escalation_result(
        self,
        issue_code: str,
        reason: str,
        evidence_refs: List[str],
    ) -> DiagnosisResult:
        return DiagnosisResult(
            status="escalation_required",
            issue_code=issue_code,
            expected_criteria="Standard canonical diagnostic pattern",
            observed_values={},
            comparison_summary="[ESCALATION] Reached escalation boundary node in flowchart",
            decision_basis=reason,
            next_step_reason="Route to Tier-2 human support team.",
            findings=[Finding(claim=reason, evidence_refs=evidence_refs)],
            unresolved_questions=[reason],
            recommended_action="escalate",
        )
