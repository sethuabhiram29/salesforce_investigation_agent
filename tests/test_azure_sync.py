import asyncio
from app.agents.diagnosis.structured_flow import StructuredDiagnosisFlow

def run_tests():
    flow = StructuredDiagnosisFlow()

    # TEST 1: Re-hire Mismatch (Daniel Ortiz: SF FedID EMP-10022 vs Workday EMP-20491)
    print("======================================================================")
    print("TEST 1: Re-hire Mismatch (Daniel Ortiz: SF FedID EMP-10022 vs Workday EMP-20491)")
    print("======================================================================")
    context_rehire = {
        'ticket': {
            'incident_id': 'INC-REHIRE-001',
            'caller_email': 'daniel.ortiz@acme.corp',
            'short_description': 'Re-hired employee cannot sign in via Azure AD SSO',
            'description': 'Daniel Ortiz was re-hired under Workday employee id EMP-20491. Azure SSO fails.'
        }
    }
    r1, ev1, steps1 = flow.execute(
        target_identifier='daniel.ortiz@acme.corp',
        context=context_rehire,
        existing_evidence=[],
        evidence_cache={},
    )
    print("Final Confirmed Root Cause:", r1.issue_code)
    for step in steps1:
        if step.get("graph_node_id") == "NODE_AZURE_WORKDAY_MATCH":
            cmp = step.get("comparison_info", {})
            print("  Node: NODE_AZURE_WORKDAY_MATCH")
            print("  Target Value:", cmp.get("target_value"))
            print("  Baseline Value:", cmp.get("baseline_value"))
            print("  Comparison Result:", cmp.get("comparison_result"))
            print("  Decision Outcome:", cmp.get("decision_outcome"))
            print("  Reasoning:", cmp.get("reasoning"))

    # TEST 2: Random / Corrupt Federation ID (SF FedID 'RANDOM_CORRUPT_XYZ_999' vs 'EMP-00105')
    print("\n======================================================================")
    print("TEST 2: Random / Incorrect Federation ID (SF FedID 'RANDOM_CORRUPT_XYZ_999' vs 'EMP-00105')")
    print("======================================================================")
    context_random = {
        'ticket': {
            'incident_id': 'INC-RANDOM-002',
            'caller_email': 'corrupt.fed@acme.corp',
            'short_description': 'User cannot login via Azure SSO',
            'description': 'User corrupt.fed@acme.corp cannot authenticate through Azure AD SSO.'
        }
    }
    r2, ev2, steps2 = flow.execute(
        target_identifier='corrupt.fed@acme.corp',
        context=context_random,
        existing_evidence=[],
        evidence_cache={},
    )
    print("Final Confirmed Root Cause:", r2.issue_code)
    for step in steps2:
        if step.get("graph_node_id") == "NODE_AZURE_WORKDAY_MATCH":
            cmp = step.get("comparison_info", {})
            print("  Node: NODE_AZURE_WORKDAY_MATCH")
            print("  Target Value:", cmp.get("target_value"))
            print("  Baseline Value:", cmp.get("baseline_value"))
            print("  Comparison Result:", cmp.get("comparison_result"))
            print("  Decision Outcome:", cmp.get("decision_outcome"))
            print("  Reasoning:", cmp.get("reasoning"))

    # TEST 3: Genuine Match (Alex Taylor: SF FedID 'EMP-00101' == Workday 'EMP-00101')
    print("\n======================================================================")
    print("TEST 3: Genuine Match (Alex Taylor: SF FedID 'EMP-00101' == Workday 'EMP-00101')")
    print("======================================================================")
    context_match = {
        'ticket': {
            'incident_id': 'INC-MATCH-003',
            'caller_email': 'alex.taylor@acme.corp',
            'short_description': 'Mobile login setup issue on iOS device',
            'description': 'Alex Taylor has mobile login app error on iPhone.'
        }
    }
    r3, ev3, steps3 = flow.execute(
        target_identifier='alex.taylor@acme.corp',
        context=context_match,
        existing_evidence=[],
        evidence_cache={},
    )
    print("Final Confirmed Root Cause:", r3.issue_code)
    for step in steps3:
        if step.get("graph_node_id") == "NODE_AZURE_WORKDAY_MATCH":
            cmp = step.get("comparison_info", {})
            print("  Node: NODE_AZURE_WORKDAY_MATCH")
            print("  Target Value:", cmp.get("target_value"))
            print("  Baseline Value:", cmp.get("baseline_value"))
            print("  Comparison Result:", cmp.get("comparison_result"))
            print("  Decision Outcome:", cmp.get("decision_outcome"))
            print("  Reasoning:", cmp.get("reasoning"))

if __name__ == '__main__':
    run_tests()
