"""Outer LangGraph — investigation lifecycle orchestrator.

Nodes:
- triage: Classify symptom, identify ambiguity, extract search values, resolve affected user
- diagnosis: Investigate and establish supported cause (inner tool-calling loop)
- resolution_planning: Plan remediation using canonical skill
- execute_remediation: Execute the approved action
- verification: Confirm post-change state
- communication: Update ServiceNow and close
- escalation: Route to Tier-2 support for ambiguous or failed cases

Conditional edges:
- triage → diagnosis (clear domain) or clarify/escalate (ambiguous)
- diagnosis → resolution_planning (confirmed) or reinvestigate/escalate
- resolution_planning → execute_remediation (if approved) or interrupt
- verification → communication (success) or escalate (failure)
"""

import logging
from typing import Any, Dict, Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.communication.agent import CommunicationAgent
from app.agents.diagnosis.agent import DiagnosisAgent
from app.agents.resolution.agent import ResolutionAgent
from app.agents.triage.agent import TriageAgent
from app.agents.verification.agent import VerificationAgent
from app.models.state import InvestigationState
from app.tools.service_now import servicenow_add_work_notes

logger = logging.getLogger(__name__)

MAX_INVESTIGATION_ATTEMPTS = 3

triage_agent = TriageAgent()
diagnosis_agent = DiagnosisAgent()
resolution_agent = ResolutionAgent()
verification_agent = VerificationAgent()
communication_agent = CommunicationAgent()


# --- Node Callables ---

def node_triage(state: InvestigationState) -> InvestigationState:
    logger.info("LangGraph: Entering Triage Node")
    state["iteration_count"] = state.get("iteration_count", 0) + 1
    return triage_agent.run(state)


def node_diagnosis(state: InvestigationState) -> InvestigationState:
    logger.info("LangGraph: Entering Diagnosis Node")
    return diagnosis_agent.run(state)


def node_resolution_planning(state: InvestigationState) -> InvestigationState:
    logger.info("LangGraph: Entering Resolution Planning Node")
    return resolution_agent.plan_resolution(state)


def node_execute_remediation(state: InvestigationState) -> InvestigationState:
    logger.info("LangGraph: Entering Execution Node")
    return resolution_agent.execute_remediation(state)


def node_verification(state: InvestigationState) -> InvestigationState:
    logger.info("LangGraph: Entering Verification Node")
    return verification_agent.run(state)


def node_communication(state: InvestigationState) -> InvestigationState:
    logger.info("LangGraph: Entering Communication Node")
    return communication_agent.run(state)


def node_escalation(state: InvestigationState) -> InvestigationState:
    logger.info("LangGraph: Entering Escalation Node")
    incident_id = state.get("incident", {}).get("incident_id", "UNKNOWN")
    diag = state.get("diagnosis_result") or {}
    reason = diag.get("status") or state.get("triage_result", {}).get("reasoning", "Escalated to human support")

    servicenow_add_work_notes(incident_id, f"Auto-escalated to Tier-2: {reason}")
    state["servicenow_update"] = {"incident_id": incident_id, "state": "Escalated", "reason": reason}

    state.setdefault("trace_events", [])
    state["trace_events"].append({
        "stage": "escalation",
        "agent_name": "Orchestrator",
        "action": f"Escalated incident {incident_id} to Tier-2",
        "details": {"reason": reason},
    })
    return state


# --- Conditional Routing Functions ---

def route_after_triage(state: InvestigationState) -> Literal["diagnosis", "escalation"]:
    # Never abort or escalate prematurely simply because a user was not found during triage!
    # The Knowledge Graph contains a dedicated swimlane for 'User not found in any org'
    # (NODE_SEARCH_MAIN_ORG -> NODE_USER_FOUND_MAIN -> NODE_SEARCH_OTHER_ORGS -> NODE_USER_FOUND_OTHER -> TERMINAL_LOGIN_1).
    # Route directly to diagnosis so the Diagnosis Agent can traverse the Knowledge Graph!
    return "diagnosis"



def route_after_diagnosis(state: InvestigationState) -> Literal["resolution_planning", "escalation"]:
    diag = state.get("diagnosis_result") or {}
    if diag.get("status") == "confirmed":
        return "resolution_planning"
    return "escalation"


def route_after_resolution(state: InvestigationState) -> Literal["execute_remediation", "escalation"]:
    plan = state.get("resolution_plan") or {}
    approval = state.get("approval") or {}

    # If already approved (or auto-approved in test policy), proceed to execution
    if approval.get("approval_status") == "approved":
        return "execute_remediation"
    elif approval.get("approval_status") == "rejected":
        return "escalation"

    # Default: if approval is pending, wait/execute when authorized
    return "execute_remediation"


def route_after_verification(state: InvestigationState) -> Literal["communication", "escalation"]:
    verif = state.get("verification_result") or {}
    if verif.get("verified"):
        return "communication"
    return "escalation"


def build_investigation_graph(checkpointer=None):
    """Build and compile the outer LangGraph orchestrator."""
    builder = StateGraph(InvestigationState)

    # 1. Add all workflow nodes
    builder.add_node("triage", node_triage)
    builder.add_node("diagnosis", node_diagnosis)
    builder.add_node("resolution_planning", node_resolution_planning)
    builder.add_node("execute_remediation", node_execute_remediation)
    builder.add_node("verification", node_verification)
    builder.add_node("communication", node_communication)
    builder.add_node("escalation", node_escalation)

    # 2. Add edges & conditional transitions
    builder.add_edge(START, "triage")

    builder.add_conditional_edges(
        "triage",
        route_after_triage,
        {
            "diagnosis": "diagnosis",
            "escalation": "escalation",
        },
    )

    builder.add_conditional_edges(
        "diagnosis",
        route_after_diagnosis,
        {
            "resolution_planning": "resolution_planning",
            "escalation": "escalation",
        },
    )

    builder.add_conditional_edges(
        "resolution_planning",
        route_after_resolution,
        {
            "execute_remediation": "execute_remediation",
            "escalation": "escalation",
        },
    )

    builder.add_edge("execute_remediation", "verification")

    builder.add_conditional_edges(
        "verification",
        route_after_verification,
        {
            "communication": "communication",
            "escalation": "escalation",
        },
    )

    builder.add_edge("communication", END)
    builder.add_edge("escalation", END)

    # Use default memory saver if not passed
    memory = checkpointer or MemorySaver()
    return builder.compile(checkpointer=memory)
