"""ServiceNow integration tools for dynamic investigation and resolution workflows.

These tools allow any agent (Triage, Diagnosis, Resolution, Verification, Communication)
to dynamically inspect, log findings, reroute tickets, record RITM guidance, and update
work notes on the active ServiceNow incident at any point in the investigation lifecycle.

Tools:
- servicenow_get_incident: Retrieve incident metadata and caller information.
- servicenow_add_work_notes: Append dynamic investigation findings, audit entries, or milestone updates to ticket work notes.
- servicenow_reroute_incident: Reroute an incident to a dedicated assignment group (e.g., HCL Service Desk, Regional Support, CIAM, MuleSoft).
- servicenow_record_ritm_guidance: Record a formal Manage User RITM requirement in work notes.
- servicenow_get_work_notes: Inspect full history of work notes logged on the incident.
- servicenow_resolve_incident: Mark incident as Resolved with formal resolution notes and close code.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_SERVICENOW_DB: Dict[str, Dict[str, Any]] = {
    "INC10001": {
        "incident_id": "INC10001",
        "short_description": "User cannot sign in via Okta SSO",
        "description": "User jane.doe@acme.corp reports SAML SSO authentication failure. Federation ID missing.",
        "caller_id": "jane.doe@acme.corp",
        "caller_email": "jane.doe@acme.corp",
        "state": "New",
        "assignment_group": "Salesforce Support Tier 1",
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
        "assignment_group": "Salesforce Support Tier 1",
        "work_notes": [],
        "close_notes": None,
    },
}


def servicenow_get_incident(incident_id: str) -> Dict[str, Any]:
    """Retrieve ServiceNow incident details by ID.

    Use this tool to fetch the current state, caller information, description,
    and assigned group of an incident.
    """
    return _SERVICENOW_DB.get(incident_id, {
        "incident_id": incident_id,
        "short_description": "Salesforce access issue",
        "description": f"Details for incident {incident_id}",
        "state": "New",
        "assignment_group": "Salesforce Support Tier 1",
        "work_notes": [],
    })


def servicenow_add_work_notes(
    incident_id: str,
    notes: str,
    stage: Optional[str] = None,
    agent_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Append dynamic investigation findings, audit entries, or milestone updates to ticket work notes.

    Agents can invoke this tool whenever important observations or actions occur:
    e.g., identity resolution milestones, cross-org search results, audit log findings,
    remediation execution results, or verification status.

    Parameters:
    - incident_id: The ServiceNow incident identifier (e.g. 'INC10001').
    - notes: The detailed text to append to the incident work notes.
    - stage: Optional lifecycle stage (e.g. 'triage', 'diagnosis', 'resolution', 'verification').
    - agent_name: Optional name of the calling agent (e.g. 'DiagnosisAgent', 'TriageAgent').
    """
    inc = _SERVICENOW_DB.setdefault(incident_id, {
        "incident_id": incident_id,
        "work_notes": [],
        "state": "In Progress",
    })

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    header = f"[{timestamp}]"
    if agent_name:
        header += f" [{agent_name}]"
    if stage:
        header += f" (Stage: {stage.upper()})"

    formatted_note = f"{header}\n{notes.strip()}"
    inc.setdefault("work_notes", []).append(formatted_note)

    return {
        "success": True,
        "incident_id": incident_id,
        "work_notes_count": len(inc["work_notes"]),
        "latest_note": formatted_note,
        "stage": stage,
        "agent_name": agent_name,
    }


def servicenow_reroute_incident(
    incident_id: str,
    assignment_group: str,
    notes: str,
    agent_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Reroute a ServiceNow ticket to a dedicated assignment group and update work notes.

    Use this tool when an incident must be handed off to another support team:
    - 'HCL Service Desk': When the caller account cannot be located in any Salesforce org.
    - 'Salesforce Regional Support': When the user account belongs to an alternate regional org (e.g. EMEA, GA, ServiceMax).
    - 'CIAM Support Team': When external CIAM synchronization is required.
    - 'MuleSoft Support Team': When automated MuleSoft integration deactivations require integration review.
    - 'Tier-2 Salesforce Engineering': When complex out-of-scope issues occur.

    Parameters:
    - incident_id: The ServiceNow incident identifier.
    - assignment_group: Target assignment group for the reroute.
    - notes: Specific routing rationale and findings to document in work notes.
    - agent_name: Optional calling agent name.
    """
    inc = _SERVICENOW_DB.setdefault(incident_id, {"incident_id": incident_id, "work_notes": []})
    inc["assignment_group"] = assignment_group
    inc["state"] = "Rerouted"

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    prefix = f"[{timestamp}] [REROUTE -> {assignment_group}]"
    if agent_name:
        prefix += f" [{agent_name}]"
    routing_note = f"{prefix}\n{notes.strip()}"
    inc["work_notes"].append(routing_note)

    return {
        "success": True,
        "incident_id": incident_id,
        "state": "Rerouted",
        "assignment_group": assignment_group,
        "routing_note": routing_note,
    }


def servicenow_record_ritm_guidance(
    incident_id: str,
    ritm_type: str,
    notes: str,
    agent_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Record a formal Manage User RITM requirement in ticket work notes.

    Use this tool when corporate governance requires the user to submit a ServiceNow
    Request Item (RITM) for account reactivation (LOGIN-3A) or FederationIdentifier
    correction (LOGIN-5).

    Parameters:
    - incident_id: The ServiceNow incident identifier.
    - ritm_type: e.g. 'Manage User - Account Reactivation' or 'Manage User - Federation ID Correction'.
    - notes: Guidance notes explaining why RITM is required.
    - agent_name: Optional calling agent name.
    """
    inc = _SERVICENOW_DB.setdefault(incident_id, {"incident_id": incident_id, "work_notes": []})

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    prefix = f"[{timestamp}] [RITM REQUIRED: {ritm_type}]"
    if agent_name:
        prefix += f" [{agent_name}]"
    ritm_note = f"{prefix}\n{notes.strip()}"
    inc["work_notes"].append(ritm_note)

    return {
        "success": True,
        "incident_id": incident_id,
        "ritm_type": ritm_type,
        "ritm_note": ritm_note,
    }


def servicenow_get_work_notes(incident_id: str) -> List[str]:
    """Retrieve all work notes logged on a ServiceNow incident."""
    inc = _SERVICENOW_DB.get(incident_id, {})
    return list(inc.get("work_notes", []))


def servicenow_resolve_incident(
    incident_id: str,
    resolution_notes: str,
    close_code: str = "Solved (Permanently)",
    agent_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Mark ServiceNow incident as Resolved with resolution code and notes.

    Use this tool during the communication & incident closure stage after
    state verification has confirmed successful remediation.
    """
    inc = _SERVICENOW_DB.setdefault(incident_id, {"incident_id": incident_id, "work_notes": []})
    inc["state"] = "Resolved"
    inc["close_notes"] = resolution_notes
    inc["close_code"] = close_code

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    header = f"[{timestamp}] [INCIDENT RESOLVED]"
    if agent_name:
        header += f" [{agent_name}]"
    inc["work_notes"].append(f"{header}\n{resolution_notes.strip()}")

    return {
        "success": True,
        "incident_id": incident_id,
        "state": "Resolved",
        "close_code": close_code,
        "close_notes": resolution_notes,
    }


# Export LangChain Tool wrappers if langchain is installed
try:
    from langchain_core.tools import tool

    servicenow_get_incident_tool = tool(servicenow_get_incident)
    servicenow_add_work_notes_tool = tool(servicenow_add_work_notes)
    servicenow_reroute_incident_tool = tool(servicenow_reroute_incident)
    servicenow_record_ritm_guidance_tool = tool(servicenow_record_ritm_guidance)
    servicenow_get_work_notes_tool = tool(servicenow_get_work_notes)
    servicenow_resolve_incident_tool = tool(servicenow_resolve_incident)
except ImportError:
    servicenow_get_incident_tool = servicenow_get_incident
    servicenow_add_work_notes_tool = servicenow_add_work_notes
    servicenow_reroute_incident_tool = servicenow_reroute_incident
    servicenow_record_ritm_guidance_tool = servicenow_record_ritm_guidance
    servicenow_get_work_notes_tool = servicenow_get_work_notes
    servicenow_resolve_incident_tool = servicenow_resolve_incident


def get_servicenow_tools() -> List[Any]:
    """Return the complete toolkit of ServiceNow dynamic investigation and resolution tools."""
    return [
        servicenow_get_incident_tool,
        servicenow_add_work_notes_tool,
        servicenow_reroute_incident_tool,
        servicenow_record_ritm_guidance_tool,
        servicenow_get_work_notes_tool,
        servicenow_resolve_incident_tool,
    ]
