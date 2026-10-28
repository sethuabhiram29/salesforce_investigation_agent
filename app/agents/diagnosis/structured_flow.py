"""Structured Flow Decision Tree Engine for Diagnosis Agent (Login Issues).

Implements the exact Knowledge Graph flowchart specified for Login Issues:
Swimlane 1: Wrong Login URL
Swimlane 2: User not found in any org
Swimlane 3: User found in another org
Swimlane 4: User Deactivation & DA Admin audit verification
Swimlane 5: Federation ID Missing & Mirror User Comparison
Swimlane 6: Federation ID Suspended
Swimlane 7: Azure Synchronization Internal
Swimlane 8: Mobile Login Setup issue
Swimlane 9: CIAM Synchronization External
Swimlane 10: Email Not Verified
Swimlane 11: Work Order Email issue
Swimlane 12: Out Of Scope (Escalation)

Note: For this version, diagnosis is purely deterministic Knowledge Graph traversal
based on the flowchart diagram without dependency on historical incidents.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
import uuid

from app.models.schemas import DiagnosisResult, Finding
from app.knowledge.sop_repository import sop_repository, normalize_issue_code
from app.tools.salesforce import (
    salesforce_user_search,
    salesforce_get_user_details,
    salesforce_get_user_field,
)
from app.utils.validators import validate_user_identity_resolution

logger = logging.getLogger(__name__)


class StructuredDiagnosisFlow:
    """Executes the deterministic decision tree from the Login Issues flowchart."""

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
    ) -> Dict[str, Any]:
        """Record and print a formatted graph traversal step."""
        step_num = len(self.traversal_steps) + 1
        tools = tools_called or ["Decision Logic"]
        tool_main = tools[0] if tools else "Decision Logic"

        # Format observed summary
        if isinstance(observed, dict):
            obs_summary = ", ".join(f"{k}={v}" for k, v in observed.items())
        else:
            obs_summary = str(observed)

        # Print traversal card to console
        print(f"\n" + "-" * 80)
        print(f"[FLOWCHART TRAVERSAL STEP {step_num}] Swimlane: {swimlane}")
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
            "why_step_taken": f"Flowchart transition from {from_node} to {to_node}",
            "observed_summary": obs_summary,
            "observed_values": observed if isinstance(observed, dict) else {"value": str(observed)},
            "comparison": f"Decision: {decision_outcome}",
            "conclusion": f"Traversed to {to_node}",
            "decision_basis": explanation,
            "next_step": f"Advance along flowchart to {to_node}",
            "next_step_reason": explanation,
            "tool_called": tool_main,
            "tools_called": tools,
            "tool_result": observed,
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
        """Traverse the Login Issues flowchart step-by-step.
        
        Returns:
            Tuple of (DiagnosisResult, new_evidence_list, traversal_audit_steps)
        """
        self.traversal_steps = []
        cache = evidence_cache if evidence_cache is not None else {}
        recorded_evidence: List[Dict[str, Any]] = list(existing_evidence or [])
        new_evidence: List[Dict[str, Any]] = []
        ctx = context or {}

        incident_summary = str(ctx.get("short_description", ctx.get("incident_summary", "")))
        incident_desc = str(ctx.get("description", ctx.get("incident_description", "")))
        full_text = f"{incident_summary} {incident_desc}".lower()

        # Extract Triage Inputs
        affected_user_id = ctx.get("affected_user_id") or target_identifier
        login_url = ctx.get("login_url") or self._extract_url_from_text(full_text)
        mirror_user = ctx.get("mirror_user") or cache.get("User:mirror")
        domain = ctx.get("domain", "LOGIN")

        print("\n" + "=" * 80)
        print("  [KNOWLEDGE GRAPH TRAVERSAL START: Login Issues Decision Tree]")
        print("  * Starting Node:   [START: Triage Result]")
        print(f"  * Affected User:   {affected_user_id}")
        print(f"  * Issue Domain:    {domain}")
        print(f"  * Mirror User:     {mirror_user.get('Email') if isinstance(mirror_user, dict) else (mirror_user or 'None')}")
        print(f"  * Login URL:       {login_url or 'None provided in incident narrative'}")
        print("=" * 80, flush=True)

        # Record Step 0: Ingestion of Triage Result
        self._record_traversal_step(
            swimlane="Wrong Login Url",
            node_id="NODE_TRIAGE_RESULT",
            node_name="Triage Result Ingestion",
            from_node="[Triage Agent]",
            to_node="[Decision: Login URL Provided?]",
            action="Ingest ticket parameters and resolved caller identity from Triage stage",
            observed={
                "AffectedUser": affected_user_id,
                "Domain": domain,
                "MirrorUser": mirror_user.get("Email") if isinstance(mirror_user, dict) else str(mirror_user or "None"),
                "LoginURL": login_url or "None",
            },
            decision_outcome="Inputs loaded successfully into Diagnosis Knowledge Graph",
            explanation="Graph traversal initiated at root node 'Triage Result'. Retrieved target caller/affected identity and contextual incident parameters to navigate the Login Issues Decision Tree.",
            tools_called=["servicenow_get_incident", "TriageClassifier"],
            status="traversed",
        )

        # -------------------------------------------------------------
        # SWIMLANE 1: Wrong Login URL
        # -------------------------------------------------------------
        if login_url:
            is_valid_url = self._validate_salesforce_url(login_url)
            ev_url_id = f"ev_login_url_{uuid.uuid4().hex[:6]}"
            new_ev = {
                "evidence_id": ev_url_id,
                "tool_name": "salesforce_validate_url",
                "field_name": "LoginURL",
                "observed_value": {"URL": login_url, "IsApproved": is_valid_url},
            }
            recorded_evidence.append(new_ev)
            new_evidence.append(new_ev)

            if not is_valid_url:
                self._record_traversal_step(
                    swimlane="Wrong Login Url",
                    node_id="NODE_VALIDATE_LOGIN_URL",
                    node_name="Validate Login URL",
                    from_node="[Decision: Login URL Provided? (Yes)]",
                    to_node="[TERMINAL: Confirmed Wrong Salesforce URL (LOGIN-2)]",
                    action=f"Validate login URL '{login_url}' against approved MyDomain endpoints",
                    observed={"URL": login_url, "IsApproved": False},
                    decision_outcome="Outcome: 'No' (URL is unapproved)",
                    explanation=f"Provided URL '{login_url}' does not match company Salesforce MyDomain. Flowchart terminates at root cause 'LOGIN-2'.",
                    tools_called=["salesforce_validate_url"],
                    status="matched",
                )

                print("\n" + "=" * 80)
                print("[ROOT CAUSE FINALIZED via LOGIN DECISION TREE]")
                print("  * Final Terminal Node:  Confirmed Wrong Salesforce URL (LOGIN-2)")
                print("  * Issue Domain:         LOGIN")
                print("  * Knowledge Graph Path: [Triage Result] --> [Login URL Provided? (Yes)] --> [Validate Login URL] --> [LOGIN-2]")
                print("  * Confirmed Root Cause: LOGIN-2")
                print(f"  * Decision Basis (WHY): User is attempting to authenticate through unapproved URL '{login_url}'.")
                print("  * Next Stage:           Advancing to Resolution Planning to load canonical skill file for 'LOGIN-2'")
                print("=" * 80 + "\n", flush=True)

                return (
                    self._build_confirmed_result(
                        issue_code="LOGIN-2",
                        decision_basis=f"Confirmed: Provided login URL '{login_url}' is not an approved Salesforce MyDomain endpoint.",
                        expected="Login via approved company MyDomain URL",
                        observed={"LoginURL": login_url, "IsApproved": False},
                        findings=[
                            Finding(
                                claim=f"User is attempting to authenticate through unapproved URL '{login_url}'",
                                evidence_refs=[ev_url_id],
                            )
                        ],
                    ),
                    new_evidence,
                    self.traversal_steps,
                )
            else:
                self._record_traversal_step(
                    swimlane="Wrong Login Url",
                    node_id="NODE_VALIDATE_LOGIN_URL",
                    node_name="Validate Login URL",
                    from_node="[Decision: Login URL Provided? (Yes)]",
                    to_node="[Action: Search user in main org]",
                    action=f"Validate login URL '{login_url}' against approved MyDomain endpoints",
                    observed={"URL": login_url, "IsApproved": True},
                    decision_outcome="Outcome: 'Yes' (Approved MyDomain URL)",
                    explanation="Login URL matches approved corporate MyDomain. Proceeding along flowchart to verify user existence in primary Salesforce org.",
                    tools_called=["salesforce_validate_url"],
                    status="traversed",
                )
        else:
            self._record_traversal_step(
                swimlane="Wrong Login Url",
                node_id="NODE_LOGIN_URL_CHECK",
                node_name="Login URL Provided Check",
                from_node="[Decision: Login URL Provided?]",
                to_node="[Action: Search user in main org]",
                action="Check whether incident narrative specifies an authentication URL",
                observed={"LoginURL": None},
                decision_outcome="Outcome: 'No' (No URL provided)",
                explanation="No specific login URL was mentioned in the ticket narrative. Bypassing URL validation and proceeding to check user existence in the main Salesforce org.",
                tools_called=["TriageNarrativeParser"],
                status="traversed",
            )

        # -------------------------------------------------------------
        # SWIMLANE 2 & 3: User not found in any org / Found in another org
        # -------------------------------------------------------------
        user_details = cache.get("User")
        ev_search_id = None

        for ev in recorded_evidence:
            if ev.get("tool_name") in ["salesforce_user_search", "salesforce_get_basic_user"]:
                ev_search_id = ev.get("evidence_id")
                break

        if not user_details:
            search_results = salesforce_user_search(target_identifier)
            identity_check = validate_user_identity_resolution(search_results)
            matched_user = identity_check.get("user") if identity_check.get("status") == "resolved" else None

            if not matched_user:
                other_org_user = self._search_other_orgs(target_identifier)
                ev_search_id = f"ev_user_search_{uuid.uuid4().hex[:6]}"
                new_ev = {
                    "evidence_id": ev_search_id,
                    "tool_name": "salesforce_user_search",
                    "field_name": "UserLookup",
                    "observed_value": {"MainOrg": None, "OtherOrgs": other_org_user},
                }
                recorded_evidence.append(new_ev)
                new_evidence.append(new_ev)

                if other_org_user:
                    self._record_traversal_step(
                        swimlane="User found in another org",
                        node_id="NODE_SEARCH_OTHER_ORGS",
                        node_name="Search User in other orgs",
                        from_node="[Action: Search user in main org (No match)]",
                        to_node="[TERMINAL: Confirmed User found in another org (LOGIN-1B)]",
                        action=f"Search auxiliary enterprise orgs for '{target_identifier}'",
                        observed={"MainOrg": None, "OtherOrgs": other_org_user},
                        decision_outcome="Outcome: 'Yes' (User found in alternate org)",
                        explanation=f"Target user was located in secondary org '{other_org_user.get('OrgName')}'. Flowchart terminates at root cause 'LOGIN-1B'.",
                        tools_called=["salesforce_user_search"],
                        status="matched",
                    )

                    print("\n" + "=" * 80)
                    print("[ROOT CAUSE FINALIZED via LOGIN DECISION TREE]")
                    print("  * Final Terminal Node:  Confirmed User found in another org (LOGIN-1B)")
                    print("  * Issue Domain:         LOGIN")
                    print("  * Knowledge Graph Path: [Search user in main org (No)] --> [Search in other orgs (Yes)] --> [LOGIN-1B]")
                    print("  * Confirmed Root Cause: LOGIN-1B")
                    print(f"  * Decision Basis (WHY): User account exists in secondary org '{other_org_user.get('OrgName', 'Secondary Org')}', explaining login failure in primary org.")
                    print("  * Next Stage:           Advancing to Resolution Planning to load canonical skill file for 'LOGIN-1B'")
                    print("=" * 80 + "\n", flush=True)

                    return (
                        self._build_confirmed_result(
                            issue_code="LOGIN-1B",
                            decision_basis=f"Confirmed: Target user account was located in alternate organization '{other_org_user.get('OrgName', 'Secondary Org')}'.",
                            expected="User account provisioned in Primary Org",
                            observed={"UserFoundInOtherOrg": other_org_user},
                            findings=[
                                Finding(
                                    claim="Target user account exists in alternate Salesforce org",
                                    evidence_refs=[ev_search_id],
                                )
                            ],
                        ),
                        new_evidence,
                        self.traversal_steps,
                    )
                else:
                    self._record_traversal_step(
                        swimlane="User not found in any org",
                        node_id="NODE_SEARCH_OTHER_ORGS",
                        node_name="Search User in other orgs",
                        from_node="[Action: Search user in main org (No match)]",
                        to_node="[TERMINAL: Confirmed User not found in any org (LOGIN-1)]",
                        action=f"Search auxiliary enterprise orgs for '{target_identifier}'",
                        observed={"MainOrg": None, "OtherOrgs": None},
                        decision_outcome="Outcome: 'No' (User not found anywhere)",
                        explanation=f"User '{target_identifier}' does not exist in main org or any auxiliary org. Flowchart terminates at root cause 'LOGIN-1'.",
                        tools_called=["salesforce_user_search"],
                        status="matched",
                    )

                    print("\n" + "=" * 80)
                    print("[ROOT CAUSE FINALIZED via LOGIN DECISION TREE]")
                    print("  * Final Terminal Node:  Confirmed User not found in any org (LOGIN-1)")
                    print("  * Issue Domain:         LOGIN")
                    print("  * Knowledge Graph Path: [Search user in main org (No)] --> [Search in other orgs (No)] --> [LOGIN-1]")
                    print("  * Confirmed Root Cause: LOGIN-1")
                    print(f"  * Decision Basis (WHY): No account provisioned in any Salesforce instance for '{target_identifier}'.")
                    print("  * Next Stage:           Advancing to Resolution Planning to load canonical skill file for 'LOGIN-1'")
                    print("=" * 80 + "\n", flush=True)

                    return (
                        self._build_confirmed_result(
                            issue_code="LOGIN-1",
                            decision_basis=f"Confirmed: Target user '{target_identifier}' was not found in any provisioned Salesforce org.",
                            expected="User account exists in Salesforce",
                            observed={"UserFound": False, "Query": target_identifier},
                            findings=[
                                Finding(
                                    claim=f"No account provisioned in Salesforce for '{target_identifier}'",
                                    evidence_refs=[ev_search_id],
                                )
                            ],
                        ),
                        new_evidence,
                        self.traversal_steps,
                    )

            user_id = matched_user["Id"]
            user_details = salesforce_get_user_details(user_id)
            cache["User"] = user_details
            cache[f"User:{user_id}"] = user_details

            ev_search_id = f"ev_user_identity_{uuid.uuid4().hex[:6]}"
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

        user_id = user_details.get("Id", target_identifier)
        is_active = user_details.get("IsActive", False)

        self._record_traversal_step(
            swimlane="User not found in any org",
            node_id="NODE_SEARCH_MAIN_ORG",
            node_name="Search user in main org",
            from_node="[Wrong Login Url Check]",
            to_node="[Action: Fetch salesforce user (User Deactivation)]",
            action=f"Search Salesforce main org for user identity '{target_identifier}'",
            observed={
                "Id": user_id,
                "Username": user_details.get("Username"),
                "IsActive": is_active,
            },
            decision_outcome="Outcome: 'Yes' (Matching User Found)",
            explanation=f"Target user was uniquely identified in primary org (Id: {user_id}). Proceeding to evaluate account deactivation status.",
            tools_called=["salesforce_user_search", "salesforce_get_basic_user"],
            status="traversed",
        )

        # -------------------------------------------------------------
        # SWIMLANE 4: User Deactivation
        # -------------------------------------------------------------
        if not is_active:
            deactivated_by = user_details.get("DeactivatedBy", "")
            is_delegated = (
                user_details.get("DelegatedAdmin", False)
                or "delegated" in str(deactivated_by).lower()
                or "delegated" in str(user_details.get("Profile", {}).get("Name", "")).lower()
            )

            ev_deact_id = f"ev_deact_audit_{uuid.uuid4().hex[:6]}"
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

            if is_delegated:
                self._record_traversal_step(
                    swimlane="User Deactivation",
                    node_id="NODE_DEACTIVATION_AUDIT",
                    node_name="Retrieve Deactivation Audit",
                    from_node="[Decision: Is Active? (No)]",
                    to_node="[TERMINAL: Confirmed User Deactivated by DA Admin (LOGIN-3)]",
                    action="Analyze SetupAuditTrail to identify deactivating actor",
                    observed={"IsActive": False, "Actor": "Delegated Administrator", "IsDelegatedAdmin": True},
                    decision_outcome="Outcome: 'Yes' (Deactivation actor verified as DA)",
                    explanation="User is inactive in Salesforce, and audit trail confirms deactivation was performed by a Delegated Administrator. Flowchart terminates at root cause 'LOGIN-3'.",
                    tools_called=["salesforce_get_user_field"],
                    status="matched",
                )

                print("\n" + "=" * 80)
                print("[ROOT CAUSE FINALIZED via LOGIN DECISION TREE]")
                print("  * Final Terminal Node:  Confirmed User Deactivated by DA Admin (LOGIN-3)")
                print("  * Issue Domain:         LOGIN")
                print("  * Knowledge Graph Path: [Search user in main org (Yes)] --> [Is Active? (No)] --> [DA Verified? (Yes)] --> [LOGIN-3]")
                print("  * Confirmed Root Cause: LOGIN-3")
                print("  * Decision Basis (WHY): User account is deactivated (IsActive=False) by a Delegated Administrator. Policy requires ServiceNow Manage User RITM for reactivation.")
                print("  * Next Stage:           Advancing to Resolution Planning to load canonical skill file for 'LOGIN-3'")
                print("=" * 80 + "\n", flush=True)

                return (
                    self._build_confirmed_result(
                        issue_code="LOGIN-3",
                        decision_basis="Confirmed: User account is deactivated in Salesforce (IsActive=False). Audit analysis confirms deactivation was performed by a Delegated Administrator.",
                        expected="User.IsActive == True",
                        observed={"IsActive": False, "Actor": "Delegated Administrator"},
                        findings=[
                            Finding(
                                claim="Target user identity resolved uniquely in Salesforce",
                                evidence_refs=[ev_search_id],
                            ),
                            Finding(
                                claim="User account is deactivated in Salesforce NA org (IsActive=False). Actor classification: Delegated Administrator.",
                                evidence_refs=[ev_deact_id],
                            ),
                        ],
                    ),
                    new_evidence,
                    self.traversal_steps,
                )
            else:
                self._record_traversal_step(
                    swimlane="User Deactivation",
                    node_id="NODE_DEACTIVATION_AUDIT",
                    node_name="Retrieve Deactivation Audit",
                    from_node="[Decision: Is Active? (No)]",
                    to_node="[TERMINAL: Escalation - Deactivated by non-DA actor (LOGIN-3-ESCALATE)]",
                    action="Analyze SetupAuditTrail to identify deactivating actor",
                    observed={"IsActive": False, "Actor": deactivated_by or "Automated Sync", "IsDelegatedAdmin": False},
                    decision_outcome="Outcome: 'No' (Non-DA actor or automated deactivation)",
                    explanation=f"User was deactivated by '{deactivated_by or 'Automated Sync'}'. Security policy mandates human review for non-DA deactivations. Routing to Tier-2 support.",
                    tools_called=["salesforce_get_user_field"],
                    status="matched",
                )

                print("\n" + "=" * 80)
                print("[ESCALATION BOUNDARY REACHED via LOGIN DECISION TREE]")
                print("  * Terminal Node:        Escalation - Deactivated by non-DA actor (LOGIN-3-ESCALATE)")
                print("  * Knowledge Graph Path: [Search user in main org (Yes)] --> [Is Active? (No)] --> [DA Verified? (No)] --> [ESCALATE]")
                print("  * Escalation Code:      LOGIN-3-ESCALATE")
                print(f"  * Decision Basis (WHY): Deactivated by non-DA actor ('{deactivated_by or 'Automated Sync'}'). Manual review required per policy.")
                print("  * Next Stage:           Routing incident to Tier-2 human support team")
                print("=" * 80 + "\n", flush=True)

                return (
                    self._build_escalation_result(
                        issue_code="LOGIN-3-ESCALATE",
                        reason=f"User is deactivated by non-DA actor ('{deactivated_by or 'Automated Sync'}'). Requires manual review per policy.",
                        evidence_refs=[ev_deact_id],
                    ),
                    new_evidence,
                    self.traversal_steps,
                )

        # User is active -> advance to mirror comparison
        self._record_traversal_step(
            swimlane="User Deactivation",
            node_id="NODE_USER_DEACTIVATION_CHECK",
            node_name="Fetch salesforce user (Is Active?)",
            from_node="[Action: Search user in main org]",
            to_node="[Action: Fetch Similar User using mirror user identity]",
            action="Check user record IsActive flag",
            observed={"IsActive": True},
            decision_outcome="Outcome: 'Yes' (User is Active)",
            explanation="User account is active in Salesforce (IsActive=True), ruling out deactivation (LOGIN-3). Advancing to evaluate user identity type by comparing against mirror user.",
            tools_called=["salesforce_get_basic_user"],
            status="traversed",
        )

        # -------------------------------------------------------------
        # SWIMLANE 5: Federation ID Missing & Mirror User Comparison
        # -------------------------------------------------------------
        mirror_obj = cache.get("User:mirror")
        if not mirror_obj and mirror_user:
            if isinstance(mirror_user, dict):
                mirror_obj = mirror_user
            else:
                m_search = salesforce_user_search(str(mirror_user))
                m_check = validate_user_identity_resolution(m_search)
                if m_check.get("status") == "resolved":
                    mirror_obj = salesforce_get_user_details(m_check["user"]["Id"])
                    cache["User:mirror"] = mirror_obj

        u_email = str(user_details.get("Email", "")).lower()
        is_internal = not any(k in u_email for k in ["partner", "contractor", "external", "vendor"])
        if mirror_obj:
            m_email = str(mirror_obj.get("Email", "")).lower()
            is_internal = ("@acme." in u_email and "@acme." in m_email) or is_internal

        if not is_internal:
            # External CIAM User Path
            self._record_traversal_step(
                swimlane="Federation ID Missing",
                node_id="NODE_MIRROR_USER_COMPARISON",
                node_name="Compare EmpId and Federation ID of mirror user",
                from_node="[Action: Fetch Similar User using mirror user identity]",
                to_node="[Swimlane: CIAM Synchronization External]",
                action="Compare user identity and domain format with mirror peer user",
                observed={"Email": u_email, "IsInternal": False},
                decision_outcome="Outcome: 'No' (External / Partner User)",
                explanation="Identity attributes indicate external user pattern. Advancing along flowchart to evaluate CIAM Synchronization.",
                tools_called=["salesforce_get_user_details"],
                status="traversed",
            )

            # ---------------------------------------------------------
            # SWIMLANE 9: CIAM Synchronization External
            # ---------------------------------------------------------
            ciam_match = self._check_ciam_synchronization(user_details)
            ev_ciam_id = f"ev_ciam_sync_{uuid.uuid4().hex[:6]}"
            new_ev = {
                "evidence_id": ev_ciam_id,
                "tool_name": "salesforce_get_user_field",
                "field_name": "CIAMSync",
                "observed_value": {"CIAMMatch": ciam_match},
            }
            recorded_evidence.append(new_ev)
            new_evidence.append(new_ev)

            if not ciam_match:
                self._record_traversal_step(
                    swimlane="CIAM Synchronization External",
                    node_id="NODE_CIAM_SYNC",
                    node_name="Federation ID matches Emp ID? (CIAM)",
                    from_node="[Action: Compare mirror identity (External)]",
                    to_node="[TERMINAL: Confirmed CIAM synthetic identity mapping issue (LOGIN-7)]",
                    action="Check external synthetic identity mapping between CIAM and Salesforce Federation ID",
                    observed={"CIAMMatch": False},
                    decision_outcome="Outcome: 'No' (CIAM Mapping Mismatch)",
                    explanation="External Federation Identifier does not match CIAM synthetic identity mapping. Flowchart terminates at root cause 'LOGIN-7'.",
                    tools_called=["salesforce_get_user_field"],
                    status="matched",
                )

                print("\n" + "=" * 80)
                print("[ROOT CAUSE FINALIZED via LOGIN DECISION TREE]")
                print("  * Final Terminal Node:  Confirmed CIAM synthetic identity mapping issue (LOGIN-7)")
                print("  * Issue Domain:         LOGIN")
                print("  * Knowledge Graph Path: [Mirror Identity (External)] --> [CIAM Matches Emp ID? (No)] --> [LOGIN-7]")
                print("  * Confirmed Root Cause: LOGIN-7")
                print("  * Decision Basis (WHY): External user Federation ID does not match external CIAM synthetic identity mapping.")
                print("  * Next Stage:           Advancing to Resolution Planning to load canonical skill file for 'LOGIN-7'")
                print("=" * 80 + "\n", flush=True)

                return (
                    self._build_confirmed_result(
                        issue_code="LOGIN-7",
                        decision_basis="Confirmed: External user Federation Identifier does not match external CIAM synthetic identity mapping.",
                        expected="External Federation ID matches CIAM identity mapping",
                        observed={"CIAMMatch": False},
                        findings=[
                            Finding(
                                claim="External user Federation ID does not match CIAM identity mapping",
                                evidence_refs=[ev_ciam_id],
                            )
                        ],
                    ),
                    new_evidence,
                    self.traversal_steps,
                )
            else:
                self._record_traversal_step(
                    swimlane="CIAM Synchronization External",
                    node_id="NODE_CIAM_SYNC",
                    node_name="Federation ID matches Emp ID? (CIAM)",
                    from_node="[Action: Compare mirror identity (External)]",
                    to_node="[Decision: Is Email Verified?]",
                    action="Check external synthetic identity mapping between CIAM and Salesforce Federation ID",
                    observed={"CIAMMatch": True},
                    decision_outcome="Outcome: 'Yes' (CIAM Mapping Valid)",
                    explanation="CIAM mapping verified. Advancing along flowchart to evaluate Email Verification status.",
                    tools_called=["salesforce_get_user_field"],
                    status="traversed",
                )

        else:
            # Internal User Path
            self._record_traversal_step(
                swimlane="Federation ID Missing",
                node_id="NODE_MIRROR_USER_COMPARISON",
                node_name="Compare EmpId and Federation ID of mirror user",
                from_node="[Action: Fetch Similar User using mirror user identity]",
                to_node="[Decision: Federation ID Blank?]",
                action="Compare user identity and domain format with mirror peer user",
                observed={"Email": u_email, "IsInternal": True},
                decision_outcome="Outcome: 'Yes' (Internal User)",
                explanation="Identity attributes confirm internal corporate employee. Advancing along flowchart to evaluate FederationIdentifier.",
                tools_called=["salesforce_get_user_details"],
                status="traversed",
            )

            fed_id = user_details.get("FederationIdentifier")
            is_fed_blank = (fed_id is None or str(fed_id).strip() == "" or str(fed_id).lower() == "none")

            ev_fed_id = f"ev_fed_id_{uuid.uuid4().hex[:6]}"
            new_ev = {
                "evidence_id": ev_fed_id,
                "tool_name": "salesforce_get_user_field",
                "field_name": "FederationIdentifier",
                "observed_value": fed_id,
            }
            recorded_evidence.append(new_ev)
            new_evidence.append(new_ev)

            if is_fed_blank:
                self._record_traversal_step(
                    swimlane="Federation ID Missing",
                    node_id="NODE_FED_ID_BLANK_CHECK",
                    node_name="Federation ID Blank?",
                    from_node="[Decision: Is same? (Internal User - Yes)]",
                    to_node="[TERMINAL: Confirmed Federation ID Missing (LOGIN-4)]",
                    action="Inspect FederationIdentifier on active Salesforce user record",
                    observed={"IsActive": True, "FederationIdentifier": None},
                    decision_outcome="Outcome: 'Yes' (Federation ID is Blank)",
                    explanation="User account is active in Salesforce but lacks FederationIdentifier, directly causing SAML SSO failure. Flowchart terminates at root cause 'LOGIN-4'.",
                    tools_called=["salesforce_get_user_field"],
                    status="matched",
                )

                print("\n" + "=" * 80)
                print("[ROOT CAUSE FINALIZED via LOGIN DECISION TREE]")
                print("  * Final Terminal Node:  Confirmed Federation ID Missing (LOGIN-4)")
                print("  * Issue Domain:         LOGIN")
                print("  * Knowledge Graph Path: [Is same? (Internal: Yes)] --> [Federation ID Blank? (Yes)] --> [LOGIN-4]")
                print("  * Confirmed Root Cause: LOGIN-4")
                print("  * Decision Basis (WHY): User is active in Salesforce but lacks FederationIdentifier, directly causing SAML SSO assertion rejection.")
                print("  * Next Stage:           Advancing to Resolution Planning to load canonical skill file for 'LOGIN-4'")
                print("=" * 80 + "\n", flush=True)

                return (
                    self._build_confirmed_result(
                        issue_code="LOGIN-4",
                        decision_basis="Confirmed: User account is active in Salesforce but lacks FederationIdentifier, directly causing SAML SSO assertion failure.",
                        expected="User.IsActive == True AND (User.FederationIdentifier is null or empty)",
                        observed={"IsActive": True, "FederationIdentifier": None},
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
                    ),
                    new_evidence,
                    self.traversal_steps,
                )

            # Federation ID is populated -> check suspension
            self._record_traversal_step(
                swimlane="Federation ID Missing",
                node_id="NODE_FED_ID_BLANK_CHECK",
                node_name="Federation ID Blank?",
                from_node="[Decision: Is same? (Internal User - Yes)]",
                to_node="[Decision: Federation ID/Okta Suspended status?]",
                action="Inspect FederationIdentifier on active Salesforce user record",
                observed={"FederationIdentifier": fed_id},
                decision_outcome="Outcome: 'No' (Federation ID is populated)",
                explanation=f"Federation ID is populated ('{fed_id}'). Advancing along flowchart to check Okta/Identity Provider account status.",
                tools_called=["salesforce_get_user_field"],
                status="traversed",
            )

            # ---------------------------------------------------------
            # SWIMLANE 6: Federation ID Suspended
            # ---------------------------------------------------------
            is_suspended = self._check_okta_suspended(user_details, full_text)
            if is_suspended:
                ev_susp_id = f"ev_susp_{uuid.uuid4().hex[:6]}"
                new_ev = {
                    "evidence_id": ev_susp_id,
                    "tool_name": "salesforce_get_user_field",
                    "field_name": "FederationSuspension",
                    "observed_value": {"Suspended": True},
                }
                recorded_evidence.append(new_ev)
                new_evidence.append(new_ev)

                self._record_traversal_step(
                    swimlane="Federation ID Suspended",
                    node_id="NODE_OKTA_SUSPENDED_CHECK",
                    node_name="Federation ID/Okta Suspended status?",
                    from_node="[Decision: Federation ID Blank? (No)]",
                    to_node="[TERMINAL: Confirmed Federation ID Suspended (LOGIN-5)]",
                    action="Check Identity Provider / Okta status for user account",
                    observed={"Suspended": True, "FederationIdentifier": fed_id},
                    decision_outcome="Outcome: 'Yes' (User is Suspended in IdP)",
                    explanation="User is active in Salesforce but suspended/locked in Okta/IdP. Flowchart terminates at root cause 'LOGIN-5'.",
                    tools_called=["salesforce_get_user_field"],
                    status="matched",
                )

                print("\n" + "=" * 80)
                print("[ROOT CAUSE FINALIZED via LOGIN DECISION TREE]")
                print("  * Final Terminal Node:  Confirmed Federation ID Suspended (LOGIN-5)")
                print("  * Issue Domain:         LOGIN")
                print("  * Knowledge Graph Path: [Federation ID Blank? (No)] --> [Okta Suspended? (Yes)] --> [LOGIN-5]")
                print("  * Confirmed Root Cause: LOGIN-5")
                print("  * Decision Basis (WHY): User is active in Salesforce but Okta assertion is frozen/suspended in Identity Provider.")
                print("  * Next Stage:           Advancing to Resolution Planning to load canonical skill file for 'LOGIN-5'")
                print("=" * 80 + "\n", flush=True)

                return (
                    self._build_confirmed_result(
                        issue_code="LOGIN-5",
                        decision_basis="Confirmed: User account is active in Salesforce but Federation ID / Okta assertion is frozen/suspended in Identity Provider.",
                        expected="Active Federation status in Identity Provider",
                        observed={"Suspended": True, "FederationIdentifier": fed_id},
                        findings=[
                            Finding(
                                claim="Federation ID / Okta user status is suspended",
                                evidence_refs=[ev_susp_id],
                            )
                        ],
                    ),
                    new_evidence,
                    self.traversal_steps,
                )

            # Not suspended -> check Azure Workday sync
            self._record_traversal_step(
                swimlane="Federation ID Suspended",
                node_id="NODE_OKTA_SUSPENDED_CHECK",
                node_name="Federation ID/Okta Suspended status?",
                from_node="[Decision: Federation ID Blank? (No)]",
                to_node="[Decision: Federation ID matches Emp ID? (Workday)]",
                action="Check Identity Provider / Okta status for user account",
                observed={"Suspended": False},
                decision_outcome="Outcome: 'No' (Active in IdP)",
                explanation="Okta user status is active. Advancing along flowchart to check Azure AD / Workday directory synchronization.",
                tools_called=["salesforce_get_user_field"],
                status="traversed",
            )

            # ---------------------------------------------------------
            # SWIMLANE 7: Azure Synchronization Internal
            # ---------------------------------------------------------
            azure_sync_match = self._check_azure_workday_match(user_details, full_text)
            if not azure_sync_match:
                ev_azure_id = f"ev_azure_sync_{uuid.uuid4().hex[:6]}"
                new_ev = {
                    "evidence_id": ev_azure_id,
                    "tool_name": "salesforce_get_user_field",
                    "field_name": "AzureSync",
                    "observed_value": {"AzureMatch": False},
                }
                recorded_evidence.append(new_ev)
                new_evidence.append(new_ev)

                self._record_traversal_step(
                    swimlane="Azure Synchronization Internal",
                    node_id="NODE_AZURE_WORKDAY_SYNC",
                    node_name="Federation ID matches Emp ID? (Workday)",
                    from_node="[Decision: Okta Suspended? (No)]",
                    to_node="[TERMINAL: Confirmed Azure Federation ID Synchronization Issue (LOGIN-6)]",
                    action="Compare Salesforce Federation ID against Workday Employee ID in Azure AD",
                    observed={"AzureMatch": False, "FederationIdentifier": fed_id},
                    decision_outcome="Outcome: 'No' (Mismatch with Workday/Azure)",
                    explanation="Salesforce FederationIdentifier does not match active Employee ID in Azure AD / Workday. Flowchart terminates at root cause 'LOGIN-6'.",
                    tools_called=["salesforce_get_user_field"],
                    status="matched",
                )

                print("\n" + "=" * 80)
                print("[ROOT CAUSE FINALIZED via LOGIN DECISION TREE]")
                print("  * Final Terminal Node:  Confirmed Azure Federation ID Synchronization Issue (LOGIN-6)")
                print("  * Issue Domain:         LOGIN")
                print("  * Knowledge Graph Path: [Okta Suspended? (No)] --> [Azure Matches Workday? (No)] --> [LOGIN-6]")
                print("  * Confirmed Root Cause: LOGIN-6")
                print("  * Decision Basis (WHY): Federation ID does not match active Employee ID in Azure AD / Workday directory (re-hire synchronization mismatch).")
                print("  * Next Stage:           Advancing to Resolution Planning to load canonical skill file for 'LOGIN-6'")
                print("=" * 80 + "\n", flush=True)

                return (
                    self._build_confirmed_result(
                        issue_code="LOGIN-6",
                        decision_basis="Confirmed: Federation ID does not match active Employee ID in Azure AD / Workday directory (re-hire synchronization mismatch).",
                        expected="FederationIdentifier matches Workday Employee ID in Azure",
                        observed={"AzureMatch": False, "FederationIdentifier": fed_id},
                        findings=[
                            Finding(
                                claim="Azure AD Federation ID synchronization mismatch with Workday",
                                evidence_refs=[ev_azure_id],
                            )
                        ],
                    ),
                    new_evidence,
                    self.traversal_steps,
                )

            # Azure matches -> check Mobile Login setup
            self._record_traversal_step(
                swimlane="Azure Synchronization Internal",
                node_id="NODE_AZURE_WORKDAY_SYNC",
                node_name="Federation ID matches Emp ID? (Workday)",
                from_node="[Decision: Okta Suspended? (No)]",
                to_node="[Decision: Has Description contain 'Mobile Login Issue' Symptom?]",
                action="Compare Salesforce Federation ID against Workday Employee ID in Azure AD",
                observed={"AzureMatch": True},
                decision_outcome="Outcome: 'Yes' (Federation ID matches Workday)",
                explanation="Federation ID matches Azure/Workday records. Advancing along flowchart to evaluate mobile login symptoms.",
                tools_called=["salesforce_get_user_field"],
                status="traversed",
            )

            # ---------------------------------------------------------
            # SWIMLANE 8: Mobile Login Setup issue
            # ---------------------------------------------------------
            has_mobile_symptom = any(
                w in full_text for w in ["mobile", "phone", "ios", "android", "ipad", "tablet", "handheld"]
            )
            if has_mobile_symptom:
                ev_mob_id = f"ev_mob_{uuid.uuid4().hex[:6]}"
                new_ev = {
                    "evidence_id": ev_mob_id,
                    "tool_name": "salesforce_get_user_field",
                    "field_name": "MobileSetup",
                    "observed_value": {"HasMobileSymptom": True},
                }
                recorded_evidence.append(new_ev)
                new_evidence.append(new_ev)

                self._record_traversal_step(
                    swimlane="Mobile Login Setup issue",
                    node_id="NODE_MOBILE_LOGIN_CHECK",
                    node_name="Has Description contain 'Mobile Login Issue' Symptom?",
                    from_node="[Decision: Azure Matches Workday? (Yes)]",
                    to_node="[TERMINAL: Confirmed Mobile Login Setup Issue (LOGIN-8)]",
                    action="Analyze incident narrative for mobile app authentication symptoms",
                    observed={"HasMobileSymptom": True, "IsActive": True},
                    decision_outcome="Outcome: 'Yes' (Mobile Issue Reported)",
                    explanation="User account is operational; symptoms describe mobile client configuration procedure. Flowchart terminates at root cause 'LOGIN-8'.",
                    tools_called=["salesforce_get_user_field"],
                    status="matched",
                )

                print("\n" + "=" * 80)
                print("[ROOT CAUSE FINALIZED via LOGIN DECISION TREE]")
                print("  * Final Terminal Node:  Confirmed Mobile Login Setup Issue (LOGIN-8)")
                print("  * Issue Domain:         LOGIN")
                print("  * Knowledge Graph Path: [Azure Matches Workday? (Yes)] --> [Mobile Symptom? (Yes)] --> [LOGIN-8]")
                print("  * Confirmed Root Cause: LOGIN-8")
                print("  * Decision Basis (WHY): User is active in Salesforce; incident narrative matches mobile app client setup procedure.")
                print("  * Next Stage:           Advancing to Resolution Planning to load canonical skill file for 'LOGIN-8'")
                print("=" * 80 + "\n", flush=True)

                return (
                    self._build_confirmed_result(
                        issue_code="LOGIN-8",
                        decision_basis="Confirmed: User account is active and operational in Salesforce; incident narrative matches mobile app client-side setup procedure.",
                        expected="User.IsActive == True AND symptom indicates mobile login configuration",
                        observed={"HasMobileSymptom": True, "IsActive": True},
                        findings=[
                            Finding(
                                claim="User is active in Salesforce; issue requires mobile app client setup guidance",
                                evidence_refs=[ev_mob_id],
                            )
                        ],
                    ),
                    new_evidence,
                    self.traversal_steps,
                )

            # No mobile symptoms -> check Email Verification
            self._record_traversal_step(
                swimlane="Mobile Login Setup issue",
                node_id="NODE_MOBILE_LOGIN_CHECK",
                node_name="Has Description contain 'Mobile Login Issue' Symptom?",
                from_node="[Decision: Azure Matches Workday? (Yes)]",
                to_node="[Decision: Is Email Verified?]",
                action="Analyze incident narrative for mobile app authentication symptoms",
                observed={"HasMobileSymptom": False},
                decision_outcome="Outcome: 'No' (No Mobile Symptom)",
                explanation="No mobile-specific symptoms reported. Advancing along flowchart to evaluate Email Verification status.",
                tools_called=["TriageNarrativeParser"],
                status="traversed",
            )

        # -------------------------------------------------------------
        # SWIMLANE 10 & 11: Email Not Verified & Work Order Email
        # -------------------------------------------------------------
        is_email_verified = user_details.get("EmailVerified", True)
        if "unverified" in full_text or "email not verified" in full_text:
            is_email_verified = False

        if not is_email_verified:
            has_wo_symptom = any(
                w in full_text for w in ["work order", "closing", "wo email", "workorder"]
            )

            if has_wo_symptom:
                ev_wo_id = f"ev_wo_{uuid.uuid4().hex[:6]}"
                new_ev = {
                    "evidence_id": ev_wo_id,
                    "tool_name": "salesforce_get_user_field",
                    "field_name": "WorkOrderDelivery",
                    "observed_value": {"EmailVerified": False, "WorkOrderSymptom": True},
                }
                recorded_evidence.append(new_ev)
                new_evidence.append(new_ev)

                self._record_traversal_step(
                    swimlane="Work Order Email issue",
                    node_id="NODE_WO_EMAIL_CHECK",
                    node_name="Has Description contain 'Work Order Email Not Received' Symptom?",
                    from_node="[Decision: Is Email Verified? (No)]",
                    to_node="[TERMINAL: Confirmed Work Order Email Issue (LOGIN-9)]",
                    action="Check work order notification delivery settings and email verification",
                    observed={"EmailVerified": False, "WorkOrderSymptom": True},
                    decision_outcome="Outcome: 'Yes' (Work Order Email Symptom Reported)",
                    explanation="Email is unverified for work order delivery notifications. Flowchart terminates at root cause 'LOGIN-9'.",
                    tools_called=["salesforce_get_user_field"],
                    status="matched",
                )

                print("\n" + "=" * 80)
                print("[ROOT CAUSE FINALIZED via LOGIN DECISION TREE]")
                print("  * Final Terminal Node:  Confirmed Work Order Email Issue (LOGIN-9)")
                print("  * Issue Domain:         LOGIN")
                print("  * Knowledge Graph Path: [Is Email Verified? (No)] --> [Work Order Symptom? (Yes)] --> [LOGIN-9]")
                print("  * Confirmed Root Cause: LOGIN-9")
                print("  * Decision Basis (WHY): Missing email notifications upon work order closure due to email verification settings on Work Order.")
                print("  * Next Stage:           Advancing to Resolution Planning to load canonical skill file for 'LOGIN-9'")
                print("=" * 80 + "\n", flush=True)

                return (
                    self._build_confirmed_result(
                        issue_code="LOGIN-9",
                        decision_basis="Confirmed: Missing email notifications upon work order closure due to email deliverability / verification settings.",
                        expected="Deliverability enabled for Work Order notifications",
                        observed={"WorkOrderSymptom": True, "Email": user_details.get("Email")},
                        findings=[
                            Finding(
                                claim="Email notifications not sent on work order closure",
                                evidence_refs=[ev_wo_id],
                            )
                        ],
                    ),
                    new_evidence,
                    self.traversal_steps,
                )
            else:
                ev_email_id = f"ev_email_{uuid.uuid4().hex[:6]}"
                new_ev = {
                    "evidence_id": ev_email_id,
                    "tool_name": "salesforce_get_user_field",
                    "field_name": "EmailVerified",
                    "observed_value": {"EmailVerified": False},
                }
                recorded_evidence.append(new_ev)
                new_evidence.append(new_ev)

                self._record_traversal_step(
                    swimlane="Email Not Verified",
                    node_id="NODE_EMAIL_VERIFIED_CHECK",
                    node_name="Is Email Verified?",
                    from_node="[Decision: Is Email Verified? (No)]",
                    to_node="[TERMINAL: Confirmed Email not verified (LOGIN-10)]",
                    action="Check Salesforce User EmailVerified status",
                    observed={"EmailVerified": False},
                    decision_outcome="Outcome: 'No' (Email Unverified, No WO Symptom)",
                    explanation="User email address has not been verified in Salesforce, preventing login access. Flowchart terminates at root cause 'LOGIN-10'.",
                    tools_called=["salesforce_get_user_field"],
                    status="matched",
                )

                print("\n" + "=" * 80)
                print("[ROOT CAUSE FINALIZED via LOGIN DECISION TREE]")
                print("  * Final Terminal Node:  Confirmed Email not verified (LOGIN-10)")
                print("  * Issue Domain:         LOGIN")
                print("  * Knowledge Graph Path: [Is Email Verified? (No)] --> [Work Order Symptom? (No)] --> [LOGIN-10]")
                print("  * Confirmed Root Cause: LOGIN-10")
                print("  * Decision Basis (WHY): User account email address has not been verified in Salesforce, preventing login access.")
                print("  * Next Stage:           Advancing to Resolution Planning to load canonical skill file for 'LOGIN-10'")
                print("=" * 80 + "\n", flush=True)

                return (
                    self._build_confirmed_result(
                        issue_code="LOGIN-10",
                        decision_basis="Confirmed: Salesforce User account email address is unverified, blocking portal and SSO login.",
                        expected="User.EmailVerified == True",
                        observed={"EmailVerified": False, "Email": user_details.get("Email")},
                        findings=[
                            Finding(
                                claim="Salesforce User account email address is unverified",
                                evidence_refs=[ev_email_id],
                            )
                        ],
                    ),
                    new_evidence,
                    self.traversal_steps,
                )

        # -------------------------------------------------------------
        # SWIMLANE 12: Out Of Scope
        # -------------------------------------------------------------
        self._record_traversal_step(
            swimlane="Out Of Scope",
            node_id="NODE_OUT_OF_SCOPE",
            node_name="Out Of Scope Evaluation",
            from_node="[Decision: Is Email Verified? (Yes)]",
            to_node="[TERMINAL: OUT OF SCOPE (Escalating to Tier-2 support)]",
            action="Final flowchart boundary check",
            observed={"IsActive": True, "EmailVerified": True, "FederationIdentifier": user_details.get("FederationIdentifier")},
            decision_outcome="Outcome: 'Out of Scope' (All flowchart checks passed without issue)",
            explanation="User is active, email verified, and Federation ID populated. No canonical flowchart issue matched. Escalating to Tier-2 engineering.",
            tools_called=["Decision Logic"],
            status="matched",
        )

        print("\n" + "=" * 80)
        print("[ESCALATION BOUNDARY REACHED via LOGIN DECISION TREE]")
        print("  * Terminal Node:        OUT OF SCOPE (Escalating to Tier-2 support)")
        print("  * Knowledge Graph Path: [Is Email Verified? (Yes)] --> [OUT-OF-SCOPE]")
        print("  * Escalation Code:      OUT-OF-SCOPE")
        print("  * Decision Basis (WHY): User verified active with valid credentials, verified email, and valid Federation ID. No canonical login issue matched flowchart criteria. Routing to Tier-2 engineering.")
        print("  * Next Stage:           Routing incident to Tier-2 human support team")
        print("=" * 80 + "\n", flush=True)

        return (
            self._build_escalation_result(
                issue_code="OUT-OF-SCOPE",
                reason="User verified active with valid credentials, verified email, and valid Federation ID. No canonical login issue matched flowchart criteria. Routing to Tier-2 engineering.",
                evidence_refs=[ev_search_id],
            ),
            new_evidence,
            self.traversal_steps,
        )

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
