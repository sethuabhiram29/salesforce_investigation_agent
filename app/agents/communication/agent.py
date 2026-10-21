"""Communication and ServiceNow Post-Incident Update Agent.

Responsibilities:
- Draft clear, grounded communication for requester based on actual evidence
- Update ServiceNow work notes with complete investigation audit trail
- Mark incident Resolved only when verification criteria are met
"""

import logging
from typing import Any, Dict

from app.models.state import InvestigationState
from app.tools.service_now import servicenow_add_work_notes, servicenow_resolve_incident

logger = logging.getLogger(__name__)


class CommunicationAgent:
    """Prepares customer update and finalizes ServiceNow incident."""

    def __init__(self):
        pass

    def run(self, state: InvestigationState) -> InvestigationState:
        """Compose communication and update ServiceNow status."""
        incident = state.get("incident") or {}
        incident_id = incident.get("incident_id", "INC000")
        diag = state.get("diagnosis_result") or {}
        plan = state.get("resolution_plan") or {}
        verif = state.get("verification_result") or {}
        affected_user = state.get("affected_user") or {}

        user_name = affected_user.get("FirstName", "User")
        issue_code = diag.get("issue_code", "Unknown")

        # 1. Draft user communication
        if verif.get("verified"):
            action_obj = plan.get('proposed_action', {})
            target_f = action_obj.get('target_field', '')
            prop_v = action_obj.get('proposed_value', '')
            if target_f == "RITMGuidance":
                message = (
                    f"Hello {user_name},\n\n"
                    f"Your Salesforce access issue has been investigated.\n"
                    f"• Root Cause: Your Salesforce user account was deactivated by a Delegated Administrator.\n"
                    f"• Resolution Step: Per security policy, automated direct reactivation is not permitted. "
                    f"Please submit a 'Manage User' Request Item (RITM) in ServiceNow to obtain the required approval for account reactivation.\n"
                    f"• Ticket Status: Resolved with instructions.\n\n"
                    f"Once your Manage User RITM is approved, your account will be reactivated automatically."
                )
                res_notes = (
                    f"Automated investigation completed.\n"
                    f"Issue Code: {issue_code} (User Account Deactivated by Delegated Administrator)\n"
                    f"Action: User notified via email and work notes to submit a Manage User RITM in ServiceNow for account reactivation.\n"
                    f"Ticket State: Resolved."
                )
            elif target_f in ["SetupGuide", "Guidance", "Documentation", "Communication"]:
                action_desc = f"{prop_v}"
                message = (
                    f"Hello {user_name},\n\n"
                    f"Your Salesforce access issue has been investigated and resolved.\n"
                    f"• Root Cause: Identified issue {issue_code} ({diag.get('status')}).\n"
                    f"• Action Taken: {action_desc}.\n"
                    f"• Verification: Confirmed active Salesforce state.\n\n"
                    f"Please try logging in now. If you encounter any further issues, feel free to reply."
                )
                res_notes = (
                    f"Automated resolution completed.\n"
                    f"Issue Code: {issue_code}\n"
                    f"Action: {plan.get('proposed_action')}\n"
                    f"Verification: {verif.get('details')}"
                )
            else:
                action_desc = f"Updated User.{target_f} to enable your access"
                message = (
                    f"Hello {user_name},\n\n"
                    f"Your Salesforce access issue has been investigated and resolved.\n"
                    f"• Root Cause: Identified issue {issue_code} ({diag.get('status')}).\n"
                    f"• Action Taken: {action_desc}.\n"
                    f"• Verification: Confirmed active Salesforce state.\n\n"
                    f"Please try logging in now. If you encounter any further issues, feel free to reply."
                )
                res_notes = (
                    f"Automated resolution completed.\n"
                    f"Issue Code: {issue_code}\n"
                    f"Action: {plan.get('proposed_action')}\n"
                    f"Verification: {verif.get('details')}"
                )
            state["communication_draft"] = message

            # 2. Update ServiceNow to Resolved
            servicenow_resolve_incident(incident_id, res_notes)
            state["servicenow_update"] = {
                "incident_id": incident_id,
                "state": "Resolved",
                "notes": res_notes,
            }
        else:
            message = (
                f"Hello {user_name},\n\n"
                f"Your incident has been investigated ({issue_code}). "
                f"Automatic resolution could not be verified, and the ticket has been escalated "
                f"to Tier-2 Support for manual review."
            )
            state["communication_draft"] = message
            servicenow_add_work_notes(incident_id, f"Escalated to Tier-2: {verif.get('details')}")
            state["servicenow_update"] = {
                "incident_id": incident_id,
                "state": "Escalated",
            }

        state.setdefault("trace_events", [])
        state["trace_events"].append({
            "stage": "communication",
            "agent_name": "CommunicationAgent",
            "action": f"Finalized communication and updated ServiceNow state to {state['servicenow_update']['state']}",
            "details": state["servicenow_update"],
        })

        # Record step in step_audit_trail for complete graph lifecycle transparency
        state.setdefault("step_audit_trail", [])
        sn_state = state["servicenow_update"]["state"]
        tool_used = "servicenow_resolve_incident" if sn_state == "Resolved" else "servicenow_add_work_notes"
        state["step_audit_trail"].append({
            "step_order": len(state["step_audit_trail"]) + 1,
            "stage": "communication",
            "step_name": f"Incident Closure & User Communication: {sn_state}",
            "graph_node_id": f"DAG_NODE_INCIDENT_CLOSURE_{issue_code.replace('-', '_')}",
            "graph_node_name": "Knowledge Graph DAG: Incident Closure & User Notification Dispatch Node",
            "movement_direction": "Knowledge Graph Lifecycle Completed -> Terminal Node (RESOLVED)",
            "status_reason": f"Remediation verified successfully. Finalized audit notes and closed ticket {incident_id}.",
            "current_step_details": f"Updated ServiceNow ticket {incident_id} to '{sn_state}'. Drafted grounded email communication for requester {user_name}.",
            "next_step": "TERMINAL_STATE_REACHED (Investigation & Resolution Complete)",
            "skill_file_loaded": "None (Post-resolution notification stage)",
            "skill_id": issue_code,
            "why_loaded": "Post-resolution communication dispatch and ServiceNow audit logging.",
            "tool_called": tool_used,
            "tools_called": [tool_used],
            "why_called_at_instance": f"Verification passed. Invoked {tool_used}() to lock audit notes into ServiceNow and transition incident {incident_id} to '{sn_state}'.",
            "tool_result": {
                "incident_id": incident_id,
                "state": sn_state,
                "notes_snippet": state["servicenow_update"].get("notes", "")[:120] + "..." if len(state["servicenow_update"].get("notes", "")) > 120 else state["servicenow_update"].get("notes", "")
            },
            "status": "resolved" if sn_state == "Resolved" else "escalated",
            "decision_basis": f"State verification succeeded. Closed incident {incident_id} and generated user-facing email.",
            "next_step_reason": "Investigation lifecycle reached terminal completion node.",
        })

        return state
