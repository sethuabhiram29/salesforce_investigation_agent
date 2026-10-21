"""Historical incident retrieval tools for LangGraph agents.

Tools:
- search_similar_incidents: Find past incidents by description/domain similarity
- search_sop_procedures: Retrieve standard operating procedure (SOP) guidance

These tools wrap PostgresIncidentRepository for LLM consumption.
Results are advisory context to guide hypotheses, never final confirmation of root cause.
"""

from typing import Any, Dict, List, Optional

try:
    from langchain_core.tools import tool
except ImportError:
    def tool(fn):
        fn.is_tool = True
        return fn

from app.knowledge.postgres_repository import PostgresIncidentRepository

_default_repo = PostgresIncidentRepository()


@tool
def search_similar_incidents(
    summary: str,
    description: str,
    domain: Optional[str] = None,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """Search historical incident database for past resolved cases matching symptoms.

    Parameters:
    - summary: Short title or summary of the reported incident.
    - description: Full details and error messages reported.
    - domain: Optional domain filter ('Login', 'Object', 'Record', 'Application').
    - top_k: Number of relevant cases to return (default 5).

    Returns a list of past incidents with their root causes, resolutions, and similarity scores.
    """
    return _default_repo.search_historical_incidents(
        summary=summary,
        description=description,
        domain=domain,
        top_k=top_k,
    )


@tool
def search_sop_procedures(
    query: str,
    domain: Optional[str] = None,
    top_k: int = 3,
) -> List[Dict[str, Any]]:
    """Search Standard Operating Procedures (SOPs) for step-by-step resolution guidance.

    Parameters:
    - query: Specific symptom, error text, or procedure being investigated.
    - domain: Optional domain filter ('Login', 'Object', 'Record', 'Application').
    - top_k: Number of SOP records to retrieve (default 3).
    """
    return _default_repo.search_sops(
        query=query,
        domain=domain,
        top_k=top_k,
    )


def fetch_historical_context_for_state(
    incident_summary: str,
    incident_description: str,
    domain: Optional[str] = None,
    top_k: int = 3,
) -> List[Dict[str, Any]]:
    """Helper invoked automatically during graph preflight/diagnosis without user input.

    Pulls top relevant historical incidents based on the incoming ServiceNow ticket.
    """
    return _default_repo.search_historical_incidents(
        summary=incident_summary,
        description=incident_description,
        domain=domain,
        top_k=top_k,
    )
