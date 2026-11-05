"""Unit tests for Record Issues Decision Tree Knowledge Graph."""

import unittest
from app.knowledge.neo4j_repository import neo4j_repository
from app.agents.diagnosis.structured_flow import StructuredDiagnosisFlow
from app.tools.salesforce import reset_fixture_state


class TestRecordFlowchartKnowledgeGraph(unittest.TestCase):
    """Test suite for Record Issues Decision Tree and shared login verification."""

    def setUp(self):
        reset_fixture_state()
        self.flow = StructuredDiagnosisFlow()

    def test_record_domain_start_node_retrieval(self):
        """Verify RECORD domain starts at shared NODE_TRIAGE_RESULT."""
        start_node = neo4j_repository.get_flowchart_start_node("RECORD")
        self.assertEqual(start_node["id"], "NODE_TRIAGE_RESULT")

    def test_record_report_folder_access_missing_confirms_record_1(self):
        """Verify report issue with missing folder access confirms RECORD-1."""
        res, ev, steps = self.flow.execute(
            target_identifier="sarah.connor@acme.corp",
            context={
                "domain": "RECORD",
                "short_description": "User cannot view quarterly sales report",
                "description": "Report access error folder permission missing",
                "rec_is_report_dashboard": True,
                "rec_missing_obj_perms_report": False,
                "rec_is_folder_info_avail": True,
                "rec_folder_access_missing": True,
            },
        )
        self.assertEqual(res.status, "confirmed")
        self.assertEqual(res.issue_code, "RECORD-1")
        node_ids = [s.get("graph_node_id") for s in steps]
        self.assertIn("NODE_REC_IS_REPORT_DASHBOARD", node_ids)
        self.assertIn("NODE_REC_CHECK_FOLDER_ACCESS", node_ids)
        self.assertIn("TERMINAL_REC_FOLDER_ACCESS_MISSING", node_ids)

    def test_record_opp_case_sharing_missing_confirms_record_2(self):
        """Verify Opportunity record inaccessible due to missing sharing confirms RECORD-2."""
        res, ev, steps = self.flow.execute(
            target_identifier="sarah.connor@acme.corp",
            context={
                "domain": "RECORD",
                "short_description": "Cannot open Opportunity 006xx000001",
                "description": "User cannot access Opportunity record Insufficient Privileges",
                "rec_is_report_dashboard": False,
                "rec_is_opp_case": True,
                "rec_missing_obj_perms_opp_case": False,
                "rec_opp_case_cannot_access": True,
                "rec_opp_case_has_read_access": False,
                "rec_opp_case_missing_sharing_path": True,
            },
        )
        self.assertEqual(res.status, "confirmed")
        self.assertEqual(res.issue_code, "RECORD-2")
        node_ids = [s.get("graph_node_id") for s in steps]
        self.assertIn("NODE_REC_IS_OPP_CASE", node_ids)
        self.assertIn("NODE_REC_OPP_CASE_REVIEW_SHARING", node_ids)
        self.assertIn("TERMINAL_REC_OPP_CASE_SHARING_MISSING", node_ids)

    def test_record_general_sharing_missing_confirms_record_3(self):
        """Verify general record access missing row-level sharing confirms RECORD-3."""
        res, ev, steps = self.flow.execute(
            target_identifier="sarah.connor@acme.corp",
            context={
                "domain": "RECORD",
                "short_description": "Cannot open Account record 001xx000001",
                "description": "Record sharing error on Account",
                "rec_is_report_dashboard": False,
                "rec_is_opp_case": False,
                "rec_is_salesforce_record": True,
                "rec_missing_obj_perms_record": False,
                "rec_cannot_access_record": True,
                "rec_record_has_read_access": False,
                "rec_missing_sharing_path": True,
            },
        )
        self.assertEqual(res.status, "confirmed")
        self.assertEqual(res.issue_code, "RECORD-3")
        node_ids = [s.get("graph_node_id") for s in steps]
        self.assertIn("NODE_REC_IS_SALESFORCE_RECORD", node_ids)
        self.assertIn("NODE_REC_REVIEW_SHARING_PATH", node_ids)
        self.assertIn("TERMINAL_REC_SHARING_MISSING", node_ids)

    def test_record_fls_missing_confirms_record_4(self):
        """Verify field not visible/editable due to missing FLS confirms RECORD-4."""
        res, ev, steps = self.flow.execute(
            target_identifier="sarah.connor@acme.corp",
            context={
                "domain": "RECORD",
                "short_description": "Field not visible on record",
                "description": "User can view record but custom discount field is hidden FLS missing",
                "rec_is_report_dashboard": False,
                "rec_is_opp_case": False,
                "rec_is_salesforce_record": True,
                "rec_missing_obj_perms_record": False,
                "rec_cannot_access_record": False,
                "rec_field_not_visible": True,
                "rec_is_fls_missing": True,
            },
        )
        self.assertEqual(res.status, "confirmed")
        self.assertEqual(res.issue_code, "RECORD-4")
        node_ids = [s.get("graph_node_id") for s in steps]
        self.assertIn("NODE_REC_FIELD_NOT_VISIBLE", node_ids)
        self.assertIn("NODE_REC_COMPARE_MIRROR_FLS", node_ids)
        self.assertIn("TERMINAL_REC_FLS_MISSING", node_ids)

    def test_record_object_permissions_missing(self):
        """Verify report issue with missing object permissions confirms RECORD-OBJ-PERM-MISSING."""
        res, ev, steps = self.flow.execute(
            target_identifier="sarah.connor@acme.corp",
            context={
                "domain": "RECORD",
                "short_description": "Cannot run reports",
                "description": "Report object permission missing on profile",
                "rec_is_report_dashboard": True,
                "rec_missing_obj_perms_report": True,
            },
        )
        self.assertEqual(res.status, "confirmed")
        self.assertEqual(res.issue_code, "RECORD-OBJ-PERM-MISSING")
        node_ids = [s.get("graph_node_id") for s in steps]
        self.assertIn("TERMINAL_REC_MISSING_OBJ_PERMS_REPORT", node_ids)

    def test_record_inactive_user_routes_to_shared_login_flow(self):
        """Verify inactive user in Record domain routes to Login deactivation (LOGIN-3A)."""
        res, ev, steps = self.flow.execute(
            target_identifier="john.smith@acme.corp",
            context={
                "domain": "RECORD",
                "short_description": "User reporting record access issue but account is inactive",
                "description": "Record sharing access problem",
            },
        )
        self.assertEqual(res.status, "confirmed")
        self.assertEqual(res.issue_code, "LOGIN-3A")
        node_ids = [s.get("graph_node_id") for s in steps]
        self.assertIn("NODE_SEARCH_MAIN_ORG", node_ids)
        self.assertIn("NODE_IS_ACTIVE", node_ids)
        self.assertIn("NODE_RETRIEVE_DEACT_AUDIT", node_ids)


if __name__ == "__main__":
    unittest.main()

