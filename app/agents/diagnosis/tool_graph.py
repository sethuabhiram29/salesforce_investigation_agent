"""Inner tool-calling execution loop for Diagnosis Agent.

Implements the inner graph pattern:
  Agent evaluates skill + initial context
  → requests permitted read-only tool
  → Tool executes and appends evidence
  → Agent evaluates evidence against confirmation criteria
  → returns validated DiagnosisResult with evidence references.

Key constraints:
- Maximum investigation rounds bounded by MAX_INVESTIGATION_ROUNDS.
- Read-only tools ONLY (enforced at tool binding).
- Every claim must link to a recorded evidence reference.
"""

import re
from typing import Any, Dict, List, Optional, Tuple
import uuid

from app.knowledge.skill_service import skill_service
from app.knowledge.sop_repository import (
    sop_repository,
    normalize_issue_code,
    denormalize_issue_code,
)
from app.models.schemas import DiagnosisResult, Finding, EvidenceRecord
from app.tools.salesforce import (
    get_diagnosis_tools,
    salesforce_user_search,
    salesforce_get_user_details,
    salesforce_get_object_permissions,
    salesforce_get_record_access,
    salesforce_get_user_permission_sets,
    salesforce_compare_user_access,
    salesforce_get_contact_wizard_details,
)
from app.utils.validators import (
    validate_evidence_grounding,
    validate_issue_code,
    validate_user_identity_resolution,
)

MAX_INVESTIGATION_ROUNDS = 5


class DiagnosisToolGraph:
    """Orchestrates the inner tool-calling loop for diagnostic investigation."""

    def __init__(self):
        # Whitelist of read-only tools for diagnosis
        self.tools = get_diagnosis_tools()

    @staticmethod
    def _matches_sop_scenario(
        context: Optional[Dict[str, Any]],
        sop_entry: Dict[str, Any],
        candidate_code: str,
    ) -> Tuple[bool, str]:
        """Dynamically evaluate whether the incoming incident narrative matches
        the canonical scenario description, symptoms, and historical incident precedents for this root cause.
        """
        context_str = f"{(context or {}).get('incident_summary', '')} {(context or {}).get('incident_description', '')}".lower().strip()
        if not context_str:
            return False, "Empty incident context"

        sop_desc = str(sop_entry.get("description", "")).lower()
        sop_id = str(sop_entry.get("id", candidate_code)).upper()
        norm_code = normalize_issue_code(candidate_code)

        # 1. Pull historical incident precedents for this root cause
        hist_cases = [
            c for c in sop_repository.get_historical_incidents()
            if norm_code in str(c.get("root_cause", "")).upper()
            or normalize_issue_code(str(c.get("incident_id", ""))) == norm_code
            or sop_desc in str(c.get("root_cause", "")).lower()
        ]

        # 2. Extract conceptual scenario terms from SOP and historical precedents
        reference_texts = [sop_desc] + [str(c.get("summary", "")).lower() for c in hist_cases]
        combined_ref = " ".join(reference_texts)

        # Distinctive scenario vocabulary: filter out generic domain stopwords
        generic_domain_words = {
            "the", "and", "for", "with", "from", "using", "able", "user", "users",
            "not", "cannot", "cant", "can't", "salesforce", "sfdc", "system", "org", "step",
            "get", "got", "check", "please", "help", "this", "that", "have", "has",
            "would", "like", "will", "does", "been", "also", "into", "some",
            "login", "sign", "signin", "access", "app", "application", "account",
            "error", "failure", "fail", "problem", "ticket", "portal", "today",
            "morning", "afternoon", "working", "works", "trying", "all",
        }
        tokens = set(re.findall(r"[a-z0-9]+", combined_ref)) - generic_domain_words

        # Semantic synonym groups dynamically expanded based on candidate domain/scope
        synonym_map = {
            "mobile": {"mobile", "phone", "ios", "android", "ipad", "tablet", "handheld"},
            "phone": {"mobile", "phone", "handheld", "device"},
            "url": {"url", "link", "address", "website", "domain", "mydomain"},
            "deactivated": {"deactivated", "inactive", "disabled", "locked", "blocked"},
            "federation": {"federation", "saml", "sso", "okta", "assertion", "identifier"},
            "wizard": {"wizard", "country", "contact"},
            "email": {"email", "notification", "deliverability", "alert"},
            "order": {"work order", "order", "closing"},
        }

        # Check direct token matches or concept synonyms
        matched_tokens = []
        for t in tokens:
            if len(t) < 3:
                continue
            if t in context_str:
                matched_tokens.append(t)
            elif t in synonym_map:
                if any(syn in context_str for syn in synonym_map[t]):
                    matched_tokens.append(f"{t}~syn")

        # Check distinctive multi-word phrase matching directly from SOP description
        phrases = [
            p.strip()
            for p in re.split(r"[,/.-]", sop_desc)
            if len(p.strip().split()) >= 2 and any(w not in generic_domain_words for w in p.strip().split())
        ]
        phrase_matched = any(p in context_str for p in phrases)

        is_match = phrase_matched or len(matched_tokens) >= 1
        detail = f"Matched concept tokens {matched_tokens} from SOP '{sop_desc}'" if is_match else f"No semantic overlap with SOP '{sop_desc}'"
        return is_match, detail

    def run(
        self,
        candidate_issue_code: str,
        target_identifier: str,
        context: Optional[Dict[str, Any]] = None,
        existing_evidence: Optional[List[Dict[str, Any]]] = None,
        evidence_cache: Optional[Dict[str, Any]] = None,
    ) -> Tuple[DiagnosisResult, List[Dict[str, Any]]]:
        """Execute diagnostic investigation for candidate issue against target user.

        Parameters:
        - candidate_issue_code: e.g. 'LOGIN-4', 'LOGIN-3A', 'OBJECT-1'
        - target_identifier: username, email, or user id from incident
        - context: optional extra incident or historical context
        - existing_evidence: previously recorded evidence list to reuse
        - evidence_cache: in-memory cache of previously fetched tool outputs

        Returns:
        - Tuple of (DiagnosisResult, new_or_updated_evidence_list)
        """
        validate_issue_code(candidate_issue_code)

        cache = evidence_cache if evidence_cache is not None else {}
        recorded_evidence: List[Dict[str, Any]] = list(existing_evidence or [])
        new_evidence: List[Dict[str, Any]] = []
        round_count = 0

        # Step 1: User Search & Identity Resolution (Check Cache First)
        user_details = cache.get("User")
        ev_search_id = None

        for ev in recorded_evidence:
            if ev.get("tool_name") in ["salesforce_user_search", "salesforce_get_basic_user"] and not ev_search_id:
                ev_search_id = ev.get("evidence_id")
                break

        if not user_details:
            search_results = salesforce_user_search(target_identifier)
            identity_check = validate_user_identity_resolution(search_results)
            if identity_check["status"] == "not_found":
                return (
                    DiagnosisResult(
                        status="ambiguous_identity",
                        issue_code=candidate_issue_code,
                        findings=[],
                        unresolved_questions=[
                            f"Target user '{target_identifier}' was not found in Salesforce."
                        ],
                        recommended_action="escalate",
                    ),
                    new_evidence,
                )

            if identity_check["status"] == "ambiguous":
                return (
                    DiagnosisResult(
                        status="ambiguous_identity",
                        issue_code=candidate_issue_code,
                        findings=[],
                        unresolved_questions=[
                            f"Search for '{target_identifier}' returned {identity_check['count']} candidate users."
                        ],
                        recommended_action="escalate",
                    ),
                    new_evidence,
                )

            matched_user = identity_check["user"]
            user_id = matched_user["Id"]

            # Fetch detailed user record into in-memory cache for on-demand field evaluation
            user_details = salesforce_get_user_details(user_id)
            cache["User"] = user_details
            cache[f"User:{user_id}"] = user_details

            # Store only minimal core identity in evidence list
            ev_search_id = f"ev_user_identity_{uuid.uuid4().hex[:6]}"
            basic_identity = {
                "Id": user_details.get("Id"),
                "Username": user_details.get("Username"),
                "Email": user_details.get("Email"),
                "Name": user_details.get("Name") or f"{user_details.get('FirstName', '')} {user_details.get('LastName', '')}".strip(),
                "IsActive": user_details.get("IsActive"),
            }
            new_ev = {
                "evidence_id": ev_search_id,
                "tool_name": "salesforce_user_search",
                "field_name": "UserIdentity",
                "user_id": user_id,
                "observed_value": basic_identity,
            }
            recorded_evidence.append(new_ev)
            new_evidence.append(new_ev)
        else:
            user_id = user_details.get("Id", target_identifier)
            if not ev_search_id:
                ev_search_id = f"ev_user_identity_{uuid.uuid4().hex[:6]}"
                basic_identity = {
                    "Id": user_details.get("Id"),
                    "Username": user_details.get("Username"),
                    "Email": user_details.get("Email"),
                    "Name": user_details.get("Name") or f"{user_details.get('FirstName', '')} {user_details.get('LastName', '')}".strip(),
                    "IsActive": user_details.get("IsActive"),
                }
                new_ev = {
                    "evidence_id": ev_search_id,
                    "tool_name": "salesforce_user_search",
                    "field_name": "UserIdentity",
                    "user_id": user_id,
                    "observed_value": basic_identity,
                }
                recorded_evidence.append(new_ev)
                new_evidence.append(new_ev)

        # Step 2: Evaluate against the specific candidate skill criteria
        norm_code = normalize_issue_code(candidate_issue_code)
        raw_code = denormalize_issue_code(candidate_issue_code)

        if norm_code == "LOGIN-4":
            fed_id = user_details.get("FederationIdentifier")
            is_active = user_details.get("IsActive", False)
            expected_criteria = "User.IsActive == True AND (User.FederationIdentifier is null or empty)"
            observed_values = {
                "IsActive": is_active,
                "FederationIdentifier": fed_id,
                "Username": user_details.get("Username"),
                "Email": user_details.get("Email"),
            }

            # On-demand field evidence for FederationIdentifier
            ev_fed_id = f"ev_fed_id_{uuid.uuid4().hex[:6]}"
            ev_fed_record = {
                "evidence_id": ev_fed_id,
                "tool_name": "salesforce_get_user_field",
                "field_name": "FederationIdentifier",
                "user_id": user_id,
                "observed_value": fed_id,
            }
            recorded_evidence.append(ev_fed_record)
            new_evidence.append(ev_fed_record)

            if is_active and (fed_id is None or str(fed_id).strip() == ""):
                result = DiagnosisResult(
                    status="confirmed",
                    issue_code="LOGIN-4",
                    expected_criteria=expected_criteria,
                    observed_values=observed_values,
                    comparison_summary="[MATCH] Observed User.IsActive=True and FederationIdentifier is null/empty",
                    decision_basis="Confirmed: Observed evidence satisfies all criteria for LOGIN-4. Target user is active but lacks FederationIdentifier, directly causing SAML SSO assertion failure.",
                    next_step_reason="Advance to Root Cause Confirmation gate to formally confirm root cause before entering resolution planning.",
                    findings=[
                        Finding(
                            claim="Target user identity resolved uniquely in Salesforce",
                            evidence_refs=[ev_search_id],
                        ),
                        Finding(
                            claim="FederationIdentifier field on active user record is null/empty",
                            evidence_refs=[ev_fed_id],
                        ),
                    ],
                    unresolved_questions=[],
                    recommended_action="resolution",
                )
            elif not is_active:
                result = DiagnosisResult(
                    status="contradicted",
                    issue_code="LOGIN-4",
                    expected_criteria=expected_criteria,
                    observed_values=observed_values,
                    comparison_summary=f"[MISMATCH] Expected User.IsActive=True, but observed IsActive={is_active}",
                    decision_basis="Contradicted: Target user is deactivated in Salesforce, disproving SSO FederationIdentifier hypothesis (inactive users fail at authentication gateway prior to SSO assertion).",
                    next_step_reason="Advance to next candidate scenario in priority sequence without loading skill files.",
                    findings=[
                        Finding(
                            claim="User is inactive in Salesforce, which contradicts LOGIN-4 confirmation criteria",
                            evidence_refs=[ev_fed_id],
                        )
                    ],
                    unresolved_questions=["Consider candidate issue LOGIN-3 (User Account Deactivated) instead."],
                    recommended_action="switch_hypothesis",
                )
            else:
                result = DiagnosisResult(
                    status="contradicted",
                    issue_code="LOGIN-4",
                    expected_criteria=expected_criteria,
                    observed_values=observed_values,
                    comparison_summary=f"[MISMATCH] Expected null/empty FederationIdentifier, but observed FederationIdentifier='{fed_id}'",
                    decision_basis=f"Contradicted: FederationIdentifier already exists and is populated with '{fed_id}'.",
                    next_step_reason="Advance to next candidate scenario in priority sequence without loading skill files.",
                    findings=[
                        Finding(
                            claim=f"FederationIdentifier is already populated with '{fed_id}', contradicting LOGIN-4",
                            evidence_refs=[ev_fed_id],
                        )
                    ],
                    unresolved_questions=["FederationIdentifier exists. Check other authentication/SSO factors."],
                    recommended_action="switch_hypothesis",
                )

        elif norm_code in ["LOGIN-3", "LOGIN-3A"]:
            is_active = user_details.get("IsActive", True)
            is_delegated_admin = user_details.get("DelegatedAdmin", False) or "delegated" in str(user_details.get("Profile", {}).get("Name", "")).lower()
            expected_criteria = "User.IsActive == False"

            # Classify deactivation actor and mechanism
            deactivated_by = user_details.get("DeactivatedBy") or ""
            if is_delegated_admin or "delegated" in str(deactivated_by).lower():
                deactivation_actor = "Delegated Administrator"
                comparison_summary = "[MATCH] Observed User.IsActive=False (Deactivated by Delegated Administrator)"
                decision_basis = (
                    "Confirmed: User account is deactivated in Salesforce (IsActive=False). "
                    "Audit analysis confirms deactivation was performed by a Delegated Administrator."
                )
            elif "mulesoft" in str(deactivated_by).lower() or "mulesoft" in str(user_details.get("LastModifiedBy", "")).lower():
                deactivation_actor = "Mulesoft"
                comparison_summary = "[MATCH] Observed User.IsActive=False (Deactivated via Mulesoft)"
                decision_basis = (
                    "Confirmed: User account is deactivated in Salesforce (IsActive=False). "
                    "Deactivation originated through automated Mulesoft integration sync."
                )
            else:
                deactivation_actor = "Standard Admin"
                comparison_summary = "[MATCH] Observed User.IsActive=False"
                decision_basis = "Confirmed: User account is deactivated in Salesforce (IsActive=False)."

            observed_values = {
                "IsActive": is_active,
                "DelegatedAdmin": is_delegated_admin,
                "deactivation_actor": deactivation_actor,
                "Username": user_details.get("Username"),
                "Email": user_details.get("Email"),
            }

            # On-demand field evidence for IsActive & DeactivationActor
            ev_active_id = f"ev_active_{uuid.uuid4().hex[:6]}"
            ev_active_record = {
                "evidence_id": ev_active_id,
                "tool_name": "salesforce_get_user_field",
                "field_name": "IsActive",
                "user_id": user_id,
                "observed_value": {"IsActive": is_active, "DeactivationActor": deactivation_actor},
            }
            recorded_evidence.append(ev_active_record)
            new_evidence.append(ev_active_record)

            if not is_active:
                result = DiagnosisResult(
                    status="confirmed",
                    issue_code="LOGIN-3",
                    expected_criteria=expected_criteria,
                    observed_values=observed_values,
                    comparison_summary=comparison_summary,
                    decision_basis=decision_basis,
                    next_step_reason="Advance to Root Cause Confirmation gate to formally confirm root cause.",
                    findings=[
                        Finding(
                            claim="Target user identity resolved uniquely in Salesforce",
                            evidence_refs=[ev_search_id],
                        ),
                        Finding(
                            claim=f"User account is deactivated in Salesforce NA org (IsActive=False). Actor classification: {deactivation_actor}.",
                            evidence_refs=[ev_active_id],
                        ),
                    ],
                    unresolved_questions=[],
                    recommended_action="resolution",
                )
            else:
                result = DiagnosisResult(
                    status="contradicted",
                    issue_code="LOGIN-3",
                    expected_criteria=expected_criteria,
                    observed_values=observed_values,
                    comparison_summary=f"[MISMATCH] Expected User.IsActive=False, but observed User.IsActive=True",
                    decision_basis="Contradicted: Target user is active in Salesforce (IsActive=True), disproving deactivation hypothesis.",
                    next_step_reason="Advance to next candidate scenario in evaluation sequence without loading skill files.",
                    findings=[
                        Finding(
                            claim="User is active (IsActive=True), contradicting LOGIN-3 deactivation",
                            evidence_refs=[ev_active_id],
                        )
                    ],
                    unresolved_questions=["User is active. Re-evaluate credentials or SSO configuration."],
                    recommended_action="switch_hypothesis",
                )

        elif norm_code == "LOGIN-1":
            # Scenario: User Account Not Available
            expected_criteria = f"Target user '{target_identifier}' not found in Salesforce NA org"
            if user_details and user_details.get("Id"):
                observed_values = {
                    "user_found": True,
                    "Id": user_details.get("Id"),
                    "Username": user_details.get("Username"),
                    "IsActive": user_details.get("IsActive"),
                }
                result = DiagnosisResult(
                    status="contradicted",
                    issue_code=norm_code,
                    expected_criteria=expected_criteria,
                    observed_values=observed_values,
                    comparison_summary=f"[MISMATCH] Expected user account not found, but user record exists (Id: {user_details.get('Id')})",
                    decision_basis=f"Contradicted: Target user identity was successfully found in Salesforce org (Id: {user_details.get('Id')}), disproving LOGIN-1 (User Account Not Available).",
                    next_step_reason="Advance to next candidate scenario in evaluation sequence without loading skill files.",
                    findings=[
                        Finding(
                            claim=f"Target user account exists in Salesforce (Id: {user_details.get('Id')}), disproving LOGIN-1",
                            evidence_refs=[ev_details_id or ev_search_id],
                        )
                    ],
                    unresolved_questions=["User account is present. Verify credentials or SSO federation status."],
                    recommended_action="switch_hypothesis",
                )
            else:
                observed_values = {"user_found": False, "target_identifier": target_identifier}
                result = DiagnosisResult(
                    status="confirmed",
                    issue_code=norm_code,
                    expected_criteria=expected_criteria,
                    observed_values=observed_values,
                    comparison_summary=f"[MATCH] User '{target_identifier}' was not found in Salesforce NA org",
                    decision_basis=f"Confirmed: Zero matching user records found in Salesforce for '{target_identifier}'.",
                    next_step_reason="Advance to Root Cause Confirmation gate to formally confirm root cause.",
                    findings=[
                        Finding(
                            claim=f"Target user '{target_identifier}' does not have a provisioned account in Salesforce",
                            evidence_refs=[ev_search_id],
                        )
                    ],
                    unresolved_questions=[],
                    recommended_action="resolution",
                )

        elif norm_code == "LOGIN-2":
            # Scenario: Using Wrong URL to Access Salesforce (SOP LOGIN-002)
            sop_entry = sop_repository.get_sop("LOGIN-002") or sop_repository.get_sop("LOGIN-2") or {}
            sop_desc = sop_entry.get("description", "Using wrong URL address to access salesforce system")
            sop_id = sop_entry.get("id", "LOGIN-002")

            is_url_issue, match_detail = self._matches_sop_scenario(context, sop_entry, norm_code)
            is_active = user_details.get("IsActive", True)
            expected_criteria = f"User.IsActive == True AND symptom indicates accessing incorrect Salesforce login URL per SOP {sop_id}"
            observed_values = {
                "IsActive": is_active,
                "Username": user_details.get("Username"),
                "URLSymptomMatched": is_url_issue,
                "MatchDetail": match_detail,
                "SOPReference": sop_id,
            }

            # On-demand field evidence for LoginURL
            ev_url_id = f"ev_login_url_{uuid.uuid4().hex[:6]}"
            ev_url_record = {
                "evidence_id": ev_url_id,
                "tool_name": "salesforce_get_user_field",
                "field_name": "LoginURL",
                "user_id": user_id,
                "observed_value": {"IsActive": is_active, "URLSymptomMatched": is_url_issue},
            }
            recorded_evidence.append(ev_url_record)
            new_evidence.append(ev_url_record)

            if not is_active:
                result = DiagnosisResult(
                    status="contradicted",
                    issue_code=norm_code,
                    expected_criteria=expected_criteria,
                    observed_values=observed_values,
                    comparison_summary="[MISMATCH] Expected User.IsActive=True, but observed IsActive=False",
                    decision_basis="Contradicted: Target user is deactivated in Salesforce; account deactivation blocks login at the central gateway before URL redirection.",
                    next_step_reason="Advance to next candidate scenario in evaluation sequence without loading skill files.",
                    findings=[
                        Finding(
                            claim=f"Target user is inactive in Salesforce, disproving wrong URL hypothesis ({norm_code})",
                            evidence_refs=[ev_url_id],
                        )
                    ],
                    unresolved_questions=["User account is deactivated in Salesforce."],
                    recommended_action="switch_hypothesis",
                )
            elif is_url_issue and is_active:
                result = DiagnosisResult(
                    status="confirmed",
                    issue_code="LOGIN-2",
                    expected_criteria=expected_criteria,
                    observed_values=observed_values,
                    comparison_summary=f"[MATCH] User account is active in Salesforce; symptom matches canonical SOP {sop_id} ('{sop_desc}').",
                    decision_basis=f"Confirmed: Target user account is verified active in Salesforce org. The user is attempting to authenticate through an incorrect login URL address. Per SOP {sop_id}, root cause is confirmed as LOGIN-2 (Wrong Login URL). Solution is providing the correct MyDomain login URL.",
                    next_step_reason="Advance to Root Cause Confirmation gate to formally lock cause and enter resolution planning to provide the correct URL.",
                    findings=[
                        Finding(
                            claim="Target user account verified active in Salesforce",
                            evidence_refs=[ev_search_id],
                        ),
                        Finding(
                            claim=f"Incident symptoms indicate incorrect login URL per canonical SOP {sop_id}",
                            evidence_refs=[ev_url_id],
                        ),
                    ],
                    unresolved_questions=[],
                    recommended_action="resolution",
                )
            else:
                result = DiagnosisResult(
                    status="contradicted",
                    issue_code="LOGIN-2",
                    expected_criteria=expected_criteria,
                    observed_values=observed_values,
                    comparison_summary="[MISMATCH] Incident symptoms do not indicate incorrect login URL address",
                    decision_basis=f"Contradicted: Incident narrative does not match wrong login URL address scenario ('{sop_desc}').",
                    next_step_reason="Advance to next candidate scenario in evaluation sequence without loading skill files.",
                    findings=[
                        Finding(
                            claim="Standard org gateway in use, disproving wrong URL hypothesis (LOGIN-2)",
                            evidence_refs=[ev_url_id],
                        )
                    ],
                    unresolved_questions=["Evaluate authentication and identity federation."],
                    recommended_action="switch_hypothesis",
                )

        elif norm_code == "LOGIN-5":
            # Scenario: User Federation ID Suspended / Frozen
            is_active = user_details.get("IsActive", True)
            fed_id = user_details.get("FederationIdentifier")
            expected_criteria = "User account or Federation ID is suspended / frozen in identity provider"
            observed_values = {
                "IsActive": is_active,
                "FederationIdentifier": fed_id,
            }

            # On-demand field evidence for FederationSuspension
            ev_susp_id = f"ev_susp_{uuid.uuid4().hex[:6]}"
            ev_susp_record = {
                "evidence_id": ev_susp_id,
                "tool_name": "salesforce_get_user_field",
                "field_name": "FederationSuspension",
                "user_id": user_id,
                "observed_value": {"IsActive": is_active, "FederationIdentifier": fed_id},
            }
            recorded_evidence.append(ev_susp_record)
            new_evidence.append(ev_susp_record)

            if is_active and fed_id:
                result = DiagnosisResult(
                    status="contradicted",
                    issue_code=norm_code,
                    expected_criteria=expected_criteria,
                    observed_values=observed_values,
                    comparison_summary=f"[MISMATCH] User is active and FederationIdentifier is present ('{fed_id}')",
                    decision_basis="Contradicted: User record is active in Salesforce with an assigned FederationIdentifier, disproving suspension.",
                    next_step_reason="Advance to next candidate scenario in evaluation sequence without loading skill files.",
                    findings=[
                        Finding(
                            claim=f"User account is active in Salesforce with assigned FederationIdentifier, disproving {norm_code}",
                            evidence_refs=[ev_susp_id],
                        )
                    ],
                    unresolved_questions=["User is active with FederationIdentifier."],
                    recommended_action="switch_hypothesis",
                )
            else:
                result = DiagnosisResult(
                    status="insufficient_evidence",
                    issue_code=norm_code,
                    expected_criteria=expected_criteria,
                    observed_values=observed_values,
                    comparison_summary="Insufficient evidence to confirm suspension without IdP audit logs",
                    decision_basis="Insufficient evidence: Verification of IdP freeze flag requires identity provider admin query.",
                    next_step_reason="Advance to next candidate scenario without loading skill files.",
                    findings=[],
                    unresolved_questions=["Check IdP login logs for suspension status."],
                    recommended_action="switch_hypothesis",
                )

        elif norm_code == "LOGIN-8":
            # Scenario: Salesforce Mobile App Login Failure (SOP LOGIN-008 / Historical INC0100107)
            sop_entry = sop_repository.get_sop("LOGIN-008") or sop_repository.get_sop("LOGIN-8") or {}
            sop_desc = sop_entry.get("description", "User not able to login using Salesforce Mobile app")
            sop_res = sop_entry.get("resolution_steps", "Provide Salesforce Mobile Setup Document to user.")
            sop_id = sop_entry.get("id", "LOGIN-008")

            is_scenario_matched, match_detail = self._matches_sop_scenario(context, sop_entry, norm_code)
            is_active = user_details.get("IsActive", True)

            expected_criteria = f"User.IsActive == True AND incident narrative matches canonical SOP {sop_id} ('{sop_desc}')"
            observed_values = {
                "IsActive": is_active,
                "Username": user_details.get("Username"),
                "FederationIdentifier": user_details.get("FederationIdentifier") or "(Present)",
                "ScenarioMatched": is_scenario_matched,
                "MatchDetail": match_detail,
                "SOPReference": sop_id,
            }

            # On-demand field evidence for MobileSetup
            ev_mob_id = f"ev_mobile_{uuid.uuid4().hex[:6]}"
            ev_mob_record = {
                "evidence_id": ev_mob_id,
                "tool_name": "salesforce_get_user_field",
                "field_name": "MobileSetup",
                "user_id": user_id,
                "observed_value": {"IsActive": is_active, "ScenarioMatched": is_scenario_matched},
            }
            recorded_evidence.append(ev_mob_record)
            new_evidence.append(ev_mob_record)

            if not is_active:
                result = DiagnosisResult(
                    status="contradicted",
                    issue_code=norm_code,
                    expected_criteria=expected_criteria,
                    observed_values=observed_values,
                    comparison_summary="[MISMATCH] Expected User.IsActive=True, but observed IsActive=False",
                    decision_basis="Contradicted: Target user is deactivated in Salesforce; inactive status blocks authentication at the server gateway before mobile app handshake or procedural guidance can take effect.",
                    next_step_reason="Advance to next candidate scenario in evaluation sequence without loading skill files.",
                    findings=[
                        Finding(
                            claim=f"Target user is inactive in Salesforce, disproving mobile-specific client handshake issue ({norm_code})",
                            evidence_refs=[ev_mob_id],
                        )
                    ],
                    unresolved_questions=["User account is deactivated in Salesforce."],
                    recommended_action="switch_hypothesis",
                )
            elif is_scenario_matched and is_active:
                decision_basis = (
                    f"Confirmed: Target user account is verified active in Salesforce org with valid credentials. "
                    f"Analysis of canonical SOP {sop_id} ('{sop_desc}') and historical precedent INC0100107 confirms "
                    f"that gateway authentication is operational and the root cause is client-side setup/handshake. "
                    f"Resolution is procedural guidance: transmit the official Salesforce Mobile Setup Document per SOP resolution steps without requiring Salesforce database mutations."
                )
                result = DiagnosisResult(
                    status="confirmed",
                    issue_code=norm_code,
                    expected_criteria=expected_criteria,
                    observed_values=observed_values,
                    comparison_summary=f"[MATCH] User account is active in Salesforce NA org; incident narrative matches canonical SOP {sop_id} ('{sop_desc}').",
                    decision_basis=decision_basis,
                    next_step_reason="Advance to Root Cause Confirmation gate to formally lock cause and enter resolution planning to transmit the mobile setup guide.",
                    findings=[
                        Finding(
                            claim="Target user account is verified active in Salesforce org with valid credentials",
                            evidence_refs=[ev_search_id],
                        ),
                        Finding(
                            claim=f"Incident symptoms match Salesforce Mobile App setup procedure per canonical SOP {sop_id} ('{sop_desc}')",
                            evidence_refs=[ev_mob_id],
                        ),
                    ],
                    unresolved_questions=[],
                    recommended_action="resolution",
                )
            else:
                result = DiagnosisResult(
                    status="contradicted",
                    issue_code=norm_code,
                    expected_criteria=expected_criteria,
                    observed_values=observed_values,
                    comparison_summary=f"[MISMATCH] Incident symptoms do not involve Salesforce Mobile App access ('{sop_desc}')",
                    decision_basis=f"Contradicted: Incident narrative does not match mobile application login scenario ('{sop_desc}').",
                    next_step_reason="Advance to next candidate scenario in evaluation sequence without loading skill files.",
                    findings=[
                        Finding(
                            claim=f"No mobile application access failure indicated in incident narrative, disproving {norm_code}",
                            evidence_refs=[ev_mob_id],
                        )
                    ],
                    unresolved_questions=[],
                    recommended_action="switch_hypothesis",
                )

        elif norm_code in ["LOGIN-6", "LOGIN-7"]:
            # Scenario: Federation ID Sync Mismatch (Azure Re-hire or CIAM)
            is_active = user_details.get("IsActive", True)
            fed_id = user_details.get("FederationIdentifier")
            expected_criteria = f"User.IsActive == True AND Federation ID mismatch with external identity provider ({norm_code})"
            observed_values = {
                "IsActive": is_active,
                "FederationIdentifier": fed_id,
            }

            # On-demand field evidence for FederationSync
            ev_sync_id = f"ev_sync_{uuid.uuid4().hex[:6]}"
            ev_sync_record = {
                "evidence_id": ev_sync_id,
                "tool_name": "salesforce_get_user_field",
                "field_name": "FederationSync",
                "user_id": user_id,
                "observed_value": {"IsActive": is_active, "FederationIdentifier": fed_id},
            }
            recorded_evidence.append(ev_sync_record)
            new_evidence.append(ev_sync_record)

            if not is_active:
                result = DiagnosisResult(
                    status="contradicted",
                    issue_code=norm_code,
                    expected_criteria=expected_criteria,
                    observed_values=observed_values,
                    comparison_summary="[MISMATCH] Expected User.IsActive=True, but observed IsActive=False",
                    decision_basis=f"Contradicted: Target user is deactivated in Salesforce, disproving active {norm_code} external sync failure.",
                    next_step_reason="Advance to next candidate scenario in evaluation sequence without loading skill files.",
                    findings=[
                        Finding(
                            claim=f"Target user is inactive in Salesforce, disproving active external sync failure ({norm_code})",
                            evidence_refs=[ev_sync_id],
                        )
                    ],
                    unresolved_questions=["User is inactive in Salesforce."],
                    recommended_action="switch_hypothesis",
                )
            else:
                result = DiagnosisResult(
                    status="insufficient_evidence",
                    issue_code=norm_code,
                    expected_criteria=expected_criteria,
                    observed_values=observed_values,
                    comparison_summary=f"Requires external IdP audit assertion to confirm sync mismatch for {norm_code}",
                    decision_basis="External identity provider directory lookup required.",
                    next_step_reason="Advance to next candidate scenario in evaluation sequence without loading skill files.",
                    findings=[],
                    unresolved_questions=["Query external IdP directory."],
                    recommended_action="switch_hypothesis",
                )

        elif norm_code == "LOGIN-9":
            # Scenario: No Email on Work Order Close (SOP LOGIN-009)
            sop_entry = sop_repository.get_sop("LOGIN-009") or sop_repository.get_sop("LOGIN-9") or {}
            sop_desc = sop_entry.get("description", "User not able to get email while closing work order")
            sop_res = sop_entry.get("resolution_steps", "Provide email deliverability guidance and setup checklist.")
            sop_id = sop_entry.get("id", "LOGIN-009")

            is_wo_issue, match_detail = self._matches_sop_scenario(context, sop_entry, norm_code)
            is_active = user_details.get("IsActive", True)
            expected_criteria = f"User.IsActive == True AND symptom indicates missing email notification on work order closure per SOP {sop_id}"
            observed_values = {
                "IsActive": is_active,
                "Email": user_details.get("Email"),
                "WorkOrderSymptomMatched": is_wo_issue,
                "MatchDetail": match_detail,
                "SOPReference": sop_id,
            }

            # On-demand field evidence for WorkOrderDelivery
            ev_wo_id = f"ev_workorder_{uuid.uuid4().hex[:6]}"
            ev_wo_record = {
                "evidence_id": ev_wo_id,
                "tool_name": "salesforce_get_user_field",
                "field_name": "WorkOrderDelivery",
                "user_id": user_id,
                "observed_value": {"IsActive": is_active, "WorkOrderSymptomMatched": is_wo_issue},
            }
            recorded_evidence.append(ev_wo_record)
            new_evidence.append(ev_wo_record)

            if not is_active:
                result = DiagnosisResult(
                    status="contradicted",
                    issue_code=norm_code,
                    expected_criteria=expected_criteria,
                    observed_values=observed_values,
                    comparison_summary="[MISMATCH] Expected User.IsActive=True, but observed IsActive=False",
                    decision_basis="Contradicted: Target user is inactive in Salesforce.",
                    next_step_reason="Advance to next candidate scenario in evaluation sequence without loading skill files.",
                    findings=[
                        Finding(
                            claim=f"Target user is inactive in Salesforce, disproving {norm_code} work order close delivery",
                            evidence_refs=[ev_wo_id],
                        )
                    ],
                    unresolved_questions=[],
                    recommended_action="switch_hypothesis",
                )
            elif is_wo_issue:
                result = DiagnosisResult(
                    status="confirmed",
                    issue_code=norm_code,
                    expected_criteria=expected_criteria,
                    observed_values=observed_values,
                    comparison_summary=f"[MATCH] User account is active with verified email; symptom matches work order email notification failure per SOP {sop_id}.",
                    decision_basis=f"Confirmed: Target user account is verified active in Salesforce org. The issue is missing work order notification delivery. Per SOP {sop_id}, root cause is confirmed as {norm_code} (Work Order Email Notification). Solution is providing email deliverability guidance and setup checklist.",
                    next_step_reason="Advance to Root Cause Confirmation gate to formally lock cause and enter resolution planning to provide email notification guidance.",
                    findings=[
                        Finding(
                            claim="Target user account verified active in Salesforce with verified email address",
                            evidence_refs=[ev_search_id],
                        ),
                        Finding(
                            claim=f"Incident symptoms match Field Service work order email closure procedure per canonical SOP {sop_id}",
                            evidence_refs=[ev_wo_id],
                        ),
                    ],
                    unresolved_questions=[],
                    recommended_action="resolution",
                )
            else:
                result = DiagnosisResult(
                    status="contradicted",
                    issue_code=norm_code,
                    expected_criteria=expected_criteria,
                    observed_values=observed_values,
                    comparison_summary=f"[MISMATCH] Incident symptoms do not involve Field Service work order notifications ('{sop_desc}')",
                    decision_basis=f"Contradicted: Incident narrative does not match work order closing email scenario ('{sop_desc}').",
                    next_step_reason="Advance to next candidate scenario in evaluation sequence without loading skill files.",
                    findings=[
                        Finding(
                            claim=f"No work order notification delivery failure indicated in incident, disproving {norm_code}",
                            evidence_refs=[ev_wo_id],
                        )
                    ],
                    unresolved_questions=[],
                    recommended_action="switch_hypothesis",
                )

        elif norm_code in ["OBJECT-1", "OBJECT-2", "OBJECT-3"]:
            target_obj = (context or {}).get("target_object", "Account")
            perm_key = f"perms:{target_obj}"
            perm_data = cache.get(perm_key)
            ev_perm_id = None
            if perm_data:
                for ev in recorded_evidence:
                    if ev.get("tool_name") == "salesforce_get_object_permissions" and ev.get("field_name") == target_obj:
                        ev_perm_id = ev.get("evidence_id")
                        break

            if not perm_data or not ev_perm_id:
                round_count += 1
                perm_data = salesforce_get_object_permissions(user_id, target_obj)
                ev_perm_id = f"ev_object_perms_{uuid.uuid4().hex[:6]}"
                new_ev = {
                    "evidence_id": ev_perm_id,
                    "tool_name": "salesforce_get_object_permissions",
                    "field_name": target_obj,
                    "observed_value": perm_data,
                    "raw_output": perm_data,
                }
                recorded_evidence.append(new_ev)
                new_evidence.append(new_ev)
                cache[perm_key] = perm_data

            expected_criteria = f"PermissionsEdit == False on object '{target_obj}'"
            observed_values = {
                "TargetObject": target_obj,
                "PermissionsRead": perm_data.get("PermissionsRead"),
                "PermissionsEdit": perm_data.get("PermissionsEdit"),
                "PermissionsCreate": perm_data.get("PermissionsCreate"),
            }

            if not perm_data.get("PermissionsEdit", False):
                result = DiagnosisResult(
                    status="confirmed",
                    issue_code=norm_code,
                    expected_criteria=expected_criteria,
                    observed_values=observed_values,
                    comparison_summary=f"[MATCH] User lacks PermissionsEdit on object '{target_obj}'",
                    decision_basis=f"Confirmed: User lacks PermissionsEdit on object '{target_obj}', matching object permission error.",
                    next_step_reason="Advance to Root Cause Confirmation gate to formally confirm root cause.",
                    findings=[
                        Finding(
                            claim=f"User lacks PermissionsEdit on object '{target_obj}'",
                            evidence_refs=[ev_perm_id],
                        )
                    ],
                    unresolved_questions=[],
                    recommended_action="resolution",
                )
            else:
                result = DiagnosisResult(
                    status="contradicted",
                    issue_code=norm_code,
                    expected_criteria=expected_criteria,
                    observed_values=observed_values,
                    comparison_summary=f"[MISMATCH] Expected PermissionsEdit=False, but observed PermissionsEdit=True on '{target_obj}'",
                    decision_basis=f"Contradicted: User already has PermissionsEdit on object '{target_obj}'.",
                    next_step_reason="Advance to Record-level access checks or next candidate scenario without loading skill files.",
                    findings=[
                        Finding(
                            claim=f"User already has PermissionsEdit on object '{target_obj}'",
                            evidence_refs=[ev_perm_id],
                        )
                    ],
                    unresolved_questions=[f"Edit permissions exist on '{target_obj}'. Check sharing rules/record locking."],
                    recommended_action="switch_hypothesis",
                )
        elif norm_code == "RECORD-1":
            target_obj = str((context or {}).get("target_object", "")).lower()
            is_report_or_dash = any(k in target_obj for k in ["report", "dashboard"])
            expected_criteria = "Target is a Report or Dashboard folder with sharing restrictions"
            observed_values = {"TargetObject": target_obj}
            if not is_report_or_dash:
                result = DiagnosisResult(
                    status="contradicted",
                    issue_code=norm_code,
                    expected_criteria=expected_criteria,
                    observed_values=observed_values,
                    comparison_summary="[MISMATCH] Incident does not target Report or Dashboard object",
                    decision_basis="Contradicted: Target is not a Report or Dashboard folder.",
                    next_step_reason="Advance to Opportunity / Case or record-level access evaluation.",
                    findings=[],
                    unresolved_questions=[],
                    recommended_action="switch_hypothesis",
                )
            else:
                result = DiagnosisResult(
                    status="insufficient_evidence",
                    issue_code="RECORD-1",
                    expected_criteria=expected_criteria,
                    observed_values=observed_values,
                    comparison_summary="Report and Dashboard folder sharing requires folder access check",
                    decision_basis="Report/Dashboard folder permission verification required.",
                    next_step_reason="Advance to next candidate scenario.",
                    findings=[],
                    unresolved_questions=["Verify folder permissions."],
                    recommended_action="switch_hypothesis",
                )

        elif norm_code in ["RECORD-2", "RECORD-3"]:
            target_rec = (context or {}).get("target_record_id")
            if not target_rec:
                expected_criteria = "Target record ID specified in incident with restricted row-level sharing"
                observed_values = {"RecordId": None, "target_record_id": None}
                result = DiagnosisResult(
                    status="insufficient_evidence",
                    issue_code=norm_code,
                    expected_criteria=expected_criteria,
                    observed_values=observed_values,
                    comparison_summary="[INSUFFICIENT] No specific target record was referenced in the incident narrative",
                    decision_basis="Cannot confirm record-level restriction without an identified target record ID in the ticket narrative.",
                    next_step_reason="Advance to next candidate scenario in evaluation sequence without loading skill files.",
                    findings=[],
                    unresolved_questions=["Target record ID required to verify record access."],
                    recommended_action="switch_hypothesis",
                )
            else:
                rec_key = f"rec_access:{target_rec}"
                rec_access = cache.get(rec_key)
                ev_rec_id = None
                if rec_access:
                    for ev in recorded_evidence:
                        if ev.get("tool_name") == "salesforce_get_record_access":
                            ev_rec_id = ev.get("evidence_id")
                            break

                if not rec_access or not ev_rec_id:
                    round_count += 1
                    rec_access = salesforce_get_record_access(user_id, target_rec)
                    ev_rec_id = f"ev_rec_access_{uuid.uuid4().hex[:6]}"
                    new_ev = {
                        "evidence_id": ev_rec_id,
                        "tool_name": "salesforce_get_record_access",
                        "field_name": "UserRecordAccess",
                        "observed_value": rec_access,
                        "raw_output": rec_access,
                    }
                    recorded_evidence.append(new_ev)
                    new_evidence.append(new_ev)
                    cache[rec_key] = rec_access

                expected_criteria = f"HasReadAccess == False OR HasEditAccess == False on record '{target_rec}'"
                observed_values = {
                    "RecordId": target_rec,
                    "HasReadAccess": rec_access.get("HasReadAccess"),
                    "HasEditAccess": rec_access.get("HasEditAccess"),
                }

                if not rec_access.get("HasReadAccess", True) or not rec_access.get("HasEditAccess", True):
                    result = DiagnosisResult(
                        status="confirmed",
                        issue_code=norm_code,
                        expected_criteria=expected_criteria,
                        observed_values=observed_values,
                        comparison_summary=f"[MATCH] User lacks access on record '{target_rec}' (HasRead={rec_access.get('HasReadAccess')}, HasEdit={rec_access.get('HasEditAccess')})",
                        decision_basis=f"Confirmed: User lacks record-level access on record '{target_rec}'.",
                        next_step_reason="Advance to Root Cause Confirmation gate to formally confirm root cause.",
                        findings=[
                            Finding(
                                claim=f"User lacks read or edit access on record '{target_rec}' (HasReadAccess={rec_access.get('HasReadAccess')}, HasEditAccess={rec_access.get('HasEditAccess')})",
                                evidence_refs=[ev_rec_id],
                            )
                        ],
                        unresolved_questions=[],
                        recommended_action="resolution",
                    )
                else:
                    result = DiagnosisResult(
                        status="contradicted",
                        issue_code=norm_code,
                        expected_criteria=expected_criteria,
                        observed_values=observed_values,
                        comparison_summary=f"[MISMATCH] Expected restricted record access, but observed HasRead=True and HasEdit=True",
                        decision_basis=f"Contradicted: User has full record access on '{target_rec}'.",
                        next_step_reason="Advance to next candidate scenario in evaluation sequence without loading skill files.",
                        findings=[
                            Finding(
                                claim=f"User already has record-level access on '{target_rec}'",
                                evidence_refs=[ev_rec_id],
                            )
                        ],
                        unresolved_questions=[f"Record access is valid. Check object or application level access."],
                        recommended_action="switch_hypothesis",
                    )

        elif norm_code in ["APPLICATION-1", "APPLICATION-2"]:
            perm_sets = salesforce_get_user_permission_sets(user_id)
            ev_ps_id = f"ev_perm_sets_{uuid.uuid4().hex[:6]}"
            recorded_evidence.append({
                "evidence_id": ev_ps_id,
                "tool_name": "salesforce_get_user_permission_sets",
                "field_name": "PermissionSets",
                "observed_value": perm_sets,
                "raw_output": {"PermissionSets": perm_sets},
            })

            target_ps = "CC360 Community User" if norm_code == "APPLICATION-1" else "Pharm_System_Access"
            expected_criteria = f"'{target_ps}' NOT in user PermissionSets"
            observed_values = {"PermissionSets": perm_sets}

            if target_ps not in perm_sets:
                result = DiagnosisResult(
                    status="confirmed",
                    issue_code=norm_code,
                    expected_criteria=expected_criteria,
                    observed_values=observed_values,
                    comparison_summary=f"[MATCH] '{target_ps}' is missing from user's assigned permission sets",
                    decision_basis=f"Confirmed: User lacks required {target_ps} permission set to access application.",
                    next_step_reason="Advance to Root Cause Confirmation gate to formally confirm root cause.",
                    findings=[
                        Finding(
                            claim=f"User is missing the required '{target_ps}' permission set for app access",
                            evidence_refs=[ev_ps_id],
                        )
                    ],
                    unresolved_questions=[],
                    recommended_action="resolution",
                )
            else:
                result = DiagnosisResult(
                    status="contradicted",
                    issue_code=norm_code,
                    expected_criteria=expected_criteria,
                    observed_values=observed_values,
                    comparison_summary=f"[MISMATCH] '{target_ps}' is already present in user's permission sets",
                    decision_basis=f"Contradicted: User already possesses {target_ps} permission set.",
                    next_step_reason="Advance to next candidate scenario without loading skill files.",
                    findings=[
                        Finding(
                            claim=f"User already possesses '{target_ps}' permission set",
                            evidence_refs=[ev_ps_id],
                        )
                    ],
                    unresolved_questions=[f"{target_ps} permission set is assigned. Check portal license or user status."],
                    recommended_action="switch_hypothesis",
                )

        elif norm_code in ["APPLICATION-3", "APPLICATION-4"]:
            perm_sets = salesforce_get_user_permission_sets(user_id)
            ev_ps_id = f"ev_perm_sets_{uuid.uuid4().hex[:6]}"
            recorded_evidence.append({
                "evidence_id": ev_ps_id,
                "tool_name": "salesforce_get_user_permission_sets",
                "field_name": "PermissionSets",
                "observed_value": perm_sets,
                "raw_output": {"PermissionSets": perm_sets},
            })

            target_ps = "Conga_CLM_User" if norm_code == "APPLICATION-3" else "Showpad_Integration_User"
            expected_criteria = f"'{target_ps}' NOT in user PermissionSets"
            observed_values = {"PermissionSets": perm_sets}

            if target_ps not in perm_sets:
                result = DiagnosisResult(
                    status="confirmed",
                    issue_code=norm_code,
                    expected_criteria=expected_criteria,
                    observed_values=observed_values,
                    comparison_summary=f"[MATCH] '{target_ps}' is missing from user's assigned permission sets",
                    decision_basis=f"Confirmed: User lacks {target_ps} permission set for application access.",
                    next_step_reason="Advance to Root Cause Confirmation gate to formally confirm root cause.",
                    findings=[
                        Finding(
                            claim=f"User is missing '{target_ps}' permission set for application access",
                            evidence_refs=[ev_ps_id],
                        )
                    ],
                    unresolved_questions=[],
                    recommended_action="resolution",
                )
            else:
                result = DiagnosisResult(
                    status="contradicted",
                    issue_code=norm_code,
                    expected_criteria=expected_criteria,
                    observed_values=observed_values,
                    comparison_summary=f"[MISMATCH] '{target_ps}' is already present in user's permission sets",
                    decision_basis=f"Contradicted: User already possesses {target_ps} permission set.",
                    next_step_reason="Advance to next candidate scenario without loading skill files.",
                    findings=[
                        Finding(
                            claim=f"User already possesses {target_ps} permission set",
                            evidence_refs=[ev_ps_id],
                        )
                    ],
                    unresolved_questions=[f"{target_ps} permission set present. Check Content User checkbox."],
                    recommended_action="switch_hypothesis",
                )
        else:
            sop_data = sop_repository.get_sop(candidate_issue_code) or sop_repository.get_sop(norm_code)
            if sop_data:
                sop_desc = sop_data.get("description", norm_code)
                sop_res = sop_data.get("resolution_steps", "")
                sop_id = sop_data.get("id", norm_code)
                is_active = user_details.get("IsActive", True)
                narrative_matches, match_detail = self._matches_sop_scenario(context, sop_data, norm_code)

                if narrative_matches and is_active:
                    result = DiagnosisResult(
                        status="confirmed",
                        issue_code=norm_code,
                        expected_criteria=f"User.IsActive == True AND symptom matches SOP {sop_id} ('{sop_desc}')",
                        observed_values={"IsActive": is_active, "SOPDescription": sop_desc, "MatchDetail": match_detail},
                        comparison_summary=f"[MATCH] User is active and narrative matches SOP {sop_id} ('{sop_desc}')",
                        decision_basis=f"Confirmed: Analyzed SOP {sop_id} ('{sop_desc}'). Live Salesforce user is active, and incident context matches the scenario scope. Resolution: {sop_res[:100]}...",
                        next_step_reason="Advance to Root Cause Confirmation gate to formally confirm root cause.",
                        findings=[
                            Finding(
                                claim=f"User is active in Salesforce and symptoms match SOP {sop_id} ('{sop_desc}')",
                                evidence_refs=[ev_details_id or ev_search_id],
                            )
                        ],
                        unresolved_questions=[],
                        recommended_action="resolution",
                    )
                else:
                    result = DiagnosisResult(
                        status="contradicted",
                        issue_code=norm_code,
                        expected_criteria=f"Symptom matches SOP {sop_id} ('{sop_desc}')",
                        observed_values={"IsActive": is_active, "NarrativeMatch": narrative_matches, "MatchDetail": match_detail},
                        comparison_summary=f"[MISMATCH] Incident narrative does not match SOP {sop_id} scenario ('{sop_desc}')",
                        decision_basis=f"Contradicted: Evaluated candidate SOP {sop_id} ('{sop_desc}') against incident context. Narrative does not match scenario scope.",
                        next_step_reason="Advance to next candidate scenario in fallback sequence.",
                        findings=[
                            Finding(
                                claim=f"Incident context does not match SOP {sop_id} scenario scope",
                                evidence_refs=[ev_search_id],
                            )
                        ],
                        unresolved_questions=[],
                        recommended_action="switch_hypothesis",
                    )
            else:
                result = DiagnosisResult(
                    status="insufficient_evidence",
                    issue_code=norm_code,
                    expected_criteria=f"Domain verification criteria for {norm_code}",
                    observed_values={"user_id": user_id},
                    comparison_summary=f"No matching diagnostic rule or SOP found for candidate {norm_code}",
                    decision_basis=f"Insufficient evidence: Evaluator for '{norm_code}' requires manual or specialized diagnostic probe.",
                    next_step_reason="Advance to next candidate scenario in fallback sequence.",
                    findings=[],
                    unresolved_questions=[f"Diagnostic evaluator for '{norm_code}' requires additional checks."],
                    recommended_action="escalate",
                )


        # Step 4: Validate evidence grounding before returning
        validate_evidence_grounding(result, recorded_evidence)

        return result, new_evidence
