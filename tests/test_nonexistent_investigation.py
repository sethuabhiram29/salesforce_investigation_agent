from app.orchestrator.graph import build_investigation_graph

graph = build_investigation_graph()
initial_state = {
    "incident": {
        "incident_id": "INC-LIVE-001",
        "short_description": "Cannot sign in to Salesforce",
        "caller_email": "ganeshalla@gmail.com",
        "on_behalf_of": "ganeshalla@gmail.com",
        "description": "User ganeshalla@gmail.com is unable to login to salesforce. Account was not created or found."
    },
    "evidence": [],
    "historical_cases": [],
    "trace_events": [],
    "iteration_count": 0,
    "approval": {"approval_status": "approved"}
}

config = {"configurable": {"thread_id": "test_nonexistent_user"}}
for output in graph.stream(initial_state, config=config):
    for node, state in output.items():
        print(f"\n=== NODE: {node} ===")
        if "step_audit_trail" in state:
            print(f"Steps count in {node}: {len(state['step_audit_trail'])}")
            for step in state["step_audit_trail"]:
                print(f"  -> [{step.get('swimlane')}] {step.get('step_name')} | Dir: {step.get('movement_direction')} | Outcome: {step.get('status_reason')}")
        if node == "diagnosis":
            diag = state.get("diagnosis_result") or {}
            print(f"Diagnosis status: {diag.get('status')}, issue_code: {diag.get('issue_code')}")
        if node == "resolution_planning":
            plan = state.get("resolution_plan") or {}
            print(f"Resolution plan: {plan.get('issue_code')}, action: {plan.get('proposed_action', {}).get('proposed_value')}")
        if node == "verification":
            verif = state.get("verification_result") or {}
            print(f"Verification result: verified={verif.get('verified')}")
