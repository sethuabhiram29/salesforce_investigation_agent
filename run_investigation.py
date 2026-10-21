"""Interactive CLI Runner for Salesforce Support Agent.

Allows providing a ServiceNow ticket and visualizes the investigation lifecycle,
displaying:
- Real-time state transitions across all agents
- Tool calls and observed evidence
- PostgreSQL pgvector historical retrievals
- Human-in-the-Loop (HITL) approval review
- Verification and ServiceNow closure notes
"""

import json
import sys
import time
from typing import Any, Dict

from app.orchestrator.agent import InvestigationOrchestrator
from app.tools.salesforce import reset_fixture_state, salesforce_get_user_details
from app.tools.service_now import servicenow_get_incident


def print_banner(text: str, char="="):
    print("\n" + char * 80)
    print(text.center(80))
    print(char * 80)


def print_section(title: str):
    print("\n" + "-" * 80)
    print(f" > {title.upper()}")
    print("-" * 80)


def format_json(obj: Any) -> str:
    return json.dumps(obj, indent=2, default=str)


def run_interactive_ticket(ticket: Dict[str, Any], auto_approve: bool = False):
    print_banner("SALESFORCE AGENTIC SUPPORT SYSTEM — INVESTIGATION TRACE")

    print(f"Incident ID : {ticket.get('incident_id')}")
    print(f"Summary     : {ticket.get('short_description')}")
    print(f"Caller      : {ticket.get('caller_email')}")
    print(f"Description :\n  {ticket.get('description')}")

    orchestrator = InvestigationOrchestrator()

    # We run the orchestrator streaming state transitions
    config = {"configurable": {"thread_id": f"cli_{int(time.time())}"}}
    initial_state = {
        "incident": ticket,
        "evidence": [],
        "historical_cases": [],
        "trace_events": [],
        "iteration_count": 0,
    }

    print("\nStarting Outer LangGraph workflow execution...")

    current_state = initial_state
    for output in orchestrator.graph.stream(initial_state, config=config):
        for node_name, state_update in output.items():
            print_section(f"Agent Node Executed: [{node_name}]")

            # --- Stage-Specific Inspection ---
            if node_name == "triage":
                triage = state_update.get("triage_result", {})
                affected = state_update.get("affected_user", {})
                history = state_update.get("historical_cases", [])

                print(f"  • Classified Domain    : {triage.get('domain')}")
                print(f"  • Ambiguity Flag       : {triage.get('is_ambiguous')}")
                print(f"  • Extracted Entities   : {triage.get('extracted_entities')}")
                print(f"  • Resolved Target User : {affected.get('FirstName', '')} {affected.get('LastName', '')} ({affected.get('Email', 'Unknown')})")
                mirror = state_update.get("mirror_user")
                if mirror:
                    print(f"  • Resolved Mirror User : {mirror.get('FirstName', '')} {mirror.get('LastName', '')} ({mirror.get('Email', 'Unknown')}) [Comparison Baseline]")

                print("\n  [pgvector Historical Experience Retrieved from PostgreSQL]")
                if history:
                    for idx, h in enumerate(history, 1):
                        sim = h.get('similarity', 0) * 100
                        print(f"    ({idx}) [{sim:.1f}% Match] Past Incident {h.get('incident_id')}: {h.get('root_cause')}")
                else:
                    print("    No previous incidents matched or fallback used.")

            elif node_name == "diagnosis":
                diag = state_update.get("diagnosis_result", {})
                skill = state_update.get("skill_refs", {})
                evidence = state_update.get("evidence", [])

                print(f"  * Root Cause Confirmed   : {diag.get('issue_code')}")
                print(f"  * Diagnostic Status      : {diag.get('status').upper()}")
                print(f"  * Skill File Status      : Loaded in Resolution Planning Stage")

                print("\n  [Evidence Gathered via ToolNode / MCP]")
                for ev in evidence:
                    print(f"    - [{ev.get('evidence_id')}] Tool '{ev.get('tool_name')}' observed:")
                    if ev.get("observed_value"):
                        obs = ev.get("observed_value")
                        if isinstance(obs, dict):
                            print(f"        IsActive: {obs.get('IsActive')}, FederationIdentifier: {obs.get('FederationIdentifier')}")
                        else:
                            print(f"        {obs}")
                    elif ev.get("raw_output"):
                        print(f"        Result: {len(ev.get('raw_output'))} records matched")

                print("\n  [Findings Grounded in Evidence]")
                for f in diag.get("findings", []):
                    print(f"    [MATCH] Claim: \"{f.get('claim')}\" -> Cited Evidence: {f.get('evidence_refs')}")

            elif node_name == "resolution_planning":
                plan = state_update.get("resolution_plan", {})
                action = plan.get("proposed_action", {})
                appr = state_update.get("approval", {})
                skill = state_update.get("skill_refs", {})

                print(f"  * Skill File Loaded    : {skill.get('file_path')} (v{skill.get('version', 1)})")
                print(f"  * Remediation Action   : {action.get('action_type')}")
                print(f"  * Target Salesforce ID : {action.get('target_record_id')}")
                print(f"  * Field Modification   : User.{action.get('target_field')}")
                print(f"  * Current Value        : {action.get('current_value')}")
                print(f"  * Proposed Value       : '{action.get('proposed_value')}'")
                print(f"  * Preconditions        : {plan.get('preconditions')}")
                print(f"  * Requires HITL Review : {plan.get('requires_approval')}")

                # Human-In-The-Loop Interactive Gate
                if plan.get("requires_approval") and not auto_approve:
                    print("\n  " + "=" * 60)
                    print("  [HITL APPROVAL GATE] Please review the proposed change:")
                    print(f"  Target: User.{action.get('target_field')} -> '{action.get('proposed_value')}'")
                    print("  " + "=" * 60)
                    user_input = input("  Do you approve this change? (yes/no) [yes]: ").strip().lower()
                    if user_input in ("", "y", "yes"):
                        state_update["approval"]["approval_status"] = "approved"
                        print("  >> Action Approved by Administrator.")
                    else:
                        state_update["approval"]["approval_status"] = "rejected"
                        print("  >> Action REJECTED by Administrator.")
                else:
                    state_update["approval"]["approval_status"] = "approved"
                    print("  >> Action Auto-Approved (Policy/Test flag).")

            elif node_name == "execute_remediation":
                plan = state_update.get("resolution_plan", {})
                appr = state_update.get("approval", {})
                print(f"  * Execution Status     : {plan.get('status')}")
                print(f"  * Bound Approval ID    : {appr.get('approval_id')}")

            elif node_name == "verification":
                verif = state_update.get("verification_result", {})
                print(f"  * Post-Change Verified : {verif.get('verified')}")
                print(f"  * Checks Performed     : {verif.get('checks_performed')}")
                print(f"  * Expected State       : {verif.get('expected_state')}")
                print(f"  * Actual State in SF   : {verif.get('actual_state')}")

            elif node_name == "communication":
                comm = state_update.get("communication_draft")
                sn = state_update.get("servicenow_update", {})
                print(f"  * ServiceNow State     : {sn.get('state')}")
                print(f"\n  [Drafted Customer Update Response]:\n")
                for line in comm.splitlines():
                    print(f"    {line}")

            elif node_name == "escalation":
                sn = state_update.get("servicenow_update", {})
                print(f"  * Ticket Escalated     : State -> {sn.get('state')}")
                print(f"  * Reason               : {sn.get('reason')}")

            current_state = state_update

    print_banner("INVESTIGATION COMPLETE", char="=")


def main():
    reset_fixture_state()

    print("\nSelect a ticket to investigate:")
    print("1. INC10001: Jane Doe cannot login via Okta SSO (Missing Federation ID - LOGIN-4)")
    print("2. INC10002: John Smith locked out after leave (Deactivated Delegated Admin - LOGIN-3)")
    print("3. INC10003: General access ticket ('Can't access salesforce at all') -> Dynamic diagnosis & fallback")
    print("4. INC10004: Sarah Connor cannot edit Account / compare with Alex Taylor (OBJECT-1/2)")
    print("5. INC10005: Sarah Connor cannot view Opportunity 006xx000001OPP (RECORD-3)")
    print("6. Custom: Enter your own incident details")

    choice = input("\nEnter choice [1-6] (default 1): ").strip()
    if choice == "2":
        ticket = servicenow_get_incident("INC10002")
    elif choice == "3":
        ticket = {
            "incident_id": "INC10003",
            "short_description": "Salesforce broken",
            "description": "Can't access salesforce at all. Please help.",
            "caller_email": "jane.doe@acme.corp",
        }
    elif choice == "4":
        ticket = {
            "incident_id": "INC10004",
            "short_description": "Cannot edit account records",
            "description": "User sarah.connor@acme.corp cannot edit Account records. Works fine for alex.taylor@acme.corp.",
            "caller_email": "sarah.connor@acme.corp",
        }
    elif choice == "5":
        ticket = {
            "incident_id": "INC10005",
            "short_description": "Record access denied on Opportunity",
            "description": "User sarah.connor@acme.corp cannot view or edit Opportunity record 006xx000001OPP.",
            "caller_email": "sarah.connor@acme.corp",
        }
    elif choice == "6":
        inc_id = input("Incident ID: ").strip() or "INC_CUSTOM"
        summary = input("Short Description: ").strip() or "Cannot login"
        desc = input("Full Description: ").strip() or "User cannot authenticate"
        caller = input("Caller Email: ").strip() or "jane.doe@acme.corp"
        ticket = {
            "incident_id": inc_id,
            "short_description": summary,
            "description": desc,
            "caller_email": caller,
        }
    else:
        ticket = servicenow_get_incident("INC10001")

    run_interactive_ticket(ticket)


if __name__ == "__main__":
    main()
