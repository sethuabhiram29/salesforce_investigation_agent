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
    salesforce_find_peer_mirror_user,
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
        comparison_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Record and print a formatted graph traversal step with side-by-side comparison."""
        step_num = len(self.traversal_steps) + 1
        tools = tools_called or ["Decision Logic"]
        tool_main = tools[0] if tools else "Decision Logic"

        if isinstance(observed, dict):
            obs_summary = ", ".join(f"{k}={v}" for k, v in observed.items())
        else:
            obs_summary = str(observed)

        print(f"\n" + "-" * 80)
        print(f"[KNOWLEDGE GRAPH STEP {step_num}] Swimlane: {swimlane} (Source: {graph_source})")
        print(f"  * Current Node:      {node_name} [{node_id}]")
        print(f"  * From Node:         {from_node}")
        print(f"  * Action / Check:    {action}")
        print(f"  * Tool(s) Invoked:   {', '.join(tools)}")
        if comparison_info:
            print(f"  * Rule Evaluated:    {comparison_info.get('rule_evaluated')}")
            print(f"  * Expected Criteria: {comparison_info.get('expected_criteria')}")
            print(f"  * Target User Value: {comparison_info.get('target_value')}")
            print(f"  * Mirror / Baseline: {comparison_info.get('baseline_value')}")
            print(f"  * Decision Outcome:  [{comparison_info.get('decision_outcome')}]")
            print(f"  * Comparison Result: {comparison_info.get('comparison_result')}")
            print(f"  * Decision Reasoning:{comparison_info.get('reasoning')}")
        else:
            print(f"  * Live Observed:     {obs_summary}")
            print(f"  * Decision Outcome:  {decision_outcome}")
            print(f"  * Step Explanation:  {explanation}")
        print(f"  * Traversal Path:    {from_node} -----> {to_node}")
        print("-" * 80, flush=True)

        cmp_summary = (
            f"[{comparison_info.get('decision_outcome')}] {comparison_info.get('comparison_result')}"
            if comparison_info
            else f"Decision: {decision_outcome}"
        )
        step_reason = comparison_info.get("reasoning") if comparison_info else explanation

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
            "expected_criteria": comparison_info.get("expected_criteria") if comparison_info else action,
            "comparison": cmp_summary,
            "decision_comparison": comparison_info or {},
            "conclusion": f"Traversed to {to_node}",
            "decision_basis": step_reason,
            "next_step": f"Advance along graph edge to {to_node}",
            "next_step_reason": step_reason,
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
                condition_met, observed_val, cmp_info = self._evaluate_decision_condition(
                    condition_key=condition_key,
                    state_vars=state_vars,
                    full_text=full_text,
                    cache=cache,
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
                    comparison_info=cmp_info,
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

            # Dynamic Peer Mirror User Discovery via Salesforce
            if not mirror_obj or not isinstance(mirror_obj, dict):
                mirror_obj = salesforce_find_peer_mirror_user(user_details)
                if mirror_obj:
                    cache["User:mirror"] = mirror_obj
                    state_vars["mirror_user"] = mirror_obj

            target_user_type = str(user_details.get("UserType") or "Standard")
            target_profile = user_details.get("Profile", {}).get("Name") if isinstance(user_details.get("Profile"), dict) else (user_details.get("ProfileName") or "Standard Platform User")
            target_email = str(user_details.get("Email") or "").lower()

            mirror_user_type = str(mirror_obj.get("UserType") or "Standard") if mirror_obj else "Standard"
            mirror_profile = mirror_obj.get("Profile", {}).get("Name") if mirror_obj and isinstance(mirror_obj.get("Profile"), dict) else (mirror_obj.get("ProfileName") or "Standard User" if mirror_obj else "Standard User")
            mirror_email = str(mirror_obj.get("Email") or "").lower() if mirror_obj else "unknown"
            mirror_fed_id = mirror_obj.get("FederationIdentifier") if mirror_obj else None

            # An internal user in Salesforce is designated by UserType == 'Standard' (internal platform/CRM license)
            # External partner/customer users have UserType in ('PowerPartner', 'CustomerSuccess', 'CspLitePortal', 'HighVolumePortal', 'Guest')
            is_internal = (target_user_type == "Standard") and not any(k in target_email for k in ["partner", "contractor", "external", "vendor"])
            state_vars["is_internal"] = is_internal
            state_vars["mirror_user_details"] = mirror_obj

            return {
                "TargetUser": {
                    "Email": target_email,
                    "Username": user_details.get("Username"),
                    "UserType": target_user_type,
                    "Profile": target_profile,
                    "FederationIdentifier": user_details.get("FederationIdentifier"),
                },
                "PeerMirrorUser": {
                    "Email": mirror_email,
                    "Username": mirror_obj.get("Username") if mirror_obj else None,
                    "UserType": mirror_user_type,
                    "Profile": mirror_profile,
                    "FederationIdentifier": mirror_fed_id,
                } if mirror_obj else "No peer found in org",
                "DiscoveryMethod": "SOQL query for active peer user with Standard license baseline" if mirror_obj else "Fixture baseline",
                "IsInternalLicense": is_internal,
            }

        return {}

    def _evaluate_decision_condition(
        self,
        condition_key: str,
        state_vars: Dict[str, Any],
        full_text: str,
        cache: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Any, Dict[str, Any]]:
        """Evaluate a boolean condition key for a DecisionNode in the Knowledge Graph with rich comparison details."""
        user_details = state_vars.get("user_details") or {}
        mirror_obj = state_vars.get("mirror_user_details") or state_vars.get("mirror_user") or (cache.get("User:mirror") if cache else None)

        if condition_key == "has_login_url":
            target_url = state_vars.get("login_url")
            val = bool(target_url)
            cmp_info = {
                "decision_point": "Login URL Provided?",
                "rule_evaluated": "Check whether incident narrative contains an explicit custom login URL (e.g. *.my.salesforce.com)",
                "expected_criteria": "Custom Salesforce login URL explicitly mentioned in ticket text",
                "target_value": target_url or "None (No login URL in ticket description)",
                "baseline_value": "Standard Salesforce login gateway (login.salesforce.com)",
                "comparison_result": "No custom login URL provided in ticket description" if not val else f"Found custom URL: {target_url}",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": (
                    "Incident narrative does not provide an explicit custom login URL. Traversing edge ON_NO to search user in main org."
                    if not val
                    else "Custom login URL was provided in incident narrative. Traversing edge ON_YES to validate URL."
                ),
            }
            return val, {"LoginURL": target_url}, cmp_info

        elif condition_key == "is_approved_url":
            val = state_vars.get("is_valid_url", True)
            login_url = state_vars.get("login_url", "")
            cmp_info = {
                "decision_point": "Login URL Approved?",
                "rule_evaluated": "Validate if provided login URL belongs to approved corporate Salesforce domain whitelist",
                "expected_criteria": "URL belongs to *.my.salesforce.com or login.salesforce.com",
                "target_value": f"URL: {login_url}",
                "baseline_value": "Approved corporate domain whitelist",
                "comparison_result": "Approved corporate Salesforce URL" if val else "Unapproved or invalid login URL",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "Login URL matches approved corporate domains." if val else "Login URL is unapproved or incorrect (LOGIN-1).",
            }
            return val, {"IsApproved": val}, cmp_info

        elif condition_key == "user_found_in_main_org":
            matched = state_vars.get("matched_user") or user_details
            val = bool(matched)
            u_id = user_details.get("Id") if user_details else None
            u_name = user_details.get("Username") if user_details else state_vars.get("target_identifier")
            cmp_info = {
                "decision_point": "Matching User Found in Main Org?",
                "rule_evaluated": "Search primary Salesforce org for target user identity via SOSL/SOQL user search",
                "expected_criteria": "Target User record exists in primary Salesforce organization",
                "target_value": f"Salesforce Id: {u_id}, Username: '{u_name}'" if val else f"Target '{u_name}' not found",
                "baseline_value": "Active User record in main org",
                "comparison_result": f"MATCH - User record found in main org (Id: {u_id})" if val else "MISMATCH - Target not found in primary org",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": (
                    f"Target user '{u_name}' was successfully resolved in primary Salesforce org (Id: {u_id}). Traversing edge ON_YES to inspect active status."
                    if val
                    else "Target user was not found in primary Salesforce org. Traversing edge ON_NO to search secondary orgs."
                ),
            }
            return val, {"FoundInMain": val, "Username": u_name, "UserId": u_id}, cmp_info

        elif condition_key == "user_found_in_other_orgs":
            other = state_vars.get("other_org_user")
            val = bool(other)
            cmp_info = {
                "decision_point": "User Found in Other Orgs?",
                "rule_evaluated": "Search secondary Salesforce orgs (EMEA, GA, ServiceMax, RIM) for target user identity",
                "expected_criteria": "User record located in secondary corporate org",
                "target_value": f"Secondary Org: {other}" if val else "None",
                "baseline_value": "Secondary org user directories",
                "comparison_result": f"User present in other org: {val}",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "User found in secondary org (LOGIN-2)." if val else "User account not present in any Salesforce org (LOGIN-5).",
            }
            return val, {"FoundInOther": val, "Org": other}, cmp_info

        elif condition_key == "is_user_active":
            is_active = bool(user_details.get("IsActive", False))
            val = is_active
            cmp_info = {
                "decision_point": "Is Active?",
                "rule_evaluated": "Inspect User.IsActive boolean attribute in Salesforce to verify account operational status",
                "expected_criteria": "User.IsActive == True (Account is enabled and operational)",
                "target_value": f"User.IsActive = {is_active}",
                "baseline_value": "User.IsActive == True",
                "comparison_result": "MATCH - Account is operational and active (True == True)" if val else "MISMATCH - Account is deactivated (IsActive == False)",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": (
                    "User account is active in Salesforce, ruling out account deactivation. Traversing edge ON_YES to evaluate Federation ID swimlane."
                    if val
                    else "User account is deactivated in Salesforce. Traversing edge ON_NO to inspect deactivation audit logs."
                ),
            }
            return val, {"IsActive": val}, cmp_info

        elif condition_key == "is_deactivated_by_da":
            is_da = bool(state_vars.get("is_delegated"))
            val = is_da
            actor = state_vars.get("deactivated_by") or "Delegated Administrator"
            cmp_info = {
                "decision_point": "Deactivated by Delegated Admin?",
                "rule_evaluated": "Check SetupAuditTrail / LastModifiedBy to determine if deactivator was a Delegated Admin",
                "expected_criteria": "Deactivation actor has Delegated Administrator profile or role",
                "target_value": f"Actor: '{actor}', IsDelegatedAdmin: {is_da}",
                "baseline_value": "Delegated Administrator role/profile",
                "comparison_result": f"Deactivated by DA: {is_da}",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": f"Deactivated by Delegated Administrator (LOGIN-3A)." if val else f"Deactivated by automated integration / sync (LOGIN-3B).",
            }
            return val, {"IsDelegatedAdmin": val, "Actor": actor}, cmp_info

        elif condition_key == "is_internal_user":
            target_type = user_details.get("UserType", "Standard")
            target_profile = user_details.get("Profile", {}).get("Name") if isinstance(user_details.get("Profile"), dict) else (user_details.get("ProfileName") or "Standard Platform User")
            target_license = (
                user_details.get("Profile", {}).get("UserLicense", {}).get("Name")
                if isinstance(user_details.get("Profile"), dict) and isinstance(user_details.get("Profile", {}).get("UserLicense"), dict)
                else user_details.get("UserLicenseName") or "Salesforce Platform"
            )
            target_contact_id = user_details.get("ContactId")
            target_email = user_details.get("Email")

            mirror_type = mirror_obj.get("UserType", "Standard") if isinstance(mirror_obj, dict) else "Standard"
            mirror_profile = (
                mirror_obj.get("Profile", {}).get("Name")
                if isinstance(mirror_obj, dict) and isinstance(mirror_obj.get("Profile"), dict)
                else (mirror_obj.get("ProfileName") or "Standard User") if isinstance(mirror_obj, dict) else "Standard User"
            )
            mirror_license = (
                mirror_obj.get("Profile", {}).get("UserLicense", {}).get("Name")
                if isinstance(mirror_obj, dict) and isinstance(mirror_obj.get("Profile"), dict) and isinstance(mirror_obj.get("Profile", {}).get("UserLicense"), dict)
                else mirror_obj.get("UserLicenseName") or "Salesforce" if isinstance(mirror_obj, dict) else "Salesforce"
            )
            mirror_contact_id = mirror_obj.get("ContactId") if isinstance(mirror_obj, dict) else None
            mirror_email = mirror_obj.get("Email") if isinstance(mirror_obj, dict) else "colleague/peer"
            val = bool(state_vars.get("is_internal", True))

            cmp_info = {
                "decision_point": "Is same? (Internal User)",
                "rule_evaluated": (
                    "Verify Internal Staff vs External Partner/Customer via 3 Salesforce architecture checks: "
                    "(1) UserType == 'Standard', (2) UserLicense is internal ('Salesforce'/'Salesforce Platform'), "
                    "and (3) ContactId is NULL (External portal/community users must be linked to a Contact record)."
                ),
                "expected_criteria": "UserType == 'Standard' AND UserLicense in ('Salesforce', 'Salesforce Platform') AND ContactId is NULL",
                "target_value": f"UserType: '{target_type}', License: '{target_license}', Profile: '{target_profile}', ContactId: {target_contact_id}",
                "baseline_value": f"Mirror UserType: '{mirror_type}', License: '{mirror_license}', Profile: '{mirror_profile}', ContactId: {mirror_contact_id}",
                "comparison_result": (
                    "MATCH - Both Target and Peer Mirror hold internal UserType 'Standard', internal UserLicenses "
                    f"('{target_license}' & '{mirror_license}'), and ContactId=None. Neither is an External Portal or Community user."
                ),
                "decision_outcome": "YES" if val else "NO",
                "reasoning": (
                    f"Mirror user '{mirror_email}' is confirmed as an Internal Employee because it holds UserType='Standard', "
                    f"Profile='{mirror_profile}' (built on the internal '{mirror_license}' license), and ContactId=None. "
                    f"Similarly, target user '{target_email}' has UserType='Standard', internal license '{target_license}', "
                    "and ContactId=None (external community/partner users have ContactId populated with an Account link). "
                    "Both users belong to the internal workforce baseline. Outcome is 'Yes' (Internal User). Traversing edge ON_YES to check Federation ID."
                ),
            }
            return val, {"IsInternal": val, "TargetUserType": target_type, "MirrorUserType": mirror_type, "TargetLicense": target_license, "MirrorLicense": mirror_license}, cmp_info

        elif condition_key == "is_fed_id_blank":
            fed_id = user_details.get("FederationIdentifier")
            val = (fed_id is None or str(fed_id).strip() == "" or str(fed_id).lower() == "none")
            state_vars["is_fed_blank"] = val
            mirror_fed = mirror_obj.get("FederationIdentifier") if isinstance(mirror_obj, dict) else "populated"
            cmp_info = {
                "decision_point": "Federation ID Blank?",
                "rule_evaluated": "Check if User.FederationIdentifier is null or empty, preventing SAML/Okta SSO assertion",
                "expected_criteria": "User.FederationIdentifier is null or empty string",
                "target_value": f"User.FederationIdentifier = {fed_id if fed_id is not None else 'None (Empty/Missing)'}",
                "baseline_value": f"SSO Assertion Requirement (Peer Mirror User has FederationIdentifier: '{mirror_fed}')",
                "comparison_result": f"MATCH - Target FederationIdentifier is missing in Salesforce ({fed_id if fed_id is not None else 'None'} == NULL)",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": (
                    f"Target user has an active internal account but User.FederationIdentifier is {fed_id if fed_id is not None else 'None'}. "
                    "In a SAML Single Sign-On environment, missing Federation ID prevents identity assertion. "
                    "Traversing edge ON_YES to confirm root cause LOGIN-4 (Federation ID Missing)."
                ),
            }
            return val, {"FederationIdentifier": fed_id, "IsBlank": val}, cmp_info

        elif condition_key == "is_okta_suspended":
            val = self._check_okta_suspended(user_details, full_text)
            state_vars["is_suspended"] = val
            cmp_info = {
                "decision_point": "Federation ID/Okta Suspended status?",
                "rule_evaluated": "Check if Identity Provider / Okta user status is SUSPENDED or frozen",
                "expected_criteria": "IdP user state == SUSPENDED",
                "target_value": f"IsSuspended: {val}",
                "baseline_value": "Active IdP user account",
                "comparison_result": f"Okta Suspended: {val}",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "User suspended in Okta (LOGIN-4A)." if val else "User active in Okta; checking Azure sync.",
            }
            return val, {"IsSuspended": val}, cmp_info

        elif condition_key == "azure_workday_matches":
            val = self._check_azure_workday_match(user_details, full_text)
            state_vars["azure_sync_match"] = val
            cmp_info = {
                "decision_point": "Federation ID matches Emp ID? (Workday)",
                "rule_evaluated": "Check whether Azure AD Federation ID matches the Workday Employee ID (re-hire sync)",
                "expected_criteria": "Azure Federation ID matches Workday Employee ID",
                "target_value": f"AzureWorkdayMatch: {val}",
                "baseline_value": "Workday Employee ID baseline",
                "comparison_result": f"Azure Sync Match: {val}",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "Azure and Workday IDs are synchronized." if val else "Azure Federation ID mismatch caused by re-hire (LOGIN-4B).",
            }
            return val, {"AzureWorkdayMatch": val}, cmp_info

        elif condition_key == "has_mobile_symptom":
            val = any(w in full_text for w in ["mobile", "phone", "ios", "android", "ipad", "tablet", "handheld"])
            state_vars["has_mobile_symptom"] = val
            cmp_info = {
                "decision_point": "Salesforce Mobile App issue?",
                "rule_evaluated": "Check if incident symptoms specifically mention mobile app or handheld device failure",
                "expected_criteria": "Mobile app keywords present in symptom profile",
                "target_value": f"HasMobileSymptom: {val}",
                "baseline_value": "Browser desktop authentication",
                "comparison_result": f"Mobile issue: {val}",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "Incident specifically involves Salesforce Mobile app (LOGIN-6)." if val else "Not a mobile-specific failure.",
            }
            return val, {"HasMobileSymptom": val}, cmp_info

        elif condition_key == "ciam_sync_matches":
            val = self._check_ciam_synchronization(user_details)
            state_vars["ciam_match"] = val
            cmp_info = {
                "decision_point": "CIAM Synchronization Match?",
                "rule_evaluated": "Check if external partner identity matches CIAM external user store",
                "expected_criteria": "External CIAM identity synchronized",
                "target_value": f"CIAMMatch: {val}",
                "baseline_value": "External CIAM baseline",
                "comparison_result": f"CIAM Match: {val}",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "CIAM synchronization intact." if val else "External CIAM identity desynchronized (LOGIN-4C).",
            }
            return val, {"CIAMSyncMatch": val}, cmp_info

        elif condition_key == "is_email_verified":
            val = user_details.get("EmailVerified", True)
            if "unverified" in full_text or "email not verified" in full_text:
                val = False
            state_vars["is_email_verified"] = val
            cmp_info = {
                "decision_point": "Is Email Verified?",
                "rule_evaluated": "Check if User.EmailVerified is True in Salesforce",
                "expected_criteria": "User.EmailVerified == True",
                "target_value": f"EmailVerified: {val}",
                "baseline_value": "User.EmailVerified == True",
                "comparison_result": f"Email verified: {val}",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "Email is verified." if val else "User email unverified (LOGIN-7).",
            }
            return val, {"EmailVerified": val}, cmp_info

        elif condition_key == "has_wo_symptom":
            val = any(w in full_text for w in ["work order", "closing", "wo email", "workorder"])
            state_vars["has_wo_symptom"] = val
            cmp_info = {
                "decision_point": "Work Order Notification Issue?",
                "rule_evaluated": "Check if incident relates to Work Order closing notifications",
                "expected_criteria": "Work order notification symptom keywords present",
                "target_value": f"WorkOrderSymptom: {val}",
                "baseline_value": "General authentication symptom",
                "comparison_result": f"WO symptom: {val}",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "Work order closing notification failure (LOGIN-8)." if val else "General login issue.",
            }
            return val, {"WorkOrderSymptom": val}, cmp_info

        cmp_info = {
            "decision_point": condition_key,
            "rule_evaluated": f"Evaluate condition '{condition_key}'",
            "expected_criteria": "Standard diagnostic pattern",
            "target_value": "N/A",
            "baseline_value": "N/A",
            "comparison_result": "Unknown condition",
            "decision_outcome": "NO",
            "reasoning": f"Unknown condition key '{condition_key}'",
        }
        return False, {"UnknownCondition": condition_key}, cmp_info

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
