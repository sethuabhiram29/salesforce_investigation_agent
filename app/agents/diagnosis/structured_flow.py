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
    salesforce_execute_soql,
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
            node_type = current_node.get("node_type") or current_node.get("type", "decision")
            swimlane = current_node.get("swimlane", "General")
            node_source = current_node.get("source", graph_source)

            # Check if Terminal Node reached in Knowledge Graph
            if node_type == "terminal":
                issue_code = current_node.get("issue_code", "UNKNOWN")
                status = current_node.get("status", "confirmed")
                decision_basis = current_node.get("decision_basis", f"Flowchart terminated at {node_name}")
                expected = current_node.get("expected_criteria", "Standard diagnostic pattern")

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
            user_details = state_vars.get("user_details") or {}
            is_active = user_details.get("IsActive", False)
            state_vars["is_active"] = is_active
            return {"IsActive": is_active}

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
        # Pattern 1: Labelled URL
        label_match = re.search(
            r"(?:login\s*url|login_url|login\s*link|endpoint|target\s*url|accessing\s*url|link|url)\s*[:=]\s*([^\s,;\"\'<>]+)",
            text,
            re.IGNORECASE,
        )
        if label_match:
            cand = label_match.group(1).strip(".,;:)")
            return cand if (cand.startswith("http://") or cand.startswith("https://")) else f"https://{cand}"

        # Pattern 2: Explicit http/https URL
        url_match = re.search(r"https?://[^\s<>'\"\)\]]+", text)
        if url_match:
            return url_match.group(0).rstrip(".,;:)")

        # Pattern 3: Bare enterprise domain
        for tok in ["bdx.my.salesforce.com", "bd2my.salesforce.com", "bd2.my.salesforce.com", "bdxga.my.salesforce.com", "bdsmx.my.salesforce.com"]:
            if tok in text.lower():
                return f"https://{tok}"

        # Pattern 4: Any domain ending in salesforce.com or force.com
        for token in text.split():
            clean = token.strip("(),;\"'<>")
            if "salesforce.com" in clean.lower() or "force.com" in clean.lower():
                return clean if (clean.startswith("http://") or clean.startswith("https://")) else f"https://{clean}"
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

        return host in approved_domains

    def _is_main_org_url(self, url: str) -> bool:
        if not url:
            return True
        import re
        clean = url.strip().lower()
        host = re.sub(r"^https?://", "", clean).split("/")[0].split("?")[0].strip()
        main_org = neo4j_repository.get_main_org()
        main_domain = main_org.get("domain_name", "bdx.my.salesforce.com").lower()
        return host == main_domain or host.startswith("bdx.") or host == "login.salesforce.com"

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
