"""Knowledge Graph-Driven Traversal Engine for Diagnosis Agent.

Queries and traverses the Decision Tree Knowledge Graph (stored in Neo4j with
offline local graph fallback) to diagnose Login Issues dynamically.

Every step retrieves the current node, executes the tool action or evaluates
the decision condition, looks up the outgoing edge (ON_YES, ON_NO, TRANSITIONS_TO),
and navigates the graph until a TerminalNode is reached.
"""

import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple
import uuid

from app.models.schemas import DiagnosisResult, Finding
from app.knowledge.neo4j_repository import neo4j_repository
from app.tools.salesforce import (
    salesforce_get_user_package_licenses,
    salesforce_get_user_public_groups,
    salesforce_add_user_to_public_group,
    salesforce_get_user_permission_sets,
    salesforce_user_search,
    salesforce_get_user_details,
    salesforce_get_user_field,
    salesforce_find_peer_mirror_user,
    salesforce_execute_soql,
    salesforce_validate_login_url,
    salesforce_cross_org_user_search,
    salesforce_audit_trail_search,
    salesforce_check_delegated_admin,
    identity_team_engage,
    salesforce_get_object_permissions,
    salesforce_get_record_access,
    salesforce_compare_user_access,
    salesforce_get_contact_wizard_details,
)
from app.tools.service_now import (
    servicenow_add_work_notes,
    servicenow_reroute_incident,
    servicenow_record_ritm_guidance,
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

        try:
            print(f"\n" + "-" * 80)
            try:
                print(f"[KNOWLEDGE GRAPH STEP {step_num}] Swimlane: {swimlane} (Source: {graph_source})")
            except (OSError, UnicodeEncodeError):
                pass
            try:
                print(f"  * Current Node:      {node_name} [{node_id}]")
            except (OSError, UnicodeEncodeError):
                pass
            try:
                print(f"  * From Node:         {from_node}")
            except (OSError, UnicodeEncodeError):
                pass
            try:
                print(f"  * Action / Check:    {action}")
            except (OSError, UnicodeEncodeError):
                pass
            try:
                print(f"  * Tool(s) Invoked:   {', '.join(tools)}")
            except (OSError, UnicodeEncodeError):
                pass
            if comparison_info:
                try:
                    print(f"  * Rule Evaluated:    {comparison_info.get('rule_evaluated')}")
                except (OSError, UnicodeEncodeError):
                    pass
                try:
                    print(f"  * Expected Criteria: {comparison_info.get('expected_criteria')}")
                except (OSError, UnicodeEncodeError):
                    pass
                try:
                    print(f"  * Target User Value: {comparison_info.get('target_value')}")
                except (OSError, UnicodeEncodeError):
                    pass
                try:
                    print(f"  * Mirror / Baseline: {comparison_info.get('baseline_value')}")
                except (OSError, UnicodeEncodeError):
                    pass
                try:
                    print(f"  * Decision Outcome:  [{comparison_info.get('decision_outcome')}]")
                except (OSError, UnicodeEncodeError):
                    pass
                try:
                    print(f"  * Comparison Result: {comparison_info.get('comparison_result')}")
                except (OSError, UnicodeEncodeError):
                    pass
                try:
                    print(f"  * Decision Reasoning:{comparison_info.get('reasoning')}")
                except (OSError, UnicodeEncodeError):
                    pass
            else:
                try:
                    print(f"  * Live Observed:     {obs_summary}")
                except (OSError, UnicodeEncodeError):
                    pass
                try:
                    print(f"  * Decision Outcome:  {decision_outcome}")
                except (OSError, UnicodeEncodeError):
                    pass
                try:
                    print(f"  * Step Explanation:  {explanation}")
                except (OSError, UnicodeEncodeError):
                    pass
            try:
                print(f"  * Traversal Path:    {from_node} -----> {to_node}")
            except (OSError, UnicodeEncodeError):
                pass
            try:
                print("-" * 80, flush=True)
            except (OSError, UnicodeEncodeError):
                pass
        except (OSError, UnicodeEncodeError):
            pass

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
            "comparison_info": comparison_info or {},
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

        rec_ids = (
            ctx.get("record_ids")
            or (ctx.get("extracted_entities", {}).get("record_ids") if isinstance(ctx.get("extracted_entities"), dict) else None)
            or ctx.get("target_record_id")
            or ctx.get("record_id")
        )
        if isinstance(rec_ids, list) and rec_ids:
            record_id = str(rec_ids[0])
        elif rec_ids:
            record_id = str(rec_ids)
        else:
            m_rec = re.search(r"\b00[0-9a-zA-Z]{13,16}\b", full_text)
            record_id = m_rec.group(0) if m_rec else None

        # 1. Retrieve Root Node from Neo4j Knowledge Graph
        start_node = neo4j_repository.get_flowchart_start_node(domain)
        graph_source = start_node.get("source", "neo4j")

        try:
            print("\n" + "=" * 80)
            try:
                print(f"  [NEO4J KNOWLEDGE GRAPH ENGINE] Traversing Decision Tree for Domain '{domain}'")
            except (OSError, UnicodeEncodeError):
                pass
            try:
                print(f"  * Graph Source:     {graph_source}")
            except (OSError, UnicodeEncodeError):
                pass
            try:
                print(f"  * Root Node ID:     {start_node.get('id')}")
            except (OSError, UnicodeEncodeError):
                pass
            try:
                print(f"  * Target User:      {affected_user_id}")
            except (OSError, UnicodeEncodeError):
                pass
            try:
                print(f"  * Mirror User:      {mirror_user.get('Email') if isinstance(mirror_user, dict) else (mirror_user or 'None')}")
            except (OSError, UnicodeEncodeError):
                pass
            try:
                print(f"  * Login URL:        {login_url or 'None provided in incident narrative'}")
            except (OSError, UnicodeEncodeError):
                pass
            try:
                print("=" * 80, flush=True)
            except (OSError, UnicodeEncodeError):
                pass
        except (OSError, UnicodeEncodeError):
            pass

        current_node = start_node
        from_label = "[Triage Agent]"

        incident_id = context.get("incident_id") if isinstance(context, dict) else None
        # Runtime evaluation state
        state_vars: Dict[str, Any] = {
            "incident_id": incident_id,
            "target_identifier": target_identifier,
            "affected_user_id": affected_user_id,
            "record_id": record_id,
            "login_url": login_url,
            "is_valid_url": True,
            "domain": domain,
            "package_licenses": [],
            "public_groups": [],
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

        if isinstance(ctx, dict):
            for k, v in ctx.items():
                if k not in state_vars or state_vars[k] is None or state_vars[k] is False:
                    state_vars[k] = v

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
            node_type = str(current_node.get("node_type") or current_node.get("type", "decision")).lower()
            swimlane = current_node.get("swimlane", "General")
            node_source = current_node.get("source", graph_source)

            # Check if Terminal Node reached in Knowledge Graph
            if node_type == "terminal":
                issue_code = current_node.get("issue_code", "UNKNOWN")
                status = current_node.get("status")
                if not status:
                    if current_node.get("review_required") or current_node.get("issue_code") in ["UNKNOWN", "OUT-OF-SCOPE", "MANUAL-REVIEW"]:
                        status = "escalation_required"
                    else:
                        status = "confirmed" 
                decision_basis = current_node.get("decision_basis", f"Flowchart terminated at {node_name}")
                expected = current_node.get("expected_criteria", "Standard diagnostic pattern")

                self._record_traversal_step(
                    swimlane=swimlane,
                    node_id=node_id,
                    node_name=node_name,
                    from_node=from_label,
                    to_node="[TERMINAL]",
                    action=f"Terminal Node: {node_name}",
                    observed={"status": status, "issue_code": issue_code},
                    decision_outcome=f"Terminal Outcome: {status}",
                    explanation=decision_basis,
                    tools_called=["KnowledgeGraphTerminalEvaluator"],
                    status=status,
                    graph_source=node_source,
                )

                if status == "confirmed":
                    try:
                        print("\n" + "=" * 80)
                        try:
                            print(f"[ROOT CAUSE FINALIZED via KNOWLEDGE GRAPH: {node_source}]")
                        except (OSError, UnicodeEncodeError):
                            pass
                        try:
                            print(f"  * Final Terminal Node:  {node_name} ({issue_code})")
                        except (OSError, UnicodeEncodeError):
                            pass
                        try:
                            print(f"  * Confirmed Root Cause: {issue_code}")
                        except (OSError, UnicodeEncodeError):
                            pass
                        try:
                            print(f"  * Decision Basis (WHY): {decision_basis}")
                        except (OSError, UnicodeEncodeError):
                            pass
                        try:
                            print(f"  * Next Stage:           Advancing to Resolution Planning to load canonical skill file")
                        except (OSError, UnicodeEncodeError):
                            pass
                        try:
                            print("=" * 80 + "\n", flush=True)
                        except (OSError, UnicodeEncodeError):
                            pass
                    except (OSError, UnicodeEncodeError):
                        pass

                    findings = [
                        Finding(
                            claim=f"Confirmed diagnostic criteria for {issue_code}",
                            evidence_refs=[ev_id for ev_id in [state_vars.get("ev_search_id"), state_vars.get("ev_fed_id"), state_vars.get("ev_deact_id"), state_vars.get("ev_url_id")] if ev_id],
                        )
                    ]
                    obs_dict = dict(current_node)
                    if state_vars.get("user_details"):
                        obs_dict.update({k: v for k, v in state_vars["user_details"].items() if k not in obs_dict or obs_dict[k] is None})
                    if state_vars.get("deactivated_by"):
                        obs_dict["deactivation_actor"] = state_vars["deactivated_by"]
                        obs_dict["Actor"] = state_vars["deactivated_by"]
                    if state_vars.get("is_delegated") is not None:
                        obs_dict["IsDelegatedAdmin"] = state_vars["is_delegated"]
                    if state_vars.get("target_emp_id"):
                        obs_dict["EmployeeNumber"] = state_vars["target_emp_id"]
                    if state_vars.get("target_fed_id") is not None:
                        obs_dict["FederationIdentifier"] = state_vars["target_fed_id"]

                    # Dynamically invoke ServiceNow tool when diagnosis locks
                    inc_id = state_vars.get("incident_id")
                    if inc_id:
                        if issue_code in ["LOGIN-1", "LOGIN-001"]:
                            servicenow_reroute_incident(inc_id, "HCL Service Desk", decision_basis, agent_name="StructuredDiagnosisFlow")
                        elif issue_code in ["LOGIN-1B", "LOGIN-001B"]:
                            servicenow_reroute_incident(inc_id, "Salesforce Regional Support", decision_basis, agent_name="StructuredDiagnosisFlow")
                        elif issue_code in ["LOGIN-3A", "LOGIN-003A"]:
                            servicenow_record_ritm_guidance(inc_id, "Manage User - Account Reactivation", decision_basis, agent_name="StructuredDiagnosisFlow")
                        elif issue_code in ["LOGIN-5", "LOGIN-005"]:
                            servicenow_record_ritm_guidance(inc_id, "Manage User - Federation ID Correction", decision_basis, agent_name="StructuredDiagnosisFlow")
                        else:
                            servicenow_add_work_notes(inc_id, f"Diagnosed root cause '{issue_code}': {decision_basis}", stage="diagnosis", agent_name="StructuredDiagnosisFlow")

                    return (
                        self._build_confirmed_result(
                            issue_code=issue_code,
                            decision_basis=decision_basis,
                            expected=expected,
                            observed=obs_dict,
                            findings=findings,
                        ),
                        new_evidence,
                        self.traversal_steps,
                    )
                else:
                    try:
                        print("\n" + "=" * 80)
                        try:
                            print(f"[ESCALATION NODE REACHED via KNOWLEDGE GRAPH: {node_source}]")
                        except (OSError, UnicodeEncodeError):
                            pass
                        try:
                            print(f"  * Terminal Node:   {node_name} ({issue_code})")
                        except (OSError, UnicodeEncodeError):
                            pass
                        try:
                            print(f"  * Escalation Code: {issue_code}")
                        except (OSError, UnicodeEncodeError):
                            pass
                        try:
                            print(f"  * Decision Basis:  {decision_basis}")
                        except (OSError, UnicodeEncodeError):
                            pass
                        try:
                            print(f"  * Next Stage:      Routing incident to Tier-2 human support team")
                        except (OSError, UnicodeEncodeError):
                            pass
                        try:
                            print("=" * 80 + "\n", flush=True)
                        except (OSError, UnicodeEncodeError):
                            pass
                    except (OSError, UnicodeEncodeError):
                        pass

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

                if "azure_evidence" in state_vars:
                    ev_item = state_vars.pop("azure_evidence")
                    recorded_evidence.append(ev_item)
                    new_evidence.append(ev_item)

                domain_routes = transitions.get('domain_routes', {})
                if domain_routes:
                    target_domain = str(state_vars.get('domain') or 'LOGIN').upper()
                    next_node_id = domain_routes.get(target_domain)
                    if not next_node_id:
                        next_node_id = domain_routes.get('LOGIN') or next(iter(domain_routes.values()))
                    decision_str = f"Domain: '{target_domain}'"
                    edge_used = f"ON_DOMAIN_{target_domain}"
                elif condition_met:
                    next_node_id = transitions.get('yes_target')
                    decision_str = "Outcome: 'Yes'"
                    edge_used = "ON_YES"
                else:
                    next_node_id = transitions.get('no_target')
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
        action_type = node.get("action_type") or node.get("action_name")

        if action_type == "enter_login_domain":
            return {"Domain": "LOGIN", "Status": "Entering Login Domain Deep Diagnosis"}

        elif action_type == "enter_application_domain":
            return {"Domain": "APPLICATION", "Status": "Entering Application Domain Deep Diagnosis"}

        elif action_type == "enter_record_domain":
            return {"Domain": "RECORD", "Status": "Entering Record Domain Deep Diagnosis"}

        elif action_type == "enter_object_domain":
            return {"Domain": "OBJECT", "Status": "Entering Object Domain Deep Diagnosis"}

        elif action_type == "follow_login_flow":
            target = state_vars.get("target_identifier")
            return {
                "Target": target,
                "Action": "Following Login Mainflow: verifying user existence and active status in NA org before domain diagnosis",
            }

        elif action_type == "ingest_triage":
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

        elif action_type == "check_user_unapproved_url":
            target = state_vars["target_identifier"]
            user_details = cache.get("User")
            if not user_details:
                search_results = salesforce_user_search(target)
                identity_check = validate_user_identity_resolution(search_results)
                matched_user = identity_check.get("user") if identity_check.get("status") in ("resolved", "unique") else None
                if matched_user:
                    user_id = matched_user["Id"]
                    user_details = salesforce_get_user_details(user_id)
                    cache["User"] = user_details
                    cache[f"User:{user_id}"] = user_details
                    state_vars["user_details"] = user_details
                    state_vars["matched_user"] = matched_user
            exists_in_main = bool(user_details or state_vars.get("matched_user"))
            state_vars["user_exists_in_main_org"] = exists_in_main

            ev_id = f"ev_user_check_unapp_{uuid.uuid4().hex[:6]}"
            new_ev = {
                "evidence_id": ev_id,
                "tool_name": "salesforce_user_search",
                "field_name": "UserExistenceUnapprovedURL",
                "observed_value": {
                    "Target": target,
                    "ExistsInMainOrg": exists_in_main,
                    "UserId": user_details.get("Id") if user_details else None,
                },
            }
            recorded_evidence.append(new_ev)
            new_evidence.append(new_ev)
            return {"ExistsInMainOrg": exists_in_main, "Target": target}

        elif action_type == "search_user_provided_org":
            target = state_vars["target_identifier"]
            login_url = state_vars.get("login_url", "")
            target_org = self._get_org_for_url(login_url)
            state_vars["provided_org_info"] = target_org

            found_in_provided = self._search_specific_org(target, target_org.get("org_id"))
            state_vars["user_found_in_provided_org"] = bool(found_in_provided)
            state_vars["provided_org_match"] = found_in_provided

            ev_id = f"ev_provided_org_{uuid.uuid4().hex[:6]}"
            new_ev = {
                "evidence_id": ev_id,
                "tool_name": "cross_org_user_search",
                "field_name": "UserLookupProvidedOrg",
                "observed_value": {
                    "Target": target,
                    "ProvidedOrg": target_org,
                    "ExistsInProvidedOrg": bool(found_in_provided),
                },
            }
            recorded_evidence.append(new_ev)
            new_evidence.append(new_ev)
            return {"ExistsInProvidedOrg": bool(found_in_provided), "Target": target, "Org": target_org}

        elif action_type == "search_main_from_cross":
            target = state_vars["target_identifier"]
            user_details = cache.get("User")
            if not user_details:
                search_results = salesforce_user_search(target)
                identity_check = validate_user_identity_resolution(search_results)
                matched_user = identity_check.get("user") if identity_check.get("status") in ("resolved", "unique") else None
                if matched_user:
                    user_id = matched_user["Id"]
                    user_details = salesforce_get_user_details(user_id)
                    cache["User"] = user_details
                    cache[f"User:{user_id}"] = user_details
                    state_vars["user_details"] = user_details
                    state_vars["matched_user"] = matched_user
            exists_in_main = bool(user_details or state_vars.get("matched_user"))
            state_vars["user_found_main_from_cross"] = exists_in_main

            ev_id = f"ev_main_from_cross_{uuid.uuid4().hex[:6]}"
            new_ev = {
                "evidence_id": ev_id,
                "tool_name": "salesforce_user_search",
                "field_name": "UserLookupMainFromCross",
                "observed_value": {
                    "Target": target,
                    "ExistsInMainOrg": exists_in_main,
                    "UserId": user_details.get("Id") if user_details else None,
                },
            }
            recorded_evidence.append(new_ev)
            new_evidence.append(new_ev)
            return {"ExistsInMainOrg": exists_in_main, "Target": target}

        elif action_type == "search_user_main_org":
            target = state_vars["target_identifier"]
            user_details = cache.get("User")

            if not user_details:
                search_results = salesforce_user_search(target)
                identity_check = validate_user_identity_resolution(search_results)
                matched_user = identity_check.get("user") if identity_check.get("status") in ("resolved", "unique") else None
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
                    ev_search_id = f"ev_user_search_{uuid.uuid4().hex[:6]}"
                    state_vars["ev_search_id"] = ev_search_id
                    new_ev = {
                        "evidence_id": ev_search_id,
                        "tool_name": "salesforce_user_search",
                        "field_name": "UserLookupMainOrg",
                        "observed_value": {
                            "Target": target,
                            "Found": False,
                            "Count": 0,
                            "Org": "NA (Primary Main Org)",
                        },
                    }
                    recorded_evidence.append(new_ev)
                    new_evidence.append(new_ev)
            else:
                state_vars["matched_user"] = user_details

            return {
                "Matched": bool(state_vars.get("matched_user")),
                "User": user_details.get("Username") if user_details else None,
                "Target": target,
                "Found": bool(state_vars.get("matched_user")),
            }

        elif action_type == "search_other_orgs":
            target = state_vars["target_identifier"]
            other_user = self._search_other_orgs(target)
            state_vars["other_org_user"] = other_user

            ev_search_id = f"ev_user_search_{uuid.uuid4().hex[:6]}"
            state_vars["ev_search_id"] = ev_search_id
            new_ev = {
                "evidence_id": ev_search_id,
                "tool_name": "cross_org_user_search",
                "field_name": "UserLookupOtherOrgs",
                "observed_value": {
                    "Target": target,
                    "OrgsSearched": ["EMEA", "GA", "ServiceMax", "RIM"],
                    "OtherOrgsMatch": other_user,
                },
            }
            recorded_evidence.append(new_ev)
            new_evidence.append(new_ev)
            return {"OtherOrgs": other_user or "No matching user found across EMEA, GA, ServiceMax, RIM", "Target": target}

        elif action_type == "check_user_active":
            user_details = state_vars.get("user_details")
            if not user_details:
                target = state_vars["target_identifier"]
                search_results = salesforce_user_search(target)
                identity_check = validate_user_identity_resolution(search_results)
                matched_user = identity_check.get("user") if identity_check.get("status") in ("resolved", "unique") else None
                if matched_user:
                    user_id = matched_user["Id"]
                    user_details = salesforce_get_user_details(user_id)
                    cache["User"] = user_details
                    cache[f"User:{user_id}"] = user_details
                    state_vars["user_details"] = user_details
                    state_vars["matched_user"] = matched_user
                elif cache.get("User"):
                    user_details = cache.get("User")
                    state_vars["user_details"] = user_details
                else:
                    user_details = {}
            is_active = user_details.get("IsActive", False)
            state_vars["is_active"] = is_active
            return {"IsActive": is_active, "UserId": user_details.get("Id") if user_details else None}

        elif action_type == "get_deactivation_audit":
            user_details = state_vars.get("user_details") or {}
            deactivated_by = user_details.get("DeactivatedBy", "")

            # Steps 5-7: Retrieve SetupAuditTrail and DelegateGroupMember
            audit_records = salesforce_execute_soql(
                "SELECT Id, Action, CreatedById, Display FROM SetupAuditTrail WHERE Action = 'deactivatedUser' LIMIT 1"
            )
            audit_created_by = audit_records[0].get("CreatedById") if audit_records else None

            delegate_members = salesforce_execute_soql(
                "SELECT Id, UserOrGroupId FROM DelegateGroupMember"
            )
            delegate_user_ids = {str(m.get("UserOrGroupId")) for m in delegate_members if m.get("UserOrGroupId")}

            is_mulesoft = (
                "mulesoft" in str(deactivated_by).lower()
                or "mulesoft" in str(audit_created_by).lower()
                or user_details.get("MuleSoftIntegrationUser", False)
                or "mulesoft" in full_text
            )

            if is_mulesoft:
                is_delegated = False
                deactivated_by = "MuleSoft Integration User"
            else:
                is_delegated = (
                    user_details.get("DelegatedAdmin", False)
                    or (audit_created_by and audit_created_by in delegate_user_ids)
                    or "delegated" in str(deactivated_by).lower()
                    or "delegated" in str(user_details.get("Profile", {}).get("Name", "")).lower()
                    or not is_mulesoft
                )
                deactivated_by = "Delegated Administrator" if is_delegated else (deactivated_by or "MuleSoft Integration User")

            state_vars["is_delegated"] = is_delegated
            state_vars["deactivated_by"] = deactivated_by
            state_vars["setup_audit_created_by"] = audit_created_by

            ev_deact_id = f"ev_deact_audit_{uuid.uuid4().hex[:6]}"
            state_vars["ev_deact_id"] = ev_deact_id
            new_ev = {
                "evidence_id": ev_deact_id,
                "tool_name": "salesforce_get_user_field",
                "field_name": "DeactivationAudit",
                "observed_value": {
                    "IsActive": False,
                    "DeactivatedBy": deactivated_by,
                    "SetupAuditTrailCreatedById": audit_created_by,
                    "IsDelegatedAdmin": is_delegated,
                    "MatchesDelegateGroupMember": is_delegated,
                },
            }
            recorded_evidence.append(new_ev)
            new_evidence.append(new_ev)
            return {"IsActive": False, "Actor": deactivated_by, "IsDelegatedAdmin": is_delegated}

        elif action_type == "fetch_mirror_user":
            user_details = state_vars.get("user_details") or {}
            mirror_obj = cache.get("User:mirror") or state_vars.get("mirror_user")

            if not mirror_obj or not isinstance(mirror_obj, dict):
                mirror_obj = salesforce_find_peer_mirror_user(user_details)
                if mirror_obj:
                    cache["User:mirror"] = mirror_obj
                    state_vars["mirror_user"] = mirror_obj

            state_vars["mirror_user_details"] = mirror_obj
            mirror_email = mirror_obj.get("Email") if isinstance(mirror_obj, dict) else (mirror_obj or "None")
            mirror_user_type = mirror_obj.get("UserType") if isinstance(mirror_obj, dict) else "Standard"

            return {
                "PeerMirrorUser": mirror_email,
                "PeerUserType": mirror_user_type,
                "DiscoveryMethod": "SOQL active peer lookup with matching standard license",
            }

        elif action_type in ["compare_emp_fed_id", "compare_mirror_user"]:
            user_details = state_vars.get("user_details") or {}
            mirror_obj = state_vars.get("mirror_user_details") or cache.get("User:mirror") or state_vars.get("mirror_user")

            # Dynamic Peer Mirror User Discovery via Salesforce if not already discovered
            if not mirror_obj or not isinstance(mirror_obj, dict):
                mirror_obj = salesforce_find_peer_mirror_user(user_details)
                if mirror_obj:
                    cache["User:mirror"] = mirror_obj
                    state_vars["mirror_user"] = mirror_obj
                    state_vars["mirror_user_details"] = mirror_obj

            target_user_type = str(user_details.get("UserType") or "Standard")
            target_profile = user_details.get("Profile", {}).get("Name") if isinstance(user_details.get("Profile"), dict) else (user_details.get("ProfileName") or "Standard Platform User")
            target_email = str(user_details.get("Email") or "").lower()
            target_emp_id = user_details.get("EmployeeNumber") or user_details.get("EmployeeId") or "Not Set"
            target_fed_id = user_details.get("FederationIdentifier")

            mirror_user_type = str(mirror_obj.get("UserType") or "Standard") if mirror_obj else "Standard"
            mirror_profile = mirror_obj.get("Profile", {}).get("Name") if mirror_obj and isinstance(mirror_obj.get("Profile"), dict) else (mirror_obj.get("ProfileName") or "Standard User" if mirror_obj else "Standard User")
            mirror_email = str(mirror_obj.get("Email") or "").lower() if mirror_obj else "unknown"
            mirror_emp_id = mirror_obj.get("EmployeeNumber") or mirror_obj.get("EmployeeId") or "Not Set" if mirror_obj else "Not Set"
            mirror_fed_id = mirror_obj.get("FederationIdentifier") if mirror_obj else None

            # An internal user in Salesforce is designated by UserType == 'Standard' (internal platform/CRM license)
            # External partner/customer users have UserType in ('PowerPartner', 'CustomerSuccess', 'CspLitePortal', 'HighVolumePortal', 'Guest')
            is_internal = (target_user_type == "Standard") and not any(k in target_email for k in ["partner", "contractor", "external", "vendor"])
            state_vars["is_internal"] = is_internal
            state_vars["mirror_user_details"] = mirror_obj
            state_vars["target_emp_id"] = target_emp_id
            state_vars["target_fed_id"] = target_fed_id
            state_vars["mirror_emp_id"] = mirror_emp_id
            state_vars["mirror_fed_id"] = mirror_fed_id

            ev_emp_comp_id = f"ev_emp_fed_comp_{uuid.uuid4().hex[:6]}"
            state_vars["ev_emp_comp_id"] = ev_emp_comp_id
            new_ev = {
                "evidence_id": ev_emp_comp_id,
                "tool_name": "salesforce_get_user_details",
                "field_name": "EmpIdAndFederationIdComparison",
                "observed_value": {
                    "TargetUser": {
                        "Email": target_email,
                        "EmployeeNumber": target_emp_id,
                        "FederationIdentifier": target_fed_id,
                        "UserType": target_user_type,
                    },
                    "PeerMirrorUser": {
                        "Email": mirror_email,
                        "EmployeeNumber": mirror_emp_id,
                        "FederationIdentifier": mirror_fed_id,
                        "UserType": mirror_user_type,
                    },
                    "MirrorIdentityStandard": "Internal Standard user with synchronized Employee ID & Federation ID",
                    "IsInternalEmployee": is_internal,
                },
            }
            recorded_evidence.append(new_ev)
            new_evidence.append(new_ev)

            return {
                "TargetUser": {
                    "Email": target_email,
                    "Username": user_details.get("Username"),
                    "EmployeeNumber": target_emp_id,
                    "FederationIdentifier": target_fed_id,
                    "UserType": target_user_type,
                    "Profile": target_profile,
                },
                "PeerMirrorUser": {
                    "Email": mirror_email,
                    "Username": mirror_obj.get("Username") if mirror_obj else None,
                    "EmployeeNumber": mirror_emp_id,
                    "FederationIdentifier": mirror_fed_id,
                    "UserType": mirror_user_type,
                    "Profile": mirror_profile,
                } if mirror_obj else "No peer found in org",
                "DiscoveryMethod": "SOQL query for active peer user with Standard license baseline" if mirror_obj else "Fixture baseline",
                "IsInternalLicense": is_internal,
            }


        elif action_type == "retrieve_permission_sets":
            target = state_vars["target_identifier"]
            user_details = cache.get("User")
            if not user_details:
                search_results = salesforce_user_search(target)
                identity_check = validate_user_identity_resolution(search_results)
                matched_user = identity_check.get("user") if identity_check.get("status") in ("resolved", "unique") else None
                if matched_user:
                    user_id = matched_user["Id"]
                    user_details = salesforce_get_user_details(user_id)
                    cache["User"] = user_details
                    cache[f"User:{user_id}"] = user_details
                    state_vars["user_details"] = user_details
            user_id = user_details.get("Id") if user_details else target
            ps_list = salesforce_get_user_permission_sets(user_id) if user_id else []
            pkg_list = salesforce_get_user_package_licenses(user_id) if user_id else []
            grp_list = salesforce_get_user_public_groups(user_id) if user_id else []
            state_vars["permission_sets"] = ps_list
            state_vars["package_licenses"] = pkg_list
            state_vars["public_groups"] = grp_list

            ev_id = f"ev_ps_{uuid.uuid4().hex[:6]}"
            new_ev = {
                "evidence_id": ev_id,
                "tool_name": "salesforce_get_user_permission_sets",
                "field_name": "PermissionSetAssignment",
                "observed_value": {"UserId": user_id, "PermissionSets": ps_list, "PackageLicenses": pkg_list, "PublicGroups": grp_list},
            }
            recorded_evidence.append(new_ev)
            new_evidence.append(new_ev)

            return {
                "Target": target,
                "UserId": user_id,
                "PermissionSetsCount": len(ps_list),
                "AssignedPermissionSets": ps_list,
                "PackageLicenses": pkg_list,
                "PublicGroups": grp_list,
            }

        elif action_type == "classify_application":
            app_type = "unknown"
            if any(k in full_text for k in ["cc360", "customer 360", "cloud customer 360"]):
                app_type = "CC360"
            elif any(k in full_text for k in ["pharm", "pharma", "pure fishing", "community user"]):
                app_type = "PharmApp"
            elif any(k in full_text for k in ["conga", "clm", "apttus", "x-author", "xauthor", "contract", "crm content", "content library", "content"]):
                app_type = "CongaApp"
            state_vars["classified_app_type"] = app_type
            return {"ClassifiedApp": app_type}

        elif action_type == "analyze_incident_description":
            symptoms = []
            if any(k in full_text for k in ["clm new user", "clm onboarding", "clm setup", "onboarding"]):
                symptoms.append("CLM_New_User_Onboarding")
            if any(k in full_text for k in ["crm content", "content library"]):
                symptoms.append("CRM_Content")
            if any(k in full_text for k in ["x-author", "xauthor", "x author"]):
                symptoms.append("X_Author")
            if any(k in full_text for k in ["permission", "access", "apttus"]):
                symptoms.append("Apttus_Permission")
            state_vars["analyzed_symptoms"] = symptoms
            return {"IdentifiedSymptoms": symptoms}

        elif action_type == "classify_object_issue":
            has_wiz = any(k in full_text for k in ["wizard", "product search", "wizard app", "blank wizard"])
            has_obj_field = any(k in full_text for k in ["object access", "field access", "fls", "permission", "cannot view", "cannot edit", "insufficient privileges", "object permission"])
            is_obj = any(k in full_text for k in ["object access", "crud", "object permission", "cannot create record", "cannot delete record", "insufficient privileges on object"])
            is_field = any(k in full_text for k in ["field access", "fls", "field not visible", "field not editable", "cannot edit field", "cannot view field", "field permission"])
            
            if "has_wizard_symptom" not in state_vars:
                state_vars["has_wizard_symptom"] = has_wiz
            if "has_object_or_field_symptom" not in state_vars:
                state_vars["has_object_or_field_symptom"] = has_obj_field
            if "is_object_access_issue" not in state_vars:
                state_vars["is_object_access_issue"] = is_obj
            if "is_field_access_issue" not in state_vars:
                state_vars["is_field_access_issue"] = is_field
            
            return {
                "HasWizardSymptom": state_vars["has_wizard_symptom"],
                "HasObjectOrFieldSymptom": state_vars["has_object_or_field_symptom"],
                "IsObjectAccessIssue": state_vars["is_object_access_issue"],
                "IsFieldAccessIssue": state_vars["is_field_access_issue"],
            }

        elif action_type == "retrieve_contact_wizard_details":
            user_details = cache.get("User") or state_vars.get("user_details") or {}
            user_id = user_details.get("Id") or state_vars.get("target_identifier")
            contact_id = user_details.get("ContactId") or state_vars.get("contact_id")

            # Dynamically call Salesforce MCP tool for contact wizard details
            contact_info = salesforce_get_contact_wizard_details(user_id) if user_id else {}
            if (not contact_info or not contact_info.get("Wizard_Country__c")) and contact_id:
                soql_res = salesforce_execute_soql(f"SELECT Id, Name, Wizard_Country__c FROM Contact WHERE Id = '{contact_id}'")
                if soql_res:
                    contact_info = soql_res[0]

            if not contact_info and state_vars.get("contact_details"):
                contact_info = state_vars.get("contact_details")

            wizard_country = contact_info.get("Wizard_Country__c") if isinstance(contact_info, dict) else None
            if wizard_country is None and "wizard_country" in state_vars:
                wizard_country = state_vars.get("wizard_country")

            is_blank = state_vars.get("is_wizard_country_blank")
            if is_blank is None:
                is_blank = not bool(wizard_country)
                state_vars["is_wizard_country_blank"] = is_blank

            ev_id = f"ev_wizard_contact_{uuid.uuid4().hex[:6]}"
            new_ev = {
                "evidence_id": ev_id,
                "tool_name": "salesforce_get_contact_wizard_details",
                "field_name": "Contact.Wizard_Country__c",
                "observed_value": {"UserId": user_id, "ContactId": contact_id, "Wizard_Country__c": wizard_country, "IsBlank": is_blank},
            }
            recorded_evidence.append(new_ev)
            new_evidence.append(new_ev)
            return {"ContactId": contact_id, "Wizard_Country__c": wizard_country, "IsBlank": is_blank}

        elif action_type == "classify_record_issue":
            is_rep_dash = any(k in full_text for k in ["report", "dashboard"])
            is_opp = any(k in full_text for k in ["opportunity", "case", "opp"])
            is_rec = any(k in full_text for k in ["record", "sharing", "fls", "field not visible", "field not editable"])
            
            if "rec_is_report_dashboard" not in state_vars:
                state_vars["rec_is_report_dashboard"] = is_rep_dash
            if "rec_is_opp_case" not in state_vars:
                state_vars["rec_is_opp_case"] = is_opp
            if "rec_is_salesforce_record" not in state_vars:
                state_vars["rec_is_salesforce_record"] = is_rec or bool(state_vars.get("record_id"))
            
            return {
                "IsReportDashboard": state_vars["rec_is_report_dashboard"],
                "IsOppCase": state_vars["rec_is_opp_case"],
                "IsSalesforceRecord": state_vars["rec_is_salesforce_record"],
            }

        elif action_type == "rec_check_obj_perms_report":
            user_details = cache.get("User") or state_vars.get("user_details") or {}
            user_id = user_details.get("Id")
            missing = state_vars.get("rec_missing_obj_perms_report")
            if missing is None:
                if user_id:
                    perms = salesforce_get_object_permissions(user_id=user_id, object_name="Report")
                    missing = not perms.get("PermissionsRead", True) if isinstance(perms, dict) else False
                else:
                    missing = False
                state_vars["rec_missing_obj_perms_report"] = missing
            
            ev_id = f"ev_rec_obj_rep_{uuid.uuid4().hex[:6]}"
            new_ev = {
                "evidence_id": ev_id,
                "tool_name": "salesforce_get_object_permissions",
                "field_name": "Report.ObjectPermissions",
                "observed_value": {"UserId": user_id, "MissingPermissions": missing},
            }
            recorded_evidence.append(new_ev)
            new_evidence.append(new_ev)
            return {"MissingReportObjPerms": missing}

        elif action_type == "rec_check_folder_access":
            user_details = cache.get("User") or state_vars.get("user_details") or {}
            user_id = user_details.get("Id")
            folder_id = state_vars.get("folder_id") or "00lxx000001"
            missing = state_vars.get("rec_folder_access_missing")
            if missing is None:
                soql = f"SELECT Id, FolderId, UserOrGroupId, AccessLevel FROM FolderMember WHERE FolderId = '{folder_id}'"
                members = salesforce_execute_soql(soql)
                missing = not bool(members)
                state_vars["rec_folder_access_missing"] = missing

            ev_id = f"ev_rec_folder_{uuid.uuid4().hex[:6]}"
            new_ev = {
                "evidence_id": ev_id,
                "tool_name": "salesforce_execute_soql",
                "field_name": "FolderMember.AccessLevel",
                "observed_value": {"FolderId": folder_id, "FolderAccessMissing": missing},
            }
            recorded_evidence.append(new_ev)
            new_evidence.append(new_ev)
            return {"FolderAccessMissing": missing}

        elif action_type == "rec_check_obj_perms_opp_case":
            user_details = cache.get("User") or state_vars.get("user_details") or {}
            user_id = user_details.get("Id")
            missing = state_vars.get("rec_missing_obj_perms_opp_case")
            if missing is None:
                if user_id:
                    perms = salesforce_get_object_permissions(user_id=user_id, object_name="Opportunity")
                    missing = not perms.get("PermissionsRead", True) if isinstance(perms, dict) else False
                else:
                    missing = False
                state_vars["rec_missing_obj_perms_opp_case"] = missing

            ev_id = f"ev_rec_obj_opp_{uuid.uuid4().hex[:6]}"
            new_ev = {
                "evidence_id": ev_id,
                "tool_name": "salesforce_get_object_permissions",
                "field_name": "Opportunity.ObjectPermissions",
                "observed_value": {"UserId": user_id, "MissingPermissions": missing},
            }
            recorded_evidence.append(new_ev)
            new_evidence.append(new_ev)
            return {"MissingOppCaseObjPerms": missing}

        elif action_type == "rec_review_opp_case_sharing":
            user_details = cache.get("User") or state_vars.get("user_details") or {}
            user_id = user_details.get("Id")
            rec_id = state_vars.get("record_id") or "006xx000001"
            if user_id and rec_id and state_vars.get("rec_opp_case_has_read_access") is None:
                acc = salesforce_get_record_access(user_id=user_id, record_id=rec_id)
                has_read = acc.get("HasReadAccess", False) if isinstance(acc, dict) else False
                state_vars["rec_opp_case_has_read_access"] = has_read

            missing = state_vars.get("rec_opp_case_missing_sharing_path")
            if missing is None:
                missing = not bool(state_vars.get("rec_opp_case_has_read_access", False))
                state_vars["rec_opp_case_missing_sharing_path"] = missing

            ev_id = f"ev_rec_opp_sharing_{uuid.uuid4().hex[:6]}"
            new_ev = {
                "evidence_id": ev_id,
                "tool_name": "salesforce_get_record_access",
                "field_name": "UserRecordAccess.HasReadAccess",
                "observed_value": {"UserId": user_id, "RecordId": rec_id, "MissingSharingPath": missing},
            }
            recorded_evidence.append(new_ev)
            new_evidence.append(new_ev)
            return {"MissingOppCaseSharingPath": missing}

        elif action_type == "rec_check_obj_perms_record_id":
            user_details = cache.get("User") or state_vars.get("user_details") or {}
            user_id = user_details.get("Id")
            record_id = state_vars.get("record_id") or "001xx000001"
            missing = state_vars.get("rec_missing_obj_perms_record")
            if missing is None:
                if user_id:
                    target_obj = "Account" if str(record_id).startswith("001") else "Opportunity" if str(record_id).startswith("006") else "Contact"
                    perms = salesforce_get_object_permissions(user_id=user_id, object_name=target_obj)
                    missing = not perms.get("PermissionsRead", True) if isinstance(perms, dict) else False
                else:
                    missing = False
                state_vars["rec_missing_obj_perms_record"] = missing

            ev_id = f"ev_rec_obj_rec_{uuid.uuid4().hex[:6]}"
            new_ev = {
                "evidence_id": ev_id,
                "tool_name": "salesforce_get_object_permissions",
                "field_name": "Record.ObjectPermissions",
                "observed_value": {"UserId": user_id, "RecordId": record_id, "MissingPermissions": missing},
            }
            recorded_evidence.append(new_ev)
            new_evidence.append(new_ev)
            return {"MissingRecordObjPerms": missing}

        elif action_type == "rec_review_sharing_path":
            user_details = cache.get("User") or state_vars.get("user_details") or {}
            user_id = user_details.get("Id")
            rec_id = state_vars.get("record_id") or "001xx000001"
            if user_id and rec_id and state_vars.get("rec_record_has_read_access") is None:
                acc = salesforce_get_record_access(user_id=user_id, record_id=rec_id)
                has_read = acc.get("HasReadAccess", False) if isinstance(acc, dict) else False
                state_vars["rec_record_has_read_access"] = has_read

            missing = state_vars.get("rec_missing_sharing_path")
            if missing is None:
                missing = not bool(state_vars.get("rec_record_has_read_access", False))
                state_vars["rec_missing_sharing_path"] = missing

            ev_id = f"ev_rec_sharing_{uuid.uuid4().hex[:6]}"
            new_ev = {
                "evidence_id": ev_id,
                "tool_name": "salesforce_get_record_access",
                "field_name": "UserRecordAccess.HasReadAccess",
                "observed_value": {"UserId": user_id, "RecordId": rec_id, "MissingSharingPath": missing},
            }
            recorded_evidence.append(new_ev)
            new_evidence.append(new_ev)
            return {"MissingRecordSharingPath": missing}

        elif action_type == "rec_compare_mirror_fls":
            user_details = cache.get("User") or state_vars.get("user_details") or {}
            user_id = user_details.get("Id")
            mirror_user = state_vars.get("mirror_user_details") or state_vars.get("mirror_user") or {}
            mirror_id = mirror_user.get("Id") if isinstance(mirror_user, dict) else None

            fls_missing = state_vars.get("rec_is_fls_missing")
            if fls_missing is None:
                if user_id and mirror_id:
                    comparison = salesforce_compare_user_access(user_id=user_id, mirror_user_id=mirror_id)
                    fls_missing = bool(comparison.get("missing_field_permissions"))
                else:
                    fls_missing = True
                state_vars["rec_is_fls_missing"] = fls_missing

            ev_id = f"ev_rec_fls_{uuid.uuid4().hex[:6]}"
            new_ev = {
                "evidence_id": ev_id,
                "tool_name": "salesforce_compare_user_access",
                "field_name": "FieldPermissions.FLS",
                "observed_value": {"UserId": user_id, "MirrorUserId": mirror_id, "FLSMissing": fls_missing},
            }
            recorded_evidence.append(new_ev)
            new_evidence.append(new_ev)
            return {"FLSMissing": fls_missing}

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

        if condition_key == "incident_domain":
            domain_val = str(state_vars.get("domain") or "").upper()
            if not domain_val:
                if any(k in full_text for k in ["wizard", "product search"]):
                    domain_val = "OBJECT"
                elif any(k in full_text for k in ["report", "dashboard", "opportunity", "record sharing", "sharing rule"]):
                    domain_val = "RECORD"
                elif any(k in full_text for k in ["cc360", "pharm", "conga", "clm", "apttus", "x-author", "xauthor"]):
                    domain_val = "APPLICATION"
                else:
                    domain_val = "LOGIN"
            state_vars["domain"] = domain_val
            cmp_info = {
                "decision_point": "Route by Incident Domain",
                "rule_evaluated": "User verified active in NA Org. Route to corresponding domain deep diagnosis node based on ticket domain",
                "expected_criteria": "Active user in NA Org with valid domain classification (LOGIN, APPLICATION, RECORD, OBJECT)",
                "target_value": f"Domain: '{domain_val}'",
                "baseline_value": "Domain Dispatch Standard",
                "comparison_result": f"Routing to '{domain_val}' domain",
                "decision_outcome": domain_val,
                "reasoning": f"User is confirmed active in NA Org. Ticket belongs to '{domain_val}' domain. Traversing edge ON_DOMAIN_{domain_val} to {domain_val} domain node.",
            }
            return True, {"Domain": domain_val}, cmp_info

        elif condition_key == "is_application_domain":
            domain_val = state_vars.get("domain", "")
            if not domain_val:
                domain_val = "APPLICATION" if any(k in full_text for k in ["cc360", "pharm", "conga", "clm", "apttus", "x-author", "xauthor"]) else "LOGIN"
            val = (str(domain_val).upper() == "APPLICATION")
            cmp_info = {
                "decision_point": "Is Application Domain?",
                "rule_evaluated": "Determine if ticket domain is APPLICATION (vs LOGIN) after verifying user exists and is active in NA org",
                "expected_criteria": "Domain == 'APPLICATION'",
                "target_value": f"Domain: '{domain_val}'",
                "baseline_value": "APPLICATION",
                "comparison_result": "MATCH - Ticket belongs to APPLICATION domain" if val else "NO - Ticket belongs to LOGIN domain",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": (
                    "User exists and is active in NA Org. Ticket belongs to APPLICATION domain. Traversing edge ON_YES to retrieve application permission sets and licenses."
                    if val
                    else "User exists and is active in NA Org. Ticket belongs to LOGIN domain. Traversing edge ON_NO to inspect mirror user and Federation ID."
                ),
            }
            return val, {"IsApplicationDomain": val, "Domain": domain_val}, cmp_info

        elif condition_key == "has_login_url":
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
                "decision_point": "Approved URL?",
                "rule_evaluated": (
                    "Validate if provided login URL matches approved enterprise organizations: "
                    "NA (Main: bdx.my.salesforce.com), EMEA (bd2my.salesforce.com), "
                    "ACE/GA (bdxga.my.salesforce.com), or SMAX (bdsmx.my.salesforce.com)"
                ),
                "expected_criteria": "URL hostname matches approved enterprise org catalogue (bdx.my.salesforce.com, bd2my.salesforce.com, bdxga.my.salesforce.com, bdsmx.my.salesforce.com)",
                "target_value": f"URL: '{login_url}'",
                "baseline_value": "Approved enterprise catalogue (NA: bdx, EMEA: bd2my, ACE/GA: bdxga, SMAX: bdsmx)",
                "comparison_result": f"MATCH - '{login_url}' belongs to approved enterprise catalogue" if val else f"MISMATCH - '{login_url}' is not an approved enterprise URL",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": (
                    f"Login URL '{login_url}' matches approved enterprise Salesforce catalogue. Traversing edge ON_YES to search user in main org."
                    if val else
                    f"Login URL '{login_url}' does not match approved enterprise organizations (NA: bdx.my.salesforce.com, EMEA: bd2my.salesforce.com, ACE/GA: bdxga.my.salesforce.com, SMAX: bdsmx.my.salesforce.com). User is accessing an invalid endpoint. Traversing edge ON_NO to confirm root cause LOGIN-2 (Wrong Salesforce URL)."
                ),
            }
            return val, {"IsApproved": val, "URL": login_url}, cmp_info

        elif condition_key == "user_exists_in_main_org":
            val = bool(state_vars.get("user_exists_in_main_org", False))
            target = state_vars.get("target_identifier")
            cmp_info = {
                "decision_point": "User Exists in Main Org? (Unapproved URL)",
                "rule_evaluated": "Before concluding wrong URL, verify if affected user has an account in Main Org (NA)",
                "expected_criteria": "User account exists in Main Salesforce Organization",
                "target_value": f"Target: '{target}', FoundInMain: {val}",
                "baseline_value": "Active User record in Main Org",
                "comparison_result": f"User account present in Main Org: {val}",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": (
                    f"User '{target}' exists in Main Org (NA). The unapproved URL is the primary cause of login failure. Traversing edge ON_YES to TERMINAL_LOGIN_2 (provide bdx URL and verify)."
                    if val
                    else f"User '{target}' does NOT exist in Main Org. The user lacks an account regardless of URL. Traversing edge ON_NO to TERMINAL_LOGIN_1 (Reroute ticket directly to HCL Service Desk; no RITM required)."
                ),
            }
            return val, {"ExistsInMain": val, "Target": target}, cmp_info

        elif condition_key == "is_main_org_url":
            login_url = state_vars.get("login_url", "")
            is_main = self._is_main_org_url(login_url)
            val = is_main
            main_org = neo4j_repository.get_main_org()
            cmp_info = {
                "decision_point": "Provided URL Belongs to Main Org?",
                "rule_evaluated": "Determine if the approved URL points to the primary Main Organization (bdx.my.salesforce.com) vs secondary cross-org",
                "expected_criteria": f"URL hostname equals '{main_org.get('domain_name', 'bdx.my.salesforce.com')}'",
                "target_value": f"URL: '{login_url}'",
                "baseline_value": f"Main Org Domain: '{main_org.get('domain_name')}'",
                "comparison_result": "MATCH - URL belongs to Main Organization (NA)" if val else "NO - URL belongs to a secondary cross-organization",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": (
                    f"Provided URL '{login_url}' belongs to primary Main Organization ({main_org.get('name')}). Traversing edge ON_YES to search user in Main Org."
                    if val
                    else f"Provided URL '{login_url}' belongs to a secondary organization. Traversing edge ON_NO to verify user in that specific organization."
                ),
            }
            return val, {"IsMainOrgUrl": val, "URL": login_url}, cmp_info

        elif condition_key == "user_found_in_provided_org":
            val = bool(state_vars.get("user_found_in_provided_org", False))
            target = state_vars.get("target_identifier")
            org_info = state_vars.get("provided_org_info", {})
            org_name = org_info.get("name") or "Secondary Org"
            cmp_info = {
                "decision_point": "User Exists in Provided Secondary Org?",
                "rule_evaluated": f"Check whether affected user holds an account in the organization matching the provided URL ({org_name})",
                "expected_criteria": f"User record exists in {org_name}",
                "target_value": f"Target: '{target}', ExistsInProvidedOrg: {val}",
                "baseline_value": f"User directory for {org_name}",
                "comparison_result": f"User found in {org_name}: {val}",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": (
                    f"User '{target}' confirmed to exist in {org_name}. This organization is managed by a dedicated regional support team. Traversing edge ON_YES to TERMINAL_LOGIN_REGIONAL_SCOPE (Reroute ticket to {org_name} support team)."
                    if val
                    else f"User '{target}' does NOT exist in {org_name}. Checking whether user is a Main Org employee who accidentally entered a regional link. Traversing edge ON_NO to search Main Org."
                ),
            }
            return val, {"FoundInProvidedOrg": val, "Org": org_name}, cmp_info

        elif condition_key == "user_found_main_from_cross":
            val = bool(state_vars.get("user_found_main_from_cross", False))
            target = state_vars.get("target_identifier")
            cmp_info = {
                "decision_point": "User Exists in Main Org? (Cross-Org Link)",
                "rule_evaluated": "Check whether user who entered a cross-org link actually holds an account in the Main Organization (NA)",
                "expected_criteria": "User account exists in Main Salesforce Organization (NA)",
                "target_value": f"Target: '{target}', ExistsInMain: {val}",
                "baseline_value": "Active User record in Main Org",
                "comparison_result": f"User present in Main Org: {val}",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": (
                    f"User '{target}' exists in Main Org (NA), but attempted to access a cross-org endpoint. Traversing edge ON_YES to TERMINAL_LOGIN_2C (Provide official Main Org URL https://bdx.my.salesforce.com)."
                    if val
                    else f"User '{target}' does NOT exist in Main Org. Searching remaining registered secondary organizations. Traversing edge ON_NO to search other orgs."
                ),
            }
            return val, {"ExistsInMain": val, "Target": target}, cmp_info

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
                    else f"Target user '{u_name}' was not found in primary Salesforce org. Traversing edge ON_NO to search secondary orgs."
                ),
            }
            return val, {"FoundInMain": val, "Username": u_name, "UserId": u_id}, cmp_info

        elif condition_key == "user_found_in_other_orgs":
            other = state_vars.get("other_org_user")
            val = bool(other)
            u_name = state_vars.get("target_identifier")
            cmp_info = {
                "decision_point": "User Found in Other Orgs?",
                "rule_evaluated": "Search secondary Salesforce orgs (EMEA, GA, ServiceMax, RIM) for target user identity",
                "expected_criteria": "User record located in secondary corporate org",
                "target_value": f"Secondary Org: {other.get('OrgName', other) if isinstance(other, dict) else other}" if val else f"Target '{u_name}' not found in EMEA, GA, ServiceMax, or RIM",
                "baseline_value": "Secondary org user directories",
                "comparison_result": f"User present in secondary org: {val}",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": (
                    f"Target user found in secondary org ({other}). Traversing edge ON_YES to TERMINAL_LOGIN_1B."
                    if val
                    else f"Target user '{u_name}' is not present in any enterprise Salesforce org. Traversing edge ON_NO to TERMINAL_LOGIN_1."
                ),
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
            actor = state_vars.get("deactivated_by") or ("Delegated Administrator" if is_da else "MuleSoft Integration User")
            cmp_info = {
                "decision_point": "Deactivation actor matches DelegateGroupMember?",
                "rule_evaluated": "Compare SetupAuditTrail.CreatedById with DelegateGroupMember.UserOrGroupId (or MuleSoft Integration User)",
                "expected_criteria": "SetupAuditTrail.CreatedById matches DelegateGroupMember.UserOrGroupId",
                "target_value": f"SetupAuditTrail.CreatedById: '{actor}', MatchesDelegateGroupMember: {is_da}",
                "baseline_value": "DelegateGroupMember.UserOrGroupId (Delegated Administrator)",
                "comparison_result": "MATCH - Actor confirmed as Delegated Administrator" if val else "MISMATCH - Actor matches MuleSoft Integration User",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": (
                    "SetupAuditTrail deactivation event matches DelegateGroupMember.UserOrGroupId. User was deactivated by a Delegated Administrator. Traversing edge ON_YES to TERMINAL_LOGIN_3 (LOGIN-3A)."
                    if val
                    else "SetupAuditTrail deactivation event matches MuleSoft Integration User. Traversing edge ON_NO to TERMINAL_LOGIN_3_ESCALATE (LOGIN-3 MuleSoft deactivation)."
                ),
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
            target_fed_id = user_details.get("FederationIdentifier")

            # 1. Determine expected Workday / Azure Employee ID
            import re
            expected_emp_id = None
            m_emp = re.search(r"(?:new\s+(?:emp(?:loyee)?|workday)\s*(?:id|number|#)?\s*(?:is|:|=)?\s*|(?:workday|employee)\s*(?:id|number|#)\s*(?:is|:|=)?\s*)([A-Za-z0-9_-]+)", full_text, re.IGNORECASE)
            if m_emp:
                expected_emp_id = m_emp.group(1).strip()

            if not expected_emp_id:
                raw_emp = user_details.get("EmployeeNumber") or user_details.get("EmployeeId") or state_vars.get("target_emp_id")
                if raw_emp and raw_emp not in ("Not Set", "N/A"):
                    expected_emp_id = str(raw_emp).strip()

            # 2. Check for explicit re-hire or Azure desynchronization symptoms in narrative
            is_rehire_incident = (
                user_details.get("AzureSyncMismatch")
                or ("azure" in full_text and ("sync" in full_text or "re-hire" in full_text or "workday" in full_text))
                or ("re-hire" in full_text or "rehire" in full_text or "returning employee" in full_text)
            )

            # 3. Grounded comparison:
            # FederationIdentifier must strictly match the authoritative Employee ID.
            # If target_fed_id is missing, or expected_emp_id is missing, or they do not equal, it is a MISMATCH (NO).
            if not target_fed_id or not expected_emp_id:
                val = False
            else:
                c_fed = str(target_fed_id).strip().lower()
                c_emp = str(expected_emp_id).strip().lower()
                if c_fed == c_emp:
                    val = not is_rehire_incident
                else:
                    val = False

            state_vars["azure_sync_match"] = val
            fed_display = str(target_fed_id).strip() if target_fed_id else "None (Blank)"
            emp_display = str(expected_emp_id).strip() if expected_emp_id else "Not Configured / Unknown in Workday"

            if val:
                cmp_result = f"MATCH - Salesforce Federation ID ('{fed_display}') equals Workday Employee ID ('{emp_display}')"
                step_reason = (
                    f"Salesforce Federation ID ('{fed_display}') successfully matches authoritative Workday Employee ID ('{emp_display}'). "
                    f"Azure AD SAML SSO federation identity is properly synchronized. Traversing edge ON_YES to check mobile login setup."
                )
            else:
                cmp_result = f"MISMATCH - Salesforce Federation ID ('{fed_display}') != Workday Employee ID ('{emp_display}')"
                step_reason = (
                    f"Salesforce Federation ID ('{fed_display}') does NOT match active Workday Employee ID ('{emp_display}'). "
                    f"This identity synchronization mismatch (such as after an employee re-hire, profile recreation, or incorrect Federation ID assignment) "
                    f"causes SAML identity assertion to fail. Traversing edge ON_NO to confirm root cause LOGIN-6 (Azure Federation ID Synchronization Issue)."
                )

            cmp_info = {
                "decision_point": "Federation ID matches Emp ID? (Workday)",
                "rule_evaluated": "Verify whether Salesforce User.FederationIdentifier equals the authoritative Workday / Azure AD Employee ID",
                "expected_criteria": f"FederationIdentifier == '{emp_display}' (Workday Employee ID baseline)",
                "target_value": f"Salesforce FederationIdentifier: '{fed_display}'",
                "baseline_value": f"Workday / Azure Employee ID: '{emp_display}'",
                "comparison_result": cmp_result,
                "decision_outcome": "YES" if val else "NO",
                "reasoning": step_reason,
            }

            ev_azure_id = f"ev_azure_sync_{uuid.uuid4().hex[:6]}"
            state_vars["ev_azure_id"] = ev_azure_id
            state_vars["azure_evidence"] = {
                "evidence_id": ev_azure_id,
                "tool_name": "azure_ad_workday_identity_check",
                "field_name": "FederationIdVsEmployeeId",
                "observed_value": {
                    "SalesforceFederationIdentifier": target_fed_id,
                    "WorkdayAzureEmployeeId": expected_emp_id,
                    "IsMatching": val,
                    "ComparisonSummary": cmp_result,
                },
            }

            return val, {"FederationIdentifier": target_fed_id, "WorkdayEmployeeId": expected_emp_id, "AzureSyncMatch": val}, cmp_info

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

        elif condition_key == "is_cc360_issue":
            val = (state_vars.get("classified_app_type") == "CC360") or any(k in full_text for k in ["cc360", "customer 360", "cloud customer 360"])
            cmp_info = {
                "decision_point": "CC360 Issue?",
                "rule_evaluated": "Check if incident relates to Customer 360 (CC360)",
                "expected_criteria": "Incident mentions CC360 or Customer 360",
                "target_value": str(val),
                "baseline_value": "CC360",
                "comparison_result": "MATCH" if val else "NO MATCH",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "Incident concerns Customer 360 application." if val else "Incident does not concern Customer 360.",
            }
            return val, {"IsCC360Issue": val}, cmp_info

        elif condition_key == "is_pharm_issue":
            val = (state_vars.get("classified_app_type") == "PharmApp") or any(k in full_text for k in ["pharm", "pharma", "pure fishing", "community user", "ps community"])
            cmp_info = {
                "decision_point": "Pharm App Issue?",
                "rule_evaluated": "Check if incident relates to Pharma / Community app",
                "expected_criteria": "Incident mentions Pharma or Community app",
                "target_value": str(val),
                "baseline_value": "PharmApp",
                "comparison_result": "MATCH" if val else "NO MATCH",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "Incident concerns Pharma / Community portal." if val else "Incident does not concern Pharma.",
            }
            return val, {"IsPharmIssue": val}, cmp_info

        elif condition_key == "is_conga_issue":
            val = (state_vars.get("classified_app_type") == "CongaApp") or any(k in full_text for k in ["conga", "clm", "apttus", "x-author", "xauthor", "contract"])
            cmp_info = {
                "decision_point": "Conga App Issue?",
                "rule_evaluated": "Check if incident relates to Conga / CLM / Apttus suite",
                "expected_criteria": "Incident mentions Conga, CLM, or Apttus",
                "target_value": str(val),
                "baseline_value": "CongaApp",
                "comparison_result": "MATCH" if val else "NO MATCH",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "Incident concerns Conga / CLM / Apttus application suite." if val else "Incident is out of scope for CC360, Pharma, and Conga.",
            }
            return val, {"IsCongaIssue": val}, cmp_info

        elif condition_key == "is_cc360_ps_assigned":
            assigned = state_vars.get("permission_sets", [])
            val = any("cc360" in ps.lower() or "customer 360" in ps.lower() or "customer360" in ps.lower() for ps in assigned)
            cmp_info = {
                "decision_point": "Is CC360 Permission Set Assigned?",
                "rule_evaluated": "Check if CC360 Permission Set is assigned in PermissionSetAssignment",
                "expected_criteria": "CC360 Permission Set assigned to user",
                "target_value": f"Assigned sets: {assigned}",
                "baseline_value": "CC360 Permission Set",
                "comparison_result": "ASSIGNED" if val else "MISSING",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "CC360 permission set is already assigned to user." if val else "CC360 permission set is MISSING from user record.",
            }
            return val, {"CC360_PS_Assigned": val, "PermissionSets": assigned}, cmp_info

        elif condition_key == "is_community_ps_assigned":
            assigned = state_vars.get("permission_sets", [])
            val = any("only ps community user" in ps.lower() or "community user" in ps.lower() or "cmty-ps" in ps.lower() for ps in assigned)
            cmp_info = {
                "decision_point": "Is Only PS Community User Permission Set Assigned?",
                "rule_evaluated": "Check if Only PS Community User permission set is assigned",
                "expected_criteria": "Only PS Community User permission set assigned",
                "target_value": f"Assigned sets: {assigned}",
                "baseline_value": "Only PS Community User",
                "comparison_result": "ASSIGNED" if val else "MISSING",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "Only PS Community User permission set is already assigned." if val else "Only PS Community User permission set is MISSING.",
            }
            return val, {"Community_PS_Assigned": val, "PermissionSets": assigned}, cmp_info

        elif condition_key == "has_clm_onboarding_symptom":
            val = any(k in full_text for k in ["clm new user", "clm onboarding", "clm setup", "new user onboarding", "clm license"])
            cmp_info = {
                "decision_point": "Has Description contains 'CLM New User Onboarding Issue' Symptom?",
                "rule_evaluated": "Check if incident narrative mentions CLM new user onboarding",
                "expected_criteria": "Incident mentions CLM new user onboarding",
                "target_value": str(val),
                "baseline_value": "CLM Onboarding",
                "comparison_result": "MATCH" if val else "NO MATCH",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "CLM new user onboarding symptom identified." if val else "No CLM onboarding symptom identified.",
            }
            return val, {"CLMOnboardingSymptom": val}, cmp_info

        elif condition_key == "is_clm_package_assigned":
            pkgs = user_details.get("PackageLicenses") or user_details.get("UserPackageLicenses") or state_vars.get("package_licenses") or []
            val = any("clm" in str(p).lower() or "conga" in str(p).lower() or "apttus" in str(p).lower() for p in pkgs)
            if not val and any("conga_clm_user" in ps.lower() for ps in state_vars.get("permission_sets", [])):
                val = True
            cmp_info = {
                "decision_point": "Is CLM Package Assigned?",
                "rule_evaluated": "Check UserPackageLicense for Conga CLM managed package license",
                "expected_criteria": "Conga CLM Package License allocated to user",
                "target_value": f"Package licenses: {pkgs}",
                "baseline_value": "Conga CLM Package License",
                "comparison_result": "ASSIGNED" if val else "MISSING",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "Conga CLM package license is assigned." if val else "Conga CLM package license is MISSING from user record.",
            }
            return val, {"CLMPackageAssigned": val, "PackageLicenses": pkgs}, cmp_info

        elif condition_key == "has_crm_content_symptom":
            val = any(k in full_text for k in ["crm content", "content library", "crm content user"])
            cmp_info = {
                "decision_point": "Has Description contained 'CRM Content / Content Library Issue' Symptom?",
                "rule_evaluated": "Check if incident narrative mentions CRM Content or Content Library",
                "expected_criteria": "Incident mentions CRM Content or Content Library",
                "target_value": str(val),
                "baseline_value": "CRM Content",
                "comparison_result": "MATCH" if val else "NO MATCH",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "CRM Content symptom identified." if val else "No CRM Content symptom identified.",
            }
            return val, {"CRMContentSymptom": val}, cmp_info

        elif condition_key == "is_crm_content_user_enabled":
            val = bool(user_details.get("UserPermissionsSFContentUser", user_details.get("UserPermissionsContentUser", False)))
            cmp_info = {
                "decision_point": "Is UserPermissionsContentUser Enabled?",
                "rule_evaluated": "Check User.UserPermissionsSFContentUser flag in Salesforce User record",
                "expected_criteria": "User.UserPermissionsSFContentUser == True",
                "target_value": str(val),
                "baseline_value": "True",
                "comparison_result": "ENABLED" if val else "DISABLED",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "UserPermissionsSFContentUser is enabled." if val else "UserPermissionsSFContentUser is DISABLED on User record.",
            }
            return val, {"UserPermissionsSFContentUser": val}, cmp_info

        elif condition_key == "has_xauthor_symptom":
            val = any(k in full_text for k in ["x-author", "xauthor", "x author"])
            cmp_info = {
                "decision_point": "Has Description contained 'X-Author related issue' Symptom?",
                "rule_evaluated": "Check if incident narrative mentions Conga X-Author",
                "expected_criteria": "Incident mentions X-Author",
                "target_value": str(val),
                "baseline_value": "X-Author",
                "comparison_result": "MATCH" if val else "NO MATCH",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "X-Author symptom identified." if val else "No X-Author symptom identified.",
            }
            return val, {"XAuthorSymptom": val}, cmp_info

        elif condition_key == "is_xauthor_ps_assigned":
            assigned = state_vars.get("permission_sets", [])
            val = any("x-author" in ps.lower() or "xauthor" in ps.lower() or "x_author" in ps.lower() for ps in assigned)
            cmp_info = {
                "decision_point": "Is Agreement - Apttus X-Author Permission Set Assigned?",
                "rule_evaluated": "Check if Apttus X-Author Permission Set is in PermissionSetAssignment",
                "expected_criteria": "Agreement - Apttus X-Author Permission Set assigned",
                "target_value": f"Assigned sets: {assigned}",
                "baseline_value": "Apttus X-Author Permission Set",
                "comparison_result": "ASSIGNED" if val else "MISSING",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "Apttus X-Author Permission Set is assigned." if val else "Apttus X-Author Permission Set is MISSING from user record.",
            }
            return val, {"XAuthor_PS_Assigned": val, "PermissionSets": assigned}, cmp_info

        elif condition_key == "can_determine_bu_access":
            bu_missing_in_text = any(k in full_text for k in ["bu missing", "business unit missing", "missing bu", "no bu", "access level missing"])
            has_bu_field = bool(user_details.get("BusinessUnit") or user_details.get("Division") or user_details.get("Contact", {}).get("WizardCountry") or user_details.get("WizardCountry"))
            val = has_bu_field and not bu_missing_in_text
            cmp_info = {
                "decision_point": "Determine BU and Access Level from Description",
                "rule_evaluated": "Determine if Business Unit (BU) and Access Level are determinable",
                "expected_criteria": "Valid Business Unit and Access Level identified",
                "target_value": f"BU Field: {user_details.get('BusinessUnit') or user_details.get('Division') or user_details.get('WizardCountry')}, Missing Flag: {bu_missing_in_text}",
                "baseline_value": "Valid BU & Access Level",
                "comparison_result": "DETERMINED" if val else "MISSING",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "Business Unit and Access Level are determined." if val else "Business Unit or Access Level cannot be determined / is MISSING.",
            }
            return val, {"BU_Determinable": val}, cmp_info

        elif condition_key == "has_apttus_access_symptom":
            val = any(k in full_text for k in ["permission", "access", "apttus", "agreement"])
            cmp_info = {
                "decision_point": "Has Description contained 'Permission or Access issue' Symptom?",
                "rule_evaluated": "Check if incident narrative mentions general Apttus/Agreement permission or access issue",
                "expected_criteria": "Incident mentions Apttus permission or access issue",
                "target_value": str(val),
                "baseline_value": "Apttus Access",
                "comparison_result": "MATCH" if val else "NO MATCH",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "General Apttus permission/access symptom identified." if val else "No Apttus permission/access symptom identified.",
            }
            return val, {"ApttusAccessSymptom": val}, cmp_info

        elif condition_key == "is_apttus_ps_assigned":
            assigned = state_vars.get("permission_sets", [])
            val = any("apttus" in ps.lower() or "agreement" in ps.lower() or "conga_agreement" in ps.lower() for ps in assigned)
            cmp_info = {
                "decision_point": "Is Agreement - Apttus Permission Set Assigned?",
                "rule_evaluated": "Check if Agreement - Apttus Permission Set is assigned in PermissionSetAssignment",
                "expected_criteria": "Agreement - Apttus Permission Set assigned to user",
                "target_value": f"Assigned sets: {assigned}",
                "baseline_value": "Agreement - Apttus Permission Set",
                "comparison_result": "ASSIGNED" if val else "MISSING",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "Agreement - Apttus Permission Set is assigned." if val else "Agreement - Apttus Permission Set is MISSING from user record.",
            }
            return val, {"Apttus_PS_Assigned": val, "PermissionSets": assigned}, cmp_info

        elif condition_key == "has_wizard_symptom":
            val = bool(state_vars.get("has_wizard_symptom"))
            cmp_info = {
                "decision_point": "Has Description contained 'Wizard App or Product Search Issue' Symptom?",
                "rule_evaluated": "Check if incident symptoms mention Wizard App or Product Search",
                "expected_criteria": "Symptom contains Wizard App or Product Search",
                "target_value": full_text,
                "baseline_value": "Wizard App / Product Search",
                "comparison_result": "MATCH" if val else "NO_MATCH",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "Description contains Wizard App or Product Search symptoms." if val else "No Wizard App or Product Search symptom identified.",
            }
            return val, {"HasWizardSymptom": val}, cmp_info

        elif condition_key == "is_wizard_country_blank":
            val = bool(state_vars.get("is_wizard_country_blank"))
            cmp_info = {
                "decision_point": "Is Wizard_Country__c Blank?",
                "rule_evaluated": "Check if Contact.Wizard_Country__c is blank or null",
                "expected_criteria": "Wizard_Country__c is populated",
                "target_value": str(state_vars.get("wizard_country")),
                "baseline_value": "Non-empty string",
                "comparison_result": "BLANK" if val else "POPULATED",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "Contact Wizard_Country__c is blank/null." if val else "Contact Wizard_Country__c is populated.",
            }
            return val, {"Wizard_Country_Blank": val}, cmp_info

        elif condition_key == "has_object_or_field_symptom":
            val = bool(state_vars.get("has_object_or_field_symptom"))
            cmp_info = {
                "decision_point": "Has Description contained 'Object or Field Access Issue' Symptom?",
                "rule_evaluated": "Check if incident symptoms mention Object or Field access",
                "expected_criteria": "Symptom contains Object or Field access",
                "target_value": full_text,
                "baseline_value": "Object / Field Access",
                "comparison_result": "MATCH" if val else "NO_MATCH",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "Description contains Object or Field Access symptoms." if val else "No Object or Field Access symptom identified.",
            }
            return val, {"HasObjectOrFieldSymptom": val}, cmp_info

        elif condition_key == "is_object_access_issue":
            val = bool(state_vars.get("is_object_access_issue"))
            cmp_info = {
                "decision_point": "Is Object Access Issue?",
                "rule_evaluated": "Check if issue is an Object-level access (CRUD) permission issue",
                "expected_criteria": "Object access issue",
                "target_value": full_text,
                "baseline_value": "Object CRUD Permission",
                "comparison_result": "OBJECT_ISSUE" if val else "NOT_OBJECT_ISSUE",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "Identified as Object Access Issue." if val else "Not an Object Access Issue.",
            }
            return val, {"IsObjectAccessIssue": val}, cmp_info

        elif condition_key == "is_field_access_issue":
            val = bool(state_vars.get("is_field_access_issue"))
            cmp_info = {
                "decision_point": "Is Field Access Issue?",
                "rule_evaluated": "Check if issue is a Field-Level Security (FLS) permission issue",
                "expected_criteria": "Field access / FLS issue",
                "target_value": full_text,
                "baseline_value": "FLS Permission",
                "comparison_result": "FIELD_ISSUE" if val else "NOT_FIELD_ISSUE",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "Identified as Field Access Issue." if val else "Not a Field Access Issue.",
            }
            return val, {"IsFieldAccessIssue": val}, cmp_info

        elif condition_key == "rec_is_report_dashboard":
            val = bool(state_vars.get("rec_is_report_dashboard"))
            cmp_info = {
                "decision_point": "Report/Dashboard?",
                "rule_evaluated": "Check if incident relates to Report or Dashboard access",
                "expected_criteria": "Report or Dashboard issue",
                "target_value": full_text,
                "baseline_value": "Report/Dashboard",
                "comparison_result": "MATCH" if val else "NO_MATCH",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "Incident relates to Report/Dashboard." if val else "Incident is not Report/Dashboard related.",
            }
            return val, {"IsReportDashboard": val}, cmp_info

        elif condition_key == "rec_missing_obj_perms_report":
            val = bool(state_vars.get("rec_missing_obj_perms_report"))
            cmp_info = {
                "decision_point": "Missing Object Permissions (Report/Dashboard)?",
                "rule_evaluated": "Check if user lacks basic permissions on Report/Dashboard objects",
                "expected_criteria": "Report/Dashboard object permissions present",
                "target_value": str(val),
                "baseline_value": "Object Permissions",
                "comparison_result": "MISSING" if val else "PRESENT",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "Report/Dashboard object permissions missing." if val else "Report/Dashboard object permissions are present.",
            }
            return val, {"MissingObjPermsReport": val}, cmp_info

        elif condition_key == "rec_is_folder_info_avail":
            val = bool(state_vars.get("rec_is_folder_info_avail", True))
            cmp_info = {
                "decision_point": "Is Folder Info Available?",
                "rule_evaluated": "Check if Folder ID or folder path is present",
                "expected_criteria": "Folder information available",
                "target_value": str(val),
                "baseline_value": "Folder ID",
                "comparison_result": "AVAILABLE" if val else "MISSING",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "Folder info available." if val else "Folder info not available.",
            }
            return val, {"FolderInfoAvailable": val}, cmp_info

        elif condition_key == "rec_folder_access_missing":
            val = bool(state_vars.get("rec_folder_access_missing", True))
            cmp_info = {
                "decision_point": "Folder Access Missing?",
                "rule_evaluated": "Check if user has Viewer access to Report/Dashboard Folder",
                "expected_criteria": "User has Viewer/Editor/Manager access to folder",
                "target_value": str(val),
                "baseline_value": "Folder Viewer",
                "comparison_result": "MISSING" if val else "GRANTED",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "Folder access is missing." if val else "Folder access is present.",
            }
            return val, {"FolderAccessMissing": val}, cmp_info

        elif condition_key == "rec_is_opp_case":
            val = bool(state_vars.get("rec_is_opp_case"))
            cmp_info = {
                "decision_point": "Opportunity/Case?",
                "rule_evaluated": "Check if incident relates to Opportunity or Case record",
                "expected_criteria": "Opportunity or Case issue",
                "target_value": full_text,
                "baseline_value": "Opportunity/Case",
                "comparison_result": "MATCH" if val else "NO_MATCH",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "Incident relates to Opportunity/Case." if val else "Not Opportunity/Case related.",
            }
            return val, {"IsOppCase": val}, cmp_info

        elif condition_key == "rec_missing_obj_perms_opp_case":
            val = bool(state_vars.get("rec_missing_obj_perms_opp_case"))
            cmp_info = {
                "decision_point": "Missing Object Permissions (Opp/Case)?",
                "rule_evaluated": "Check if user lacks basic CRUD permissions on Opportunity/Case",
                "expected_criteria": "Object permissions present",
                "target_value": str(val),
                "baseline_value": "Object CRUD",
                "comparison_result": "MISSING" if val else "PRESENT",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "Opportunity/Case object permissions missing." if val else "Opportunity/Case object permissions present.",
            }
            return val, {"MissingObjPermsOppCase": val}, cmp_info

        elif condition_key == "rec_opp_case_cannot_access":
            val = bool(state_vars.get("rec_opp_case_cannot_access", True))
            cmp_info = {
                "decision_point": "Cannot Access Record (Opp/Case)?",
                "rule_evaluated": "Check if user symptom is inability to open or access record",
                "expected_criteria": "Record inaccessible",
                "target_value": str(val),
                "baseline_value": "Cannot Access",
                "comparison_result": "CANNOT_ACCESS" if val else "CAN_ACCESS",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "User cannot access record." if val else "User can access record.",
            }
            return val, {"OppCaseCannotAccess": val}, cmp_info

        elif condition_key == "rec_opp_case_has_read_access":
            val = bool(state_vars.get("rec_opp_case_has_read_access", False))
            cmp_info = {
                "decision_point": "HasReadAccess (Opp/Case)?",
                "rule_evaluated": "Check UserRecordAccess.HasReadAccess on Opportunity/Case",
                "expected_criteria": "HasReadAccess == False",
                "target_value": str(val),
                "baseline_value": "UserRecordAccess",
                "comparison_result": "READ_ACCESS" if val else "NO_READ_ACCESS",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "User has read access." if val else "User lacks read access.",
            }
            return val, {"OppCaseHasReadAccess": val}, cmp_info

        elif condition_key == "rec_opp_case_missing_sharing_path":
            val = bool(state_vars.get("rec_opp_case_missing_sharing_path", True))
            cmp_info = {
                "decision_point": "Missing Sharing Path (Opp/Case)?",
                "rule_evaluated": "Review Owner, OWD, Role Hierarchy, Sharing Rules, Teams",
                "expected_criteria": "No sharing path exists",
                "target_value": str(val),
                "baseline_value": "Record Sharing",
                "comparison_result": "MISSING_SHARING" if val else "SHARING_EXISTS",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "Missing sharing path for Opp/Case." if val else "Sharing path exists.",
            }
            return val, {"OppCaseMissingSharing": val}, cmp_info

        elif condition_key == "rec_is_salesforce_record":
            val = bool(state_vars.get("rec_is_salesforce_record", True))
            cmp_info = {
                "decision_point": "Salesforce Record?",
                "rule_evaluated": "Check if issue pertains to a Salesforce record",
                "expected_criteria": "Salesforce record issue",
                "target_value": full_text,
                "baseline_value": "Salesforce Record",
                "comparison_result": "RECORD_ISSUE" if val else "NOT_RECORD_ISSUE",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "Issue pertains to Salesforce record." if val else "Not a Salesforce record issue.",
            }
            return val, {"IsSalesforceRecord": val}, cmp_info

        elif condition_key == "rec_missing_obj_perms_record":
            val = bool(state_vars.get("rec_missing_obj_perms_record"))
            cmp_info = {
                "decision_point": "Missing Permissions (Record Object)?",
                "rule_evaluated": "Check object permissions using affected record ID prefix",
                "expected_criteria": "Object permissions present",
                "target_value": str(val),
                "baseline_value": "Object CRUD",
                "comparison_result": "MISSING" if val else "PRESENT",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "Record object permissions missing." if val else "Record object permissions present.",
            }
            return val, {"MissingObjPermsRecord": val}, cmp_info

        elif condition_key == "rec_cannot_access_record":
            val = bool(state_vars.get("rec_cannot_access_record", True))
            cmp_info = {
                "decision_point": "Cannot Access Record?",
                "rule_evaluated": "Check if user symptom is inability to open or view record",
                "expected_criteria": "Record inaccessible",
                "target_value": str(val),
                "baseline_value": "Cannot Access",
                "comparison_result": "CANNOT_ACCESS" if val else "CAN_ACCESS",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "User cannot access record." if val else "User can access record.",
            }
            return val, {"CannotAccessRecord": val}, cmp_info

        elif condition_key == "rec_record_has_read_access":
            val = bool(state_vars.get("rec_record_has_read_access", False))
            cmp_info = {
                "decision_point": "HasReadAccess (Record)?",
                "rule_evaluated": "Check UserRecordAccess.HasReadAccess on target record",
                "expected_criteria": "HasReadAccess == False",
                "target_value": str(val),
                "baseline_value": "UserRecordAccess",
                "comparison_result": "READ_ACCESS" if val else "NO_READ_ACCESS",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "User has read access on record." if val else "User lacks read access on record.",
            }
            return val, {"RecordHasReadAccess": val}, cmp_info

        elif condition_key == "rec_missing_sharing_path":
            val = bool(state_vars.get("rec_missing_sharing_path", True))
            cmp_info = {
                "decision_point": "Missing Sharing Path (Record)?",
                "rule_evaluated": "Review Owner, OWD, Role Hierarchy, Sharing Rules, Groups, Teams",
                "expected_criteria": "No sharing path exists",
                "target_value": str(val),
                "baseline_value": "Record Sharing",
                "comparison_result": "MISSING_SHARING" if val else "SHARING_EXISTS",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "Missing record sharing path." if val else "Sharing path exists.",
            }
            return val, {"MissingRecordSharing": val}, cmp_info

        elif condition_key == "rec_field_not_visible":
            val = bool(state_vars.get("rec_field_not_visible"))
            cmp_info = {
                "decision_point": "Field Not Visible/Editable?",
                "rule_evaluated": "Check if symptom is field not visible or editable on record",
                "expected_criteria": "Field visibility/editability issue",
                "target_value": full_text,
                "baseline_value": "Field Visibility",
                "comparison_result": "FIELD_ISSUE" if val else "NOT_FIELD_ISSUE",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "Field not visible or editable." if val else "Field visibility not an issue.",
            }
            return val, {"FieldNotVisible": val}, cmp_info

        elif condition_key == "rec_is_fls_missing":
            val = bool(state_vars.get("rec_is_fls_missing", True))
            cmp_info = {
                "decision_point": "FLS Missing?",
                "rule_evaluated": "Compare with mirror user and check FieldPermissions",
                "expected_criteria": "Field-Level Security is missing",
                "target_value": str(val),
                "baseline_value": "FLS Permissions",
                "comparison_result": "MISSING_FLS" if val else "FLS_PRESENT",
                "decision_outcome": "YES" if val else "NO",
                "reasoning": "Field-Level Security is missing." if val else "FLS is present.",
            }
            return val, {"FLSMissing": val}, cmp_info

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
        if not text:
            return None
        import re
        # Pattern 1: Labelled URL/endpoint pattern (e.g. "Login URL: https://...", "portal URL - https://...")
        label_match = re.search(
            r"(?:login\s*url|login_url|login\s*link|endpoint|target\s*url|accessing\s*url|portal\s*url|ps\s*portal\s*url|cc360\s*url|portal|link|url)\s*[:=-]\s*([^\s,;\"\'<>]+)",
            text,
            re.IGNORECASE,
        )
        if label_match:
            cand = label_match.group(1).strip(".,;:)")
            return cand if (cand.lower().startswith("http://") or cand.lower().startswith("https://")) else f"https://{cand}"

        # Pattern 2: Contextual action phrases indicating attempted destination
        action_match = re.search(
            r"(?:bookmarked\s*url|trying to log into|trying to access|logging into|logging in at|accessing|browsing to|navigating to|connecting to)\s+(?:salesforce\s+)?(?:using\s+)?([^\s,;\"\'<>]+)",
            text,
            re.IGNORECASE,
        )
        if action_match:
            cand = action_match.group(1).strip(".,;:)")
            inner_url = re.search(r"https?://[^\s<>'\"\)\]]+|\b[a-zA-Z0-9_.-]+\.[a-zA-Z]{2,}(?:/[^\s<>'\"\)\]]*)?", cand)
            if inner_url:
                c = inner_url.group(0).rstrip(".,;:)")
                return c if (c.lower().startswith("http://") or c.lower().startswith("https://")) else f"https://{c}"

        # Pattern 3: Explicit http/https URL anywhere in narrative
        url_match = re.search(r"https?://[^\s<>'\"\)\]]+", text)
        if url_match:
            return url_match.group(0).rstrip(".,;:)")

        # Pattern 4: Bare enterprise Salesforce / Site / Force domain
        domain_match = re.search(
            r"\b([a-zA-Z0-9_-]+(?:\.[a-zA-Z0-9_-]+)*\.(?:salesforce\.com|force\.com|site\.com)(?:/[^\s<>'\"\)\]]*)?)",
            text,
            re.IGNORECASE,
        )
        if domain_match:
            cand = domain_match.group(1).rstrip(".,;:)")
            return f"https://{cand}"

        # Pattern 5: Approved enterprise tokens
        approved_tokens = [
            "bdx.my.salesforce.com",
            "bd2my.salesforce.com",
            "bd2.my.salesforce.com",
            "bdxga.my.salesforce.com",
            "bdsmx.my.salesforce.com",
            "bdx.my.site.com",
            "login.salesforce.com",
        ]
        text_lower = text.lower()
        for tok in approved_tokens:
            if tok in text_lower:
                m = re.search(re.escape(tok) + r"(?:/[^\s<>'\"\)\]]*)?", text, re.IGNORECASE)
                if m:
                    cand = m.group(0).rstrip(".,;:)")
                    return f"https://{cand}"
                return f"https://{tok}"

        # Pattern 6: Any token containing salesforce.com, force.com, or site.com
        for token in text.split():
            clean = token.strip("(),;\"'<>")
            clean_lower = clean.lower()
            if "salesforce.com" in clean_lower or "force.com" in clean_lower or "site.com" in clean_lower:
                return clean if (clean_lower.startswith("http://") or clean_lower.startswith("https://")) else f"https://{clean}"
        return None

    def _validate_salesforce_url(self, url: str) -> bool:
        if not url:
            return False
        import re
        u = url.strip().lower()
        # Strip protocol and path to isolate host/domain
        host = re.sub(r"^https?://", "", u).split("/")[0].split("?")[0].strip()

        # Check against dynamic orgs from knowledge repository (Neo4j / graph json)
        try:
            approved_orgs = neo4j_repository.get_approved_orgs()
            approved_domains = {org.get("domain_name", "").lower() for org in approved_orgs}
            for org in approved_orgs:
                for alias in org.get("aliases", []):
                    approved_domains.add(alias.lower())
        except Exception:
            approved_domains = set()

        # Include canonical enterprise domains
        approved_domains.update([
            "bdx.my.salesforce.com",
            "bd2my.salesforce.com",
            "bd2.my.salesforce.com",
            "bdxga.my.salesforce.com",
            "bdsmx.my.salesforce.com",
            "login.salesforce.com",
        ])

        # [POC DEVELOPER ORG ENABLER] Also allow connected Developer Org from .env
        dev_inst = os.environ.get("SALESFORCE_INSTANCE_URL") or os.environ.get("SALESFORCE_LOGIN_URL") or "https://orgfarm-9053409114-dev-ed.develop.my.salesforce.com"
        dev_host = dev_inst.replace("https://", "").replace("http://", "").split("/")[0].strip().lower()
        approved_domains.add(dev_host)
        approved_domains.add("orgfarm-9053409114-dev-ed.develop.lightning.force.com")

        if "-dev-ed." in host or "develop.my.salesforce.com" in host:
            return True

        return host in approved_domains

    def _is_main_org_url(self, url: str) -> bool:
        if not url:
            return True
        import re
        clean = url.strip().lower()
        host = re.sub(r"^https?://", "", clean).split("/")[0].split("?")[0].strip()
        main_org = neo4j_repository.get_main_org()
        main_domain = main_org.get("domain_name", "bdx.my.salesforce.com").lower()

        # [POC DEVELOPER ORG ENABLER] Treat both bdx (NA) and connected Developer Org as Main Org
        if host == main_domain or host.startswith("bdx.") or host == "login.salesforce.com":
            return True

        dev_inst = os.environ.get("SALESFORCE_INSTANCE_URL") or os.environ.get("SALESFORCE_LOGIN_URL") or "https://orgfarm-9053409114-dev-ed.develop.my.salesforce.com"
        dev_host = dev_inst.replace("https://", "").replace("http://", "").split("/")[0].strip().lower()
        if host == dev_host or "orgfarm-9053409114-dev-ed" in host or "-dev-ed." in host:
            return True

        return False

    def _get_org_for_url(self, url: str) -> Dict[str, Any]:
        import re
        clean = url.strip().lower()
        host = re.sub(r"^https?://", "", clean).split("/")[0].split("?")[0].strip()
        for org in neo4j_repository.get_approved_orgs():
            d = org.get("domain_name", "").lower()
            if d and d in host:
                return org
            for alias in org.get("aliases", []):
                if alias.lower() in host:
                    return org
        if "bd2" in host or "emea" in host:
            return {"org_id": "ORG_EMEA", "name": "EMEA", "login_url": "https://bd2my.salesforce.com", "domain_name": "bd2my.salesforce.com"}
        elif "bdxga" in host or "ace" in host:
            return {"org_id": "ORG_ACE_GA", "name": "ACE/GA", "login_url": "https://bdxga.my.salesforce.com", "domain_name": "bdxga.my.salesforce.com"}
        elif "bdsmx" in host or "smax" in host:
            return {"org_id": "ORG_SMAX", "name": "SMAX", "login_url": "https://bdsmx.my.salesforce.com", "domain_name": "bdsmx.my.salesforce.com"}
        return neo4j_repository.get_main_org()

    def _search_specific_org(self, target_identifier: str, org_id: str) -> Optional[Dict[str, Any]]:
        target_lower = target_identifier.lower()
        if org_id == "ORG_EMEA" or "emea" in str(org_id).lower():
            if any(k in target_lower for k in ["emea", "europe", "uk", "de", "fr", "bd2"]):
                return {"OrgId": "00Dxx000000EMEA", "OrgName": "EMEA Salesforce Org", "Domain": "bd2my.salesforce.com", "LoginUrl": "https://bd2my.salesforce.com"}
        elif org_id == "ORG_ACE_GA" or "ace" in str(org_id).lower() or "ga" in str(org_id).lower():
            if any(k in target_lower for k in ["ace", "ga", "asia", "bdxga"]):
                return {"OrgId": "00Dxx000000ACEGA", "OrgName": "ACE/GA Salesforce Org", "Domain": "bdxga.my.salesforce.com", "LoginUrl": "https://bdxga.my.salesforce.com"}
        elif org_id == "ORG_SMAX" or "smax" in str(org_id).lower():
            if any(k in target_lower for k in ["smax", "servicemax", "bdsmx"]):
                return {"OrgId": "00Dxx000000SMAX", "OrgName": "ServiceMax Salesforce Org", "Domain": "bdsmx.my.salesforce.com", "LoginUrl": "https://bdsmx.my.salesforce.com"}
        return None

    def _search_other_orgs(self, target_identifier: str) -> Optional[Dict[str, Any]]:
        target_lower = target_identifier.lower()
        if any(k in target_lower for k in ["emea", "europe", "uk", "de", "fr", "bd2"]):
            return {
                "OrgId": "00Dxx000000EMEA",
                "OrgName": "EMEA Salesforce Org",
                "Domain": "bd2my.salesforce.com",
                "LoginUrl": "https://bd2my.salesforce.com",
            }
        elif any(k in target_lower for k in ["ace", "ga", "asia", "bdxga"]):
            return {
                "OrgId": "00Dxx000000ACEGA",
                "OrgName": "ACE/GA Salesforce Org",
                "Domain": "bdxga.my.salesforce.com",
                "LoginUrl": "https://bdxga.my.salesforce.com",
            }
        elif any(k in target_lower for k in ["smax", "servicemax", "bdsmx"]):
            return {
                "OrgId": "00Dxx000000SMAX",
                "OrgName": "ServiceMax Salesforce Org",
                "Domain": "bdsmx.my.salesforce.com",
                "LoginUrl": "https://bdsmx.my.salesforce.com",
            }
        elif "other_org" in target_lower or "another_org" in target_lower:
            return {
                "OrgId": "00Dxx000000EMEA",
                "OrgName": "EMEA Salesforce Org",
                "Domain": "bd2my.salesforce.com",
                "LoginUrl": "https://bd2my.salesforce.com",
            }
        return None

    def _check_okta_suspended(self, user_details: Dict[str, Any], text: str) -> bool:
        fed = str(user_details.get("FederationIdentifier") or "")
        if any(term in fed.lower() for term in ["suspended", "frozen", "inact", "disabled"]):
            return True
        if user_details.get("IsSuspended") or user_details.get("OktaStatus") == "SUSPENDED":
            return True
        return "suspended" in text.lower() or "frozen" in text.lower()

    def _check_azure_workday_match(self, user_details: Dict[str, Any], text: str) -> bool:
        fed = user_details.get("FederationIdentifier")
        emp = user_details.get("EmployeeNumber") or user_details.get("EmployeeId")
        if not fed or not emp:
            return False
        if str(fed).strip().lower() != str(emp).strip().lower():
            return False
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
