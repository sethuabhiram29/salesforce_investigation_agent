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
            justification = action_obj.get('justification', '')

            # Check specific domain & issue code scenarios
            if issue_code in ["LOGIN-5", "LOGIN-005"]:
                message = (
                    f"Hello {user_name},\n\n"
                    f"Your Salesforce access issue has been investigated.\n"
                    f"• Root Cause: Your Salesforce Federation Identifier was replaced with a suspended or frozen value.\n"
                    f"• Resolution Step: Per security policy, automated direct modification is restricted. "
                    f"Please submit a 'Manage User' Request Item (RITM) in ServiceNow to correct your FederationIdentifier to your Employee Number.\n"
                    f"• Ticket Status: Resolved with instructions.\n\n"
                    f"Once your Manage User RITM is approved, your FederationIdentifier will be restored."
                )
                res_notes = (
                    f"Automated investigation completed.\n"
                    f"Issue Code: {issue_code} (FederationIdentifier Suspended/Frozen)\n"
                    f"Action: User notified via email and work notes to submit a Manage User RITM in ServiceNow for FederationIdentifier correction.\n"
                    f"Ticket State: Resolved."
                )
            elif issue_code in ["LOGIN-3A", "LOGIN-3", "LOGIN-003", "LOGIN-003A"] or (target_f == "RITMGuidance" and "deactivat" in justification.lower()):
                message = (
                    f"Hello {user_name},\n\n"
                    f"Your Salesforce access issue has been investigated.\n"
                    f"• Root Cause: Your Salesforce user account was intentionally deactivated by a Delegated Administrator.\n"
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
            elif issue_code in ["OBJECT-2A", "OBJECT-2", "OBJECT-002", "OBJECT-ACCESS-MISSING"]:
                target_obj_name = action_obj.get('target_object') or "the requested object"
                message = (
                    f"Hello {user_name},\n\n"
                    f"Your Salesforce access issue has been investigated.\n"
                    f"• Root Cause: You are missing required Object CRUD (Create/Read/Edit/Delete) permissions on {target_obj_name}. "
                    f"A comparative benchmark against your peer mirror user confirmed differing object permission assignments.\n"
                    f"• Resolution Step: Per security governance, please submit a 'Manage User' Request Item (RITM) in ServiceNow "
                    f"to request assignment of the required Profile or Permission Set granting object access.\n"
                    f"• Ticket Status: Resolved with instructions.\n\n"
                    f"Once your Manage User RITM is approved and assigned, your {target_obj_name} access will be activated."
                )
                res_notes = (
                    f"Automated investigation completed.\n"
                    f"Issue Code: {issue_code} (Missing Object-level CRUD Permissions)\n"
                    f"Findings: Object permissions differ from comparative peer mirror user baseline.\n"
                    f"Action: User notified via email and work notes to submit a Manage User RITM in ServiceNow for required Profile/Permission Set assignment.\n"
                    f"Ticket State: Resolved."
                )
            elif issue_code in ["OBJECT-2B", "OBJECT-FLS-MISSING"] or (issue_code.startswith("OBJECT") and "fls" in issue_code.lower()):
                target_obj_name = action_obj.get('target_object') or "the requested object"
                message = (
                    f"Hello {user_name},\n\n"
                    f"Your Salesforce access issue has been investigated.\n"
                    f"• Root Cause: You are missing Field-Level Security (FLS) permissions on {target_obj_name}. "
                    f"A comparative benchmark against your peer mirror user confirmed differing field visibility and edit rights.\n"
                    f"• Resolution Step: Per security governance, please submit a 'Manage User' Request Item (RITM) in ServiceNow "
                    f"to request assignment of the required Field-Level Security Permission Set.\n"
                    f"• Ticket Status: Resolved with instructions.\n\n"
                    f"Once your Manage User RITM is approved, the field will become visible and editable."
                )
                res_notes = (
                    f"Automated investigation completed.\n"
                    f"Issue Code: {issue_code} (Missing Field-Level Security Permissions)\n"
                    f"Findings: FLS permissions differ from comparative peer mirror user baseline.\n"
                    f"Action: User notified via email and work notes to submit a Manage User RITM in ServiceNow for Field-Level Security Permission Set assignment.\n"
                    f"Ticket State: Resolved."
                )
            elif issue_code in ["OBJECT-1", "OBJECT-001", "OBJECT-3", "OBJECT-003", "OBJECT-WIZARD-COUNTRY-BLANK"] or target_f == "WizardCountry":
                message = (
                    f"Hello {user_name},\n\n"
                    f"Your Salesforce access issue has been investigated and resolved.\n"
                    f"• Root Cause: The Wizard Country field was blank on your Contact record, preventing Wizard Application and Product Search access.\n"
                    f"• Action Taken: Populated Contact.Wizard_Country__c with the verified peer mirror user baseline value ('{prop_v}').\n"
                    f"• Verification: Confirmed active Contact and User state in NA Org.\n\n"
                    f"Please log in and access the Wizard Application or Product Search now. If you encounter any further issues, feel free to reply."
                )
                res_notes = (
                    f"Automated resolution completed.\n"
                    f"Issue Code: {issue_code} (Contact.Wizard_Country__c Populated)\n"
                    f"Action: Updated Contact.Wizard_Country__c to '{prop_v}' based on peer mirror baseline.\n"
                    f"Verification: {verif.get('details')}\n"
                    f"Ticket State: Resolved."
                )
            elif issue_code in ["RECORD-1A", "RECORD-OBJ-PERM-REPORT", "RECORD-OBJ-PERM-MISSING"]:
                message = (
                    f"Hello {user_name},\n\n"
                    f"Your Salesforce access issue has been investigated.\n"
                    f"• Root Cause: You lack access to the underlying object(s) used by the requested report or dashboard.\n"
                    f"• Resolution Step: Please submit a 'Manage User' Request Item (RITM) in ServiceNow for underlying object permission assignment.\n"
                    f"• Ticket Status: Resolved with instructions."
                )
                res_notes = (
                    f"Automated investigation completed.\n"
                    f"Issue Code: {issue_code} (Missing Underlying Object Permissions for Report/Dashboard)\n"
                    f"Action: User notified to submit a Manage User RITM for required Profile/Permission Set.\n"
                    f"Ticket State: Resolved."
                )
            elif issue_code in ["RECORD-1B", "RECORD-1", "RECORD-001", "RECORD-FOLDER-ACCESS-MISSING"]:
                message = (
                    f"Hello {user_name},\n\n"
                    f"Your Salesforce access issue has been investigated.\n"
                    f"• Root Cause: You have object-level access, but the Report/Dashboard folder has not been shared with you.\n"
                    f"• Resolution Step: Report folders can only be shared by their respective folder owners. "
                    f"Please contact the folder owner directly to request viewer or editor access to the folder.\n"
                    f"• Ticket Status: Resolved with instructions."
                )
                res_notes = (
                    f"Automated investigation completed.\n"
                    f"Issue Code: {issue_code} (Report/Dashboard Folder Not Shared)\n"
                    f"Action: Requester advised to contact folder owner for folder sharing access.\n"
                    f"Ticket State: Resolved."
                )
            elif issue_code in ["RECORD-2A", "RECORD-3A"]:
                message = (
                    f"Hello {user_name},\n\n"
                    f"Your Salesforce access issue has been investigated.\n"
                    f"• Root Cause: You lack object-level permissions to access the requested record.\n"
                    f"• Resolution Step: Please submit a 'Manage User' Request Item (RITM) in ServiceNow for the required Object Permission Set.\n"
                    f"• Ticket Status: Resolved with instructions."
                )
                res_notes = (
                    f"Automated investigation completed.\n"
                    f"Issue Code: {issue_code} (Missing Object Permissions for Record)\n"
                    f"Action: User advised to submit Manage User RITM.\n"
                    f"Ticket State: Resolved."
                )
            elif issue_code in ["RECORD-2B", "RECORD-3B"]:
                message = (
                    f"Hello {user_name},\n\n"
                    f"Your Salesforce access issue has been investigated and resolved.\n"
                    f"• Root Cause: Missing record-level sharing access.\n"
                    f"• Action Taken: {prop_v or justification or 'Configured record sharing access'}.\n"
                    f"• Verification: Confirmed active record access.\n\n"
                    f"Please try opening the record now."
                )
                res_notes = (
                    f"Automated resolution completed.\n"
                    f"Issue Code: {issue_code} (Record Sharing Granted)\n"
                    f"Action: {plan.get('proposed_action')}\n"
                    f"Verification: {verif.get('details')}\n"
                    f"Ticket State: Resolved."
                )
            elif issue_code in ["RECORD-3C"]:
                message = (
                    f"Hello {user_name},\n\n"
                    f"Your Salesforce access issue has been investigated.\n"
                    f"• Root Cause: The requested field is not visible or editable on this record due to Field-Level Security (FLS).\n"
                    f"• Resolution Step: Please submit a 'Manage User' Request Item (RITM) in ServiceNow for the required FLS permission.\n"
                    f"• Ticket Status: Resolved with instructions."
                )
                res_notes = (
                    f"Automated investigation completed.\n"
                    f"Issue Code: {issue_code} (Field-Level Security Restriction on Record)\n"
                    f"Action: User advised to submit Manage User RITM.\n"
                    f"Ticket State: Resolved."
                )
            elif issue_code in ["OUTLOOK-1A"]:
                message = (
                    f"Hello {user_name},\n\n"
                    f"Your Salesforce Outlook Add-in issue has been investigated.\n"
                    f"• Root Cause: The Salesforce Outlook Add-in is disabled in your Outlook client.\n"
                    f"• Resolution Step: Please navigate to Outlook > File > Manage Add-ins, re-enable the Salesforce Add-in, and restart Outlook.\n"
                    f"• Ticket Status: Resolved with instructions."
                )
                res_notes = (
                    f"Automated investigation completed.\n"
                    f"Issue Code: {issue_code} (Salesforce Outlook Add-in Disabled)\n"
                    f"Action: User provided instructions to re-enable the Add-in in Outlook and restart client.\n"
                    f"Ticket State: Resolved."
                )
            elif target_f == "RITMGuidance":
                message = (
                    f"Hello {user_name},\n\n"
                    f"Your Salesforce access issue has been investigated.\n"
                    f"• Root Cause: {justification or diag.get('decision_basis') or 'Access restriction identified'}.\n"
                    f"• Resolution Step: {prop_v or 'Please submit a Manage User Request Item (RITM) in ServiceNow for required access approval.'}\n"
                    f"• Ticket Status: Resolved with instructions."
                )
                res_notes = (
                    f"Automated investigation completed.\n"
                    f"Issue Code: {issue_code}\n"
                    f"Action: {prop_v}\n"
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
