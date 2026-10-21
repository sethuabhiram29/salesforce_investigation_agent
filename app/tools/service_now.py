"""ServiceNow integration tools (fixture-backed for PoC).

Tools:
- servicenow_get_incident: Retrieve incident details
- servicenow_add_work_notes: Add investigation notes to the incident
- servicenow_resolve_incident: Update incident status and record resolution

All tools are fixture-backed for PoC with in-memory persistence.
"""

from typing import Any, Dict, List, Optional

_SERVICENOW_DB: Dict[str, Dict[str, Any]] = {
    "INC10001": {
        "incident_id": "INC10001",
        "short_description": "User cannot sign in via Okta SSO",
        "description": "User jane.doe@acme.corp reports SAML SSO authentication failure. Federation ID missing.",
        "caller_id": "jane.doe@acme.corp",
        "caller_email": "jane.doe@acme.corp",
        "state": "New",
        "work_notes": [],
        "close_notes": None,
    },
    "INC10002": {
        "incident_id": "INC10002",
        "short_description": "Delegated admin locked out",
        "description": "john.smith@acme.corp cannot sign in to Salesforce",
        "caller_id": "john.smith@acme.corp",
        "caller_email": "john.smith@acme.corp",
        "state": "New",
        "work_notes": [],
        "close_notes": None,
    },
}


def servicenow_get_incident(incident_id: str) -> Dict[str, Any]:
    """Retrieve ServiceNow incident details by ID."""
    return _SERVICENOW_DB.get(incident_id, {
        "incident_id": incident_id,
        "short_description": "Salesforce access issue",
        "description": f"Details for incident {incident_id}",
        "state": "New",
        "work_notes": [],
    })


def servicenow_add_work_notes(incident_id: str, notes: str) -> Dict[str, Any]:
    """Append work notes to a ServiceNow incident."""
    inc = _SERVICENOW_DB.setdefault(incident_id, {"incident_id": incident_id, "work_notes": []})
    inc.setdefault("work_notes", []).append(notes)
    return {"success": True, "incident_id": incident_id, "work_notes_count": len(inc["work_notes"])}


def servicenow_resolve_incident(
    incident_id: str,
    resolution_notes: str,
    close_code: str = "Solved (Permanently)",
) -> Dict[str, Any]:
    """Mark ServiceNow incident as Resolved with resolution code and notes."""
    inc = _SERVICENOW_DB.setdefault(incident_id, {"incident_id": incident_id})
    inc["state"] = "Resolved"
    inc["close_notes"] = resolution_notes
    inc["close_code"] = close_code
    return {
        "success": True,
        "incident_id": incident_id,
        "state": "Resolved",
        "close_code": close_code,
    }


try:
    from langchain_core.tools import tool
    servicenow_get_incident_tool = tool(servicenow_get_incident)
    servicenow_add_work_notes_tool = tool(servicenow_add_work_notes)
    servicenow_resolve_incident_tool = tool(servicenow_resolve_incident)
except ImportError:
    servicenow_get_incident_tool = servicenow_get_incident
    servicenow_add_work_notes_tool = servicenow_add_work_notes
    servicenow_resolve_incident_tool = servicenow_resolve_incident
