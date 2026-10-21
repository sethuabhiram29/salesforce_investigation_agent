"""Main orchestrator agent entry point.

Builds and compiles the outer LangGraph, wires up all agents,
and provides the invoke/resume interface for running end-to-end investigations.
"""

import uuid
from typing import Any, Dict, Optional

from app.models.state import InvestigationState
from app.orchestrator.graph import build_investigation_graph


class InvestigationOrchestrator:
    """High-level facade over the LangGraph support investigation pipeline."""

    def __init__(self, checkpointer=None):
        self.graph = build_investigation_graph(checkpointer=checkpointer)

    def run_investigation(
        self,
        incident: Dict[str, Any],
        auto_approve: bool = False,
        thread_id: Optional[str] = None,
    ) -> InvestigationState:
        """Execute the full investigation workflow for an incoming ServiceNow incident.

        Parameters:
        - incident: Dictionary containing incident_id, short_description, description, etc.
        - auto_approve: If True (e.g. for authorized automated tests), marks approval as approved.
        - thread_id: Optional thread ID for LangGraph checkpoint persistence.
        """
        t_id = thread_id or f"thread_{uuid.uuid4().hex[:8]}"
        config = {"configurable": {"thread_id": t_id}}

        initial_state: InvestigationState = {
            "incident": incident,
            "evidence": [],
            "historical_cases": [],
            "trace_events": [],
            "iteration_count": 0,
        }

        if auto_approve:
            initial_state["approval"] = {"approval_status": "approved"}

        final_state = self.graph.invoke(initial_state, config=config)
        return final_state
