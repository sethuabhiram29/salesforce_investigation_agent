from app.knowledge.neo4j_repository import neo4j_repository
from app.agents.diagnosis.structured_flow import StructuredDiagnosisFlow

def test_graph_validation():
    print("\n--- VALIDATING GRAPH STRUCTURE ---")
    start = neo4j_repository.get_flowchart_start_node("LOGIN")
    print(f"Start node: {start.get('name')} [{start.get('id')}]")
    
    # Check Swimlane 5 connections
    mirror_fetch = neo4j_repository.get_flowchart_node("NODE_FETCH_MIRROR_USER")
    trans_fetch = neo4j_repository.get_node_transitions("NODE_FETCH_MIRROR_USER")
    print(f"NODE_FETCH_MIRROR_USER -> next: {trans_fetch.get('next_target')}")
    assert trans_fetch.get("next_target") == "NODE_COMPARE_EMP_FED_ID"

    cmp_node = neo4j_repository.get_flowchart_node("NODE_COMPARE_EMP_FED_ID")
    trans_cmp = neo4j_repository.get_node_transitions("NODE_COMPARE_EMP_FED_ID")
    print(f"NODE_COMPARE_EMP_FED_ID -> next: {trans_cmp.get('next_target')}")
    assert trans_cmp.get("next_target") == "NODE_IS_INTERNAL_USER"

    # Check Mobile Login check connections
    trans_mobile = neo4j_repository.get_node_transitions("NODE_MOBILE_LOGIN_CHECK")
    print(f"NODE_MOBILE_LOGIN_CHECK -> yes: {trans_mobile.get('yes_target')}, no: {trans_mobile.get('no_target')}")
    assert trans_mobile.get("yes_target") == "TERMINAL_LOGIN_8"
    assert trans_mobile.get("no_target") == "TERMINAL_OUT_OF_SCOPE"

    # Check Email Verified check connections
    trans_email = neo4j_repository.get_node_transitions("NODE_IS_EMAIL_VERIFIED")
    print(f"NODE_IS_EMAIL_VERIFIED -> yes: {trans_email.get('yes_target')}, no: {trans_email.get('no_target')}")
    assert trans_email.get("yes_target") == "TERMINAL_OUT_OF_SCOPE"
    assert trans_email.get("no_target") == "NODE_WO_EMAIL_CHECK"

    # Check CIAM Sync check connections
    trans_ciam = neo4j_repository.get_node_transitions("NODE_CIAM_SYNC_MATCH")
    print(f"NODE_CIAM_SYNC_MATCH -> yes: {trans_ciam.get('yes_target')}, no: {trans_ciam.get('no_target')}")
    assert trans_ciam.get("yes_target") == "NODE_IS_EMAIL_VERIFIED"
    assert trans_ciam.get("no_target") == "TERMINAL_LOGIN_7"

    print("\nALL GRAPH NODE & EDGE ASSERTIONS PASSED!")

if __name__ == "__main__":
    test_graph_validation()
