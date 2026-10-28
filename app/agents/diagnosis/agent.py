"""Diagnosis Agent implementation.

Responsibilities:
- Load canonical skills for the identified issue domain
- Execute inner tool-calling graph to gather read-only evidence
- Evaluate evidence systematically across candidate scenarios within the domain
- If initial domain hypotheses are contradicted, fallback dynamically to checking other domains
  (LOGIN -> OBJECT -> RECORD -> APPLICATION)
- Distinguish observations, hypotheses, and confirmed findings
- Only confirm when actual evidence satisfies the canonical skill confirmation criteria
"""

import logging
from typing import Any, Dict, List, Optional

from app.agents.diagnosis.structured_flow import StructuredDiagnosisFlow
from app.agents.diagnosis.tool_graph import DiagnosisToolGraph
from app.knowledge.neo4j_repository import neo4j_repository
from app.knowledge.sop_repository import sop_repository
from app.models.schemas import DiagnosisResult
from app.models.state import InvestigationState
from app.utils.explanation import (
    format_evidence_to_human_english,
    format_observed_values_to_human_english,
    generate_step_narrative_explanation,
)

logger = logging.getLogger(__name__)


class DiagnosisAgent:
    """Agent performing evidence-driven diagnostic investigations with cross-domain fallback."""

    # Complete catalog of known root cause scenarios per domain
    DOMAIN_SCENARIOS = {
        "LOGIN": [
            "LOGIN-1", "LOGIN-2", "LOGIN-3", "LOGIN-4",
            "LOGIN-5", "LOGIN-6", "LOGIN-7", "LOGIN-8", "LOGIN-9",
        ],
        "OBJECT": [
            "OBJECT-1", "OBJECT-2", "OBJECT-3",
        ],
        "RECORD": [
            "RECORD-1", "RECORD-2", "RECORD-3",
        ],
        "APPLICATION": [
            "APPLICATION-1", "APPLICATION-2", "APPLICATION-3", "APPLICATION-4",
        ],
    }

    # Fallback domain sequence when initial domain yields no confirmed cause
    DOMAIN_FALLBACKS = {
        "LOGIN": ["OBJECT", "RECORD", "APPLICATION"],
        "OBJECT": ["LOGIN", "RECORD", "APPLICATION"],
        "RECORD": ["OBJECT", "LOGIN", "APPLICATION"],
        "APPLICATION": ["LOGIN", "OBJECT", "RECORD"],
    }

    def __init__(self):
        self.tool_graph = DiagnosisToolGraph()

    def run(self, state: InvestigationState) -> InvestigationState:
        """Execute diagnosis stage on the shared investigation state."""
        state.setdefault("evidence", [])
        state.setdefault("trace_events", [])

        # 1. Determine target user identifier
        affected_user = state.get("affected_user") or {}
        identifier = (
            affected_user.get("Email")
            or affected_user.get("Username")
            or state.get("incident", {}).get("caller_email")
            or state.get("incident", {}).get("description")
        )

        if not identifier:
            state["diagnosis_result"] = {
                "status": "ambiguous_identity",
                "issue_code": None,
                "findings": [],
                "unresolved_questions": ["Could not determine affected user identifier from incident."],
                "recommended_action": "escalate",
            }
            return state

        # 2. Determine initial domain and candidate hypotheses
        initial_domain = state.get("triage_result", {}).get("domain", "LOGIN").upper()
        explicit_candidate = state.get("skill_refs", {}).get("issue_code") or self._select_candidate_from_history(state)

        # Build investigation sequence: starting domain first, then fallback domains
        domains_to_evaluate = [initial_domain] + [
            d for d in self.DOMAIN_FALLBACKS.get(initial_domain, []) if d != initial_domain
        ]

        # Retrieve structured Neo4j investigation graph plan for domain
        domain_plan = neo4j_repository.get_domain_plan(initial_domain)
        state["neo4j_plan"] = domain_plan

        logger.info(
            "DiagnosisAgent starting investigation for %s. Neo4j plan (%s): %d scenarios. Sequence: %s",
            identifier,
            domain_plan.get("source"),
            len(domain_plan.get("scenarios", [])),
            domains_to_evaluate,
        )

        target_object = (
            state.get("triage_result", {}).get("extracted_entities", {}).get("objects", ["Account"])[0]
            if state.get("triage_result", {}).get("extracted_entities", {}).get("objects")
            else "Account"
        )
        rec_ids = state.get("triage_result", {}).get("extracted_entities", {}).get("record_ids", [])
        target_rec_id = rec_ids[0] if rec_ids else None

        incident_obj = state.get("incident", {})
        context = {
            "target_object": target_object,
            "target_record_id": target_rec_id,
            "mirror_user": state.get("mirror_user"),
            "incident_summary": incident_obj.get("short_description", ""),
            "incident_description": incident_obj.get("description", ""),
        }

        confirmed_result: Optional[DiagnosisResult] = None
        confirmed_issue_code: Optional[str] = None
        attempted_issues: List[str] = []

        # 3. Systematic Hypothesis Evaluation & Fallback Loop
        state.setdefault("step_audit_trail", [])
        evidence_cache = state.setdefault("evidence_cache", {})

        # Structured Flow: For LOGIN issues, follow the exact flowchart decision tree knowledge graph
        if initial_domain == "LOGIN":
            structured_flow = StructuredDiagnosisFlow()
            diagnosis_result, new_evidence, traversal_steps = structured_flow.execute(
                target_identifier=identifier,
                context=context,
                existing_evidence=state.get("evidence", []),
                evidence_cache=evidence_cache,
            )
            if new_evidence:
                state["evidence"].extend(new_evidence)

            # Record every single graph traversal step from the flowchart into step_audit_trail
            if traversal_steps:
                state["step_audit_trail"].extend(traversal_steps)

            issue_code = diagnosis_result.issue_code
            attempted_issues.append(issue_code)

            if diagnosis_result.status == "confirmed":
                state["step_audit_trail"].append({
                    "stage": "root_cause_confirmation",
                    "step_order": len(state.get("step_audit_trail", [])) + 1,
                    "step_name": f"Terminal Node Reached: Confirmed Root Cause ({issue_code})",
                    "graph_node_id": f"STRUCTURED_FLOW_CONFIRM_{issue_code.replace('-', '_')}",
                    "graph_node_name": f"Structured Flow Confirmation: {issue_code}",
                    "movement_direction": f"Lock Root Cause [{issue_code}] -----> Advance to Resolution Planning",
                    "status": "confirmed",
                    "status_reason": f"Flowchart decision tree successfully satisfied all criteria for root cause: {issue_code}",
                    "current_step_details": diagnosis_result.decision_basis,
                    "why_step_taken": "All upstream criteria in flowchart satisfied; locking root cause",
                    "next_step": f"Load canonical resolution skill file for '{issue_code}' in Resolution Planning stage",
                    "next_step_reason": f"Root cause '{issue_code}' is permanently confirmed. Now loading canonical skill file to formulate remediation proposal.",
                    "skill_file_loaded": None,
                    "why_loaded": "Skill loaded strictly in Resolution Planning after root cause confirmation per governance rules.",
                    "tool_called": "StructuredDiagnosisFlow",
                    "tools_called": [e.get("tool_name") for e in new_evidence],
                    "tool_result": diagnosis_result.observed_values,
                    "observed_summary": diagnosis_result.observed_values,
                    "expected_criteria": diagnosis_result.expected_criteria,
                    "observed_values": diagnosis_result.observed_values,
                    "comparison_summary": diagnosis_result.comparison_summary,
                    "decision_basis": diagnosis_result.decision_basis,
                })

                state["diagnosis_result"] = diagnosis_result.dict()
                state["incident_domain"] = "LOGIN"

                state.setdefault("trace_events", []).append({
                    "stage": "diagnosis",
                    "agent_name": "DiagnosisAgent",
                    "action": f"Confirmed root cause as {issue_code} via Structured Flow",
                    "details": {
                        "status": "confirmed",
                        "issue_code": issue_code,
                        "flowchart": "Login Issues Decision Tree",
                    },
                })
                return state
            else:
                state["step_audit_trail"].append({
                    "stage": "diagnosis",
                    "step_order": len(state.get("step_audit_trail", [])) + 1,
                    "step_name": f"Terminal Node Reached: Escalation Required ({issue_code})",
                    "graph_node_id": f"STRUCTURED_FLOW_ESCALATE_{issue_code.replace('-', '_')}",
                    "graph_node_name": f"Structured Flow Escalation: {issue_code}",
                    "movement_direction": "Advance to Orchestrator Escalation Node",
                    "status": "escalation_required",
                    "status_reason": diagnosis_result.decision_basis,
                    "current_step_details": diagnosis_result.decision_basis,
                    "why_step_taken": "Flowchart reached an escalation boundary node requiring human review",
                    "next_step": "Route to Tier-2 human support team per escalation policy",
                    "next_step_reason": "Escalation node reached in flowchart.",
                    "skill_file_loaded": None,
                    "why_loaded": "Escalation node reached in flowchart.",
                    "tool_called": "StructuredDiagnosisFlow",
                    "tools_called": [e.get("tool_name") for e in new_evidence],
                    "tool_result": diagnosis_result.observed_values,
                    "observed_summary": diagnosis_result.observed_values,
                    "expected_criteria": diagnosis_result.expected_criteria,
                    "observed_values": diagnosis_result.observed_values,
                    "comparison_summary": diagnosis_result.comparison_summary,
                    "decision_basis": diagnosis_result.decision_basis,
                })

                state["diagnosis_result"] = diagnosis_result.dict()
                state["incident_domain"] = "LOGIN"

                state.setdefault("trace_events", []).append({
                    "stage": "diagnosis",
                    "agent_name": "DiagnosisAgent",
                    "action": f"Escalated incident via Structured Flow ({issue_code})",
                    "details": {
                        "status": "escalation_required",
                        "issue_code": issue_code,
                        "flowchart": "Login Issues Decision Tree",
                    },
                })
                return state

        historical_ranks = self._rank_candidates_from_history(state, initial_domain)
        logger.info("DiagnosisAgent extracted historical candidates: %s", historical_ranks)

        for domain_idx, domain in enumerate(domains_to_evaluate):
            # Candidates ordering:
            # 1. Historical candidates strictly from this domain first (ranked top-to-bottom by similarity)
            # 2. Complete check: Followed by ALL remaining root causes belonging to this domain catalog from user's Excel SOP KB
            domain_catalog = sop_repository.get_domain_catalog(domain) or list(self.DOMAIN_SCENARIOS.get(domain, []))
            domain_hist_ranks = self._rank_candidates_from_history(state, domain)
            domain_hist_codes = [c[0] for c in domain_hist_ranks if self._code_to_domain(c[0]) == domain]

            ordered_candidates = []
            for code in domain_hist_codes:
                if self._code_to_domain(code) == domain and code not in ordered_candidates:
                    ordered_candidates.append(code)
            for code in domain_catalog:
                if code not in ordered_candidates:
                    ordered_candidates.append(code)

            if domain != initial_domain:
                boundary_notice = (
                    f"[DOMAIN BOUNDARY TRANSITION] All candidate hypotheses in classified domain '{initial_domain}' "
                    f"were systematically evaluated against live Salesforce evidence and contradicted/exhausted. "
                    f"Traversing cross-domain fallback directed edge in Knowledge Graph to evaluate secondary domain '{domain}'."
                )
                print("\n" + "=" * 80 + f"\n{boundary_notice}\n" + "=" * 80 + "\n", flush=True)
                logger.info(boundary_notice)

            for rank_idx, issue_code in enumerate(ordered_candidates, 1):
                if issue_code in attempted_issues:
                    continue
                attempted_issues.append(issue_code)

                # No skill file is loaded during candidate evaluation phase
                is_from_hist = any(c[0] == issue_code for c in domain_hist_ranks)
                hist_match = next((c for c in domain_hist_ranks if c[0] == issue_code), None)
                if is_from_hist and hist_match:
                    eval_reason = f"Candidate #{rank_idx} ({issue_code}) from '{domain}' historical precedents top-to-bottom (similarity: {int(hist_match[2]*100)}%)"
                else:
                    eval_reason = f"Candidate #{rank_idx} ({issue_code}) from complete '{domain}' domain root cause catalog"

                logger.info("DiagnosisAgent evaluating candidate hypothesis: %s (Domain: %s)", issue_code, domain)

                diagnosis_result, new_evidence = self.tool_graph.run(
                    candidate_issue_code=issue_code,
                    target_identifier=identifier,
                    context=context,
                    existing_evidence=state.get("evidence", []),
                    evidence_cache=evidence_cache,
                )

                if new_evidence:
                    state["evidence"].extend(new_evidence)

                tools_used = [e.get("tool_name") for e in new_evidence] if new_evidence else ["Retrieved from Evidence Cache (User Object)"]

                evidence_summary = {
                    f.claim: f.evidence_refs for f in diagnosis_result.findings
                } if diagnosis_result.findings else {"status": diagnosis_result.status}

                exp_criteria = diagnosis_result.expected_criteria or f"Confirmation criteria for {issue_code}"
                obs_vals = diagnosis_result.observed_values or (evidence_cache.get("User") or {})
                comp_summary = diagnosis_result.comparison_summary or diagnosis_result.status.upper()
                dec_basis = diagnosis_result.decision_basis or (
                    f"Candidate {issue_code} evaluated against observed evidence."
                )

                # Determine next candidate for explicit next-step explanation
                remaining = [c for c in ordered_candidates[rank_idx:] if c not in attempted_issues]
                next_cand_str = remaining[0] if remaining else (
                    f"next fallback domain sequence ({domains_to_evaluate[domain_idx+1]})"
                    if domain_idx + 1 < len(domains_to_evaluate) else "incident escalation"
                )

                graph_node_id = f"DAG_NODE_{domain}_EVAL_{issue_code.replace('-', '_')}"
                graph_node_name = f"Knowledge Graph DAG: Candidate Evaluation ({issue_code})"

                # Generate comprehensive, plain-English human explanation
                user_obj = evidence_cache.get("User") or state.get("affected_user") or {}
                narrative = generate_step_narrative_explanation(
                    issue_code=issue_code,
                    domain=domain,
                    status=diagnosis_result.status,
                    observed_values=obs_vals,
                    expected_criteria=exp_criteria,
                    target_identifier=identifier,
                    user_details=user_obj,
                    hist_match=hist_match,
                    rank_idx=rank_idx,
                    next_cand_str=next_cand_str,
                    decision_basis=dec_basis,
                    comparison_summary=comp_summary,
                )

                current_step_details = narrative["what_we_did"]
                obs_english_summary = narrative["evidence_english"]

                if diagnosis_result.status == "confirmed":
                    match_next_step = narrative["next_step_action"]
                    movement_direction = f"Branch [MATCH] -> Directed Edge ROOT_CAUSE_CONFIRMED -> [Root Cause Confirmation Gate: {issue_code}]"
                    status_reason = narrative["reasoning"]

                    rc_decision_basis = (
                        f"Root cause confirmed as {issue_code} based on 100% matched criteria against live Salesforce record: "
                        f"{narrative['comparison_english']} Zero contradictions found."
                    )
                    rc_next_step = (
                        f"Root cause locked as {issue_code}. Advancing to Resolution Planning stage to load the canonical "
                        f"resolution skill file for {issue_code} and plan required remediation fields without violating candidate-evaluation boundary rules."
                    )
                    rc_movement_direction = f"Directed Edge ROOT_CAUSE_CONFIRMED -> [Resolution Planning DAG: Load Canonical Skill for {issue_code}]"
                    rc_status_reason = f"Prerequisite root cause confirmation stage complete. Formally locked cause before loading resolution skill."

                    # Print formatted candidate evaluation block in plain conversational English (NO raw JSON)
                    eval_banner = (
                        "\n" + "=" * 80 + "\n"
                        f"[CANDIDATE EVALUATION] Candidate: {issue_code} (Domain: {domain})\n"
                        f"- Knowledge Graph Node:    {graph_node_id} ({graph_node_name})\n"
                        f"- Traversal Direction:     {movement_direction}\n"
                        f"- Why Step Was Taken:      {narrative['why_step_taken']}\n"
                        f"- What We Did in Step:     {narrative['what_we_did']}\n"
                        f"- Salesforce Evidence:     {obs_english_summary}\n"
                        f"- Expected vs Observed:    {narrative['comparison_english']}\n"
                        f"- Analytical Reasoning:    {narrative['reasoning']}\n"
                        f"- Selected Next Step:      {match_next_step}\n"
                        + "=" * 80
                    )
                    logger.info(eval_banner)
                    print(eval_banner, flush=True)

                    # Audit trail for Candidate Evaluation
                    state["step_audit_trail"].append({
                        "stage": "diagnosis",
                        "step_order": len(state["step_audit_trail"]) + 1,
                        "step_name": f"Candidate Evaluation: {issue_code}",
                        "graph_node_id": graph_node_id,
                        "graph_node_name": graph_node_name,
                        "movement_direction": movement_direction,
                        "status_reason": status_reason,
                        "why_step_taken": narrative["why_step_taken"],
                        "current_step_details": current_step_details,
                        "next_step": match_next_step,
                        "skill_file_loaded": "None (No skill file needed during candidate evaluation)",
                        "skill_id": None,
                        "why_loaded": f"{eval_reason}. Evaluated directly against observed evidence without loading skill file.",
                        "tools_called": tools_used,
                        "expected_criteria": exp_criteria,
                        "observed_values": obs_vals,
                        "observed_summary": obs_english_summary,
                        "comparison": narrative["comparison_english"],
                        "decision_basis": narrative["reasoning"],
                        "next_step_reason": match_next_step,
                        "evidence_checked": evidence_summary,
                        "conclusion": f"[MATCH] Observed Salesforce evidence satisfies all criteria for candidate {issue_code}.",
                        "status": "matched",
                    })

                    # Print formatted Root Cause Confirmation block
                    rc_graph_node_id = f"DAG_NODE_{domain}_CONFIRM_ROOT_CAUSE"
                    rc_graph_node_name = f"Knowledge Graph DAG: Root Cause Confirmation Gate ({issue_code})"
                    rc_banner = (
                        "\n" + "=" * 80 + "\n"
                        f"[ROOT CAUSE CONFIRMED] Issue: {issue_code} (Domain: {domain})\n"
                        f"- Graph Node:          {rc_graph_node_id} ({rc_graph_node_name})\n"
                        f"- Traversal Direction: {rc_movement_direction}\n"
                        f"- Status Reason:       {rc_status_reason}\n"
                        f"- Confirmed Root Cause: {issue_code}\n"
                        f"- Salesforce Evidence: {obs_english_summary}\n"
                        f"- Grounded Reasoning:  {narrative['reasoning']}\n"
                        f"- Next Stage:          {rc_next_step}\n"
                        + "=" * 80
                    )
                    logger.info(rc_banner)
                    print(rc_banner, flush=True)

                    # SEPARATE STAGE: Confirmation of Root Cause
                    state["step_audit_trail"].append({
                        "stage": "root_cause_confirmation",
                        "step_order": len(state["step_audit_trail"]) + 1,
                        "step_name": f"Root Cause Confirmed: {issue_code}",
                        "graph_node_id": rc_graph_node_id,
                        "graph_node_name": rc_graph_node_name,
                        "movement_direction": rc_movement_direction,
                        "status_reason": rc_status_reason,
                        "why_step_taken": "Separate prerequisite confirmation stage to lock the verified cause before loading resolution skills.",
                        "current_step_details": f"Formally locked root cause as {issue_code} based on 100% criteria match against live Salesforce record: {obs_english_summary}.",
                        "next_step": rc_next_step,
                        "skill_file_loaded": "None (Prerequisite stage: Root cause confirmed prior to loading resolution skill)",
                        "skill_id": issue_code,
                        "why_loaded": "Confirmation of root cause is a separate prerequisite stage before loading skill file for resolution steps.",
                        "tools_called": ["root_cause_confirmation_gate"],
                        "expected_criteria": exp_criteria,
                        "observed_values": obs_vals,
                        "observed_summary": obs_english_summary,
                        "comparison": narrative["comparison_english"],
                        "decision_basis": rc_decision_basis,
                        "next_step_reason": rc_next_step,
                        "evidence_checked": evidence_summary,
                        "conclusion": f"[ROOT CAUSE CONFIRMED] Verified root cause: {issue_code}. Confirmation stage complete. Next stage will load canonical skill file for resolution planning.",
                        "status": "confirmed",
                    })

                    confirmed_result = diagnosis_result
                    confirmed_issue_code = issue_code
                    logger.info("DiagnosisAgent confirmed root cause in separate confirmation stage: %s", issue_code)
                    break

                elif diagnosis_result.status == "contradicted":
                    status = "contradicted"
                    next_step = narrative["next_step_action"]
                    movement_direction = f"Branch [CONTRADICTED] -> Directed Edge HAS_NEXT_CANDIDATE -> [{next_cand_str}] in domain {domain}"
                    status_reason = narrative["reasoning"]

                    eval_banner = (
                        "\n" + "=" * 80 + "\n"
                        f"[CANDIDATE EVALUATION] Candidate: {issue_code} (Domain: {domain})\n"
                        f"- Knowledge Graph Node:    {graph_node_id} ({graph_node_name})\n"
                        f"- Traversal Direction:     {movement_direction}\n"
                        f"- Why Step Was Taken:      {narrative['why_step_taken']}\n"
                        f"- What We Did in Step:     {narrative['what_we_did']}\n"
                        f"- Salesforce Evidence:     {obs_english_summary}\n"
                        f"- Expected vs Observed:    {narrative['comparison_english']}\n"
                        f"- Analytical Reasoning:    {narrative['reasoning']}\n"
                        f"- Selected Next Step:      {next_step}\n"
                        + "=" * 80
                    )
                    logger.info(eval_banner)
                    print(eval_banner, flush=True)

                    state["step_audit_trail"].append({
                        "stage": "diagnosis",
                        "step_order": len(state["step_audit_trail"]) + 1,
                        "step_name": f"Candidate Evaluation: {issue_code}",
                        "graph_node_id": graph_node_id,
                        "graph_node_name": graph_node_name,
                        "movement_direction": movement_direction,
                        "status_reason": status_reason,
                        "why_step_taken": narrative["why_step_taken"],
                        "current_step_details": current_step_details,
                        "next_step": next_step,
                        "skill_file_loaded": "None (No skill file needed during candidate evaluation)",
                        "skill_id": None,
                        "why_loaded": f"{eval_reason}. If evidence differs, advance to next candidate without loading skill file.",
                        "tools_called": tools_used,
                        "expected_criteria": exp_criteria,
                        "observed_values": obs_vals,
                        "observed_summary": obs_english_summary,
                        "comparison": narrative["comparison_english"],
                        "decision_basis": narrative["reasoning"],
                        "next_step_reason": next_step,
                        "evidence_checked": evidence_summary,
                        "conclusion": f"[CONTRADICTED] {narrative['reasoning']}",
                        "status": status,
                    })
                else:
                    status = diagnosis_result.status
                    next_step = narrative["next_step_action"]
                    movement_direction = f"Branch [INSUFFICIENT] -> Directed Edge HAS_NEXT_CANDIDATE -> [{next_cand_str}] in domain {domain}"
                    status_reason = narrative["reasoning"]

                    eval_banner = (
                        "\n" + "=" * 80 + "\n"
                        f"[CANDIDATE EVALUATION] Candidate: {issue_code} (Domain: {domain})\n"
                        f"- Knowledge Graph Node:    {graph_node_id} ({graph_node_name})\n"
                        f"- Traversal Direction:     {movement_direction}\n"
                        f"- Why Step Was Taken:      {narrative['why_step_taken']}\n"
                        f"- What We Did in Step:     {narrative['what_we_did']}\n"
                        f"- Salesforce Evidence:     {obs_english_summary}\n"
                        f"- Expected vs Observed:    {narrative['comparison_english']}\n"
                        f"- Analytical Reasoning:    {narrative['reasoning']}\n"
                        f"- Selected Next Step:      {next_step}\n"
                        + "=" * 80
                    )
                    logger.info(eval_banner)
                    print(eval_banner, flush=True)

                    state["step_audit_trail"].append({
                        "stage": "diagnosis",
                        "step_order": len(state["step_audit_trail"]) + 1,
                        "step_name": f"Candidate Evaluation: {issue_code}",
                        "graph_node_id": graph_node_id,
                        "graph_node_name": graph_node_name,
                        "movement_direction": movement_direction,
                        "status_reason": status_reason,
                        "why_step_taken": narrative["why_step_taken"],
                        "current_step_details": current_step_details,
                        "next_step": next_step,
                        "skill_file_loaded": "None (No skill file needed during candidate evaluation)",
                        "skill_id": None,
                        "why_loaded": f"{eval_reason}. Checking against observed evidence.",
                        "tools_called": tools_used,
                        "expected_criteria": exp_criteria,
                        "observed_values": obs_vals,
                        "observed_summary": obs_english_summary,
                        "comparison": narrative["comparison_english"],
                        "decision_basis": narrative["reasoning"],
                        "next_step_reason": next_step,
                        "evidence_checked": evidence_summary,
                        "conclusion": f"Status: {diagnosis_result.status}. Insufficient evidence to confirm.",
                        "status": status,
                    })

                if diagnosis_result.status == "ambiguous_identity":
                    state["diagnosis_result"] = diagnosis_result.model_dump()
                    return state

            if confirmed_result:
                break

            # If all candidates in this domain were exhausted without confirmation, record domain fallback edge
            if not confirmed_result and domain_idx + 1 < len(domains_to_evaluate):
                next_dom = domains_to_evaluate[domain_idx + 1]
                edge_reason = (
                    f"All {len(ordered_candidates)} root causes in domain '{domain}' were systematically evaluated against "
                    f"Salesforce evidence and contradicted. Advancing along Knowledge Graph cross-domain fallback directed edge "
                    f"to evaluate secondary domain '{next_dom}'."
                )
                state["step_audit_trail"].append({
                    "stage": "diagnosis",
                    "step_order": len(state["step_audit_trail"]) + 1,
                    "step_name": f"Domain Fallback Traversal: {domain} -> {next_dom}",
                    "graph_node_id": f"DAG_EDGE_FALLBACK_{domain}_{next_dom}",
                    "graph_node_name": f"Knowledge Graph Cross-Domain Fallback Edge ({domain} -> {next_dom})",
                    "movement_direction": f"Cross-Domain Directed Edge -> [Domain: {next_dom}]",
                    "status_reason": edge_reason,
                    "current_step_details": f"Exhausted candidate sequence {ordered_candidates} in '{domain}'. Zero confirmed causes.",
                    "next_step": f"Evaluate candidates in secondary domain '{next_dom}'",
                    "skill_file_loaded": "None",
                    "skill_id": None,
                    "why_loaded": "Domain boundary transition in Knowledge Graph.",
                    "tools_called": [],
                    "expected_criteria": f"Confirmed root cause within '{domain}'",
                    "observed_values": {"evaluated_domain": domain, "candidates_checked": ordered_candidates},
                    "comparison": f"[EXHAUSTED] No candidate matched in {domain}",
                    "decision_basis": edge_reason,
                    "next_step_reason": f"Investigate next domain '{next_dom}' in fallback hierarchy.",
                    "evidence_checked": {"domain": domain, "next_domain": next_dom},
                    "conclusion": edge_reason,
                    "status": "fallback_transition",
                })


        # 4. Finalize diagnosis outcome
        if confirmed_result and confirmed_issue_code:
            state["skill_refs"] = {
                "issue_code": confirmed_issue_code,
                "file_path": None,  # Skill file will be loaded in resolution planning stage
                "title": f"Scenario {confirmed_issue_code}",
                "stage": "diagnosis",
                "version": 1,
            }
            state["diagnosis_result"] = confirmed_result.model_dump()
            action_desc = f"Confirmed root cause: {confirmed_issue_code} (Root cause confirmed before loading resolution skill)"
        else:
            final_diag = DiagnosisResult(
                status="insufficient_evidence",
                issue_code=None,
                findings=[],
                unresolved_questions=[
                    f"Evaluated candidates {attempted_issues} across domains {domains_to_evaluate} without finding confirmed cause."
                ],
                recommended_action="escalate",
            )
            state["diagnosis_result"] = final_diag.model_dump()
            action_desc = f"Contradicted/insufficient evidence across {attempted_issues}; escalated"

        # 5. Audit trace event
        state["trace_events"].append({
            "stage": "diagnosis",
            "agent_name": "DiagnosisAgent",
            "action": action_desc,
            "details": {
                "status": state["diagnosis_result"]["status"],
                "issue_code": state["diagnosis_result"].get("issue_code"),
                "attempted_scenarios": attempted_issues,
                "evidence_collected_count": len(state.get("evidence", [])),
                "neo4j_plan_source": domain_plan.get("source", "neo4j"),
                "neo4j_scenarios_count": len(domain_plan.get("scenarios", [])),
            },
        })

        return state

    def _code_to_domain(self, code: str) -> str:
        if "LOGIN" in code:
            return "LOGIN"
        if "OBJECT" in code:
            return "OBJECT"
        if "RECORD" in code:
            return "RECORD"
        if "APPLICATION" in code:
            return "APPLICATION"
        return "LOGIN"

    def _map_root_cause_to_code(self, rc_text: str, domain: str = "") -> Optional[str]:
        """Dynamically map a historical incident root cause text or code to a canonical scenario issue code."""
        if not rc_text:
            return None
        text = rc_text.upper()

        # Direct match for LOGIN-3 / LOGIN-3A
        if "LOGIN-3A" in text or "LOGIN-003A" in text:
            return "LOGIN-3"

        for code in [
            "LOGIN-1", "LOGIN-2", "LOGIN-3", "LOGIN-4", "LOGIN-5",
            "LOGIN-6", "LOGIN-7", "LOGIN-8", "LOGIN-9",
            "OBJECT-1", "OBJECT-2", "OBJECT-3",
            "RECORD-1", "RECORD-2", "RECORD-3",
            "APPLICATION-1", "APPLICATION-2", "APPLICATION-3", "APPLICATION-4",
        ]:
            if code in text:
                return code

        t_lower = rc_text.lower()

        # 2. Semantic matching based on scenario catalog
        # Mobile app
        if any(w in t_lower for w in ["mobile", "mobile app", "phone", "ios", "android"]):
            return "LOGIN-8"
        # User account not available / not found / account creation
        if any(w in t_lower for w in ["user account not available", "account not available", "user not found", "account creation", "not present in any system"]):
            return "LOGIN-1"
        # Deactivated user (standard or delegated administrator)
        if any(w in t_lower for w in ["delegated admin", "delegated administrator", "deactivated", "inactive", "switched off", "account locked"]):
            return "LOGIN-3"
        # Azure sync (Re-hire)
        if any(w in t_lower for w in ["azure", "re-hire", "rehire"]):
            return "LOGIN-6"
        # CIAM sync
        if any(w in t_lower for w in ["ciam", "external user"]):
            return "LOGIN-7"
        # Federation ID suspended
        if any(w in t_lower for w in ["suspended", "freeze", "lockout"]):
            return "LOGIN-5"
        # Federation ID missing / blank
        if any(w in t_lower for w in ["federation id", "federationidentifier", "saml", "sso"]):
            return "LOGIN-4"
        # Wrong URL
        if any(w in t_lower for w in ["wrong url", "url address", "wrong login url"]):
            return "LOGIN-2"
        # Work order email
        if any(w in t_lower for w in ["work order", "closing work order"]):
            return "LOGIN-9"

        # Object domain
        if any(w in t_lower for w in ["wizard", "wizard app", "wizard country"]):
            return "OBJECT-1"
        if any(w in t_lower for w in ["object permission", "permissionsedit", "edit permission", "edit/delete records"]):
            return "OBJECT-2"
        if any(w in t_lower for w in ["product search"]):
            return "OBJECT-3"

        # Record domain
        if any(w in t_lower for w in ["report", "dashboard"]):
            return "RECORD-1"
        if any(w in t_lower for w in ["opportunity", "case"]):
            return "RECORD-2"
        if any(w in t_lower for w in ["record access", "access a record"]):
            return "RECORD-3"

        # Application domain
        if "cc360" in t_lower:
            return "APPLICATION-1"
        if "pharm" in t_lower:
            return "APPLICATION-2"
        if "conga" in t_lower or "clm" in t_lower:
            return "APPLICATION-3"
        if "showpad" in t_lower:
            return "APPLICATION-4"

        return None

    def _rank_candidates_from_history(self, state: InvestigationState, domain: str) -> List[Tuple[str, str, float]]:
        """Extract ranked candidate issue codes and descriptions from past similar cases.
        Guarantees strict domain isolation: only returns candidates belonging to the target domain.
        Returns list of tuples: (issue_code, description, similarity)
        """
        dom = (domain or state.get("triage_result", {}).get("domain", "")).upper()
        past_cases = state.get("historical_cases", [])

        # Filter cases strictly by target domain
        if dom:
            filtered_cases = [c for c in past_cases if str(c.get("domain", "")).upper() == dom]
        else:
            filtered_cases = list(past_cases)

        if not filtered_cases and dom:
            filtered_cases = sop_repository.get_historical_incidents(dom)
            if not filtered_cases:
                try:
                    from tests.fixtures.historical_incidents import FIXTURE_HISTORICAL_INCIDENTS
                    filtered_cases = [c for c in FIXTURE_HISTORICAL_INCIDENTS if str(c.get("domain", "")).upper() == dom]
                except Exception:
                    filtered_cases = []

        candidates = []
        seen = set()
        for case in filtered_cases:
            rc = str(case.get("root_cause", ""))
            sim = float(case.get("similarity", 0.85))
            desc = case.get("summary") or rc
            code = self._map_root_cause_to_code(rc, dom)
            if code and code not in seen:
                if not dom or self._code_to_domain(code) == dom:
                    candidates.append((code, desc, sim))
                    seen.add(code)
        return candidates

    def _select_candidate_from_history(self, state: InvestigationState) -> Optional[str]:
        """Heuristic to select top candidate issue code from domain-filtered past cases."""
        dom = state.get("triage_result", {}).get("domain", "LOGIN").upper()
        ranked = self._rank_candidates_from_history(state, dom)
        return ranked[0][0] if ranked else None
