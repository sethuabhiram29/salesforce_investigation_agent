"""Unit tests for Object Issues Decision Tree Knowledge Graph."""

import unittest
from app.knowledge.neo4j_repository import neo4j_repository
from app.agents.diagnosis.structured_flow import StructuredDiagnosisFlow
from app.tools.salesforce import reset_fixture_state


class TestObjectFlowchartKnowledgeGraph(unittest.TestCase):
    """Test suite for Object Issues Decision Tree and shared login verification."""

    def setUp(self):
        reset_fixture_state()
        self.flow = StructuredDiagnosisFlow()

    def test_object_domain_start_node_retrieval(self):
        """Verify OBJECT domain starts at shared NODE_TRIAGE_RESULT."""
        start_node = neo4j_repository.get_flowchart_start_node("OBJECT")
        self.assertEqual(start_node["id"], "NODE_TRIAGE_RESULT")

    def test_object_wizard_country_blank_confirms_object_1(self):
        """Verify Wizard App symptom with blank Wizard_Country__c confirms OBJECT-1."""
        res, ev, steps = self.flow.execute(
            target_identifier="sarah.connor@acme.corp",
            context={
                "domain": "OBJECT",
                "short_description": "User unable to search products in Wizard App",
                "description": "Wizard App product search returns error",
                "has_wizard_symptom": True,
                "is_wizard_country_blank": True,
                "wizard_country": None,
                "contact_details": {"Id": "003OBJ001", "Wizard_Country__c": None},
            },
        )
        self.assertEqual(res.status, "confirmed")
        self.assertEqual(res.issue_code, "OBJECT-1")
        node_ids = [s.get("graph_node_id") for s in steps]
        self.assertIn("NODE_OBJ_CLASSIFY_ISSUE_TYPE", node_ids)
        self.assertIn("NODE_OBJ_RETRIEVE_CONTACT", node_ids)
        self.assertIn("NODE_OBJ_IS_WIZARD_COUNTRY_BLANK", node_ids)
        self.assertIn("NODE_OBJ_FETCH_MIRROR_WIZARD", node_ids)
        self.assertIn("TERMINAL_OBJ_WIZARD_COUNTRY_BLANK", node_ids)

    def test_object_wizard_country_populated_manual_review(self):
        """Verify Wizard App symptom with populated Wizard_Country__c routes to manual review."""
        res, ev, steps = self.flow.execute(
            target_identifier="sarah.connor@acme.corp",
            context={
                "domain": "OBJECT",
                "short_description": "Wizard App issue but country is populated",
                "description": "Wizard App error but country code is US",
                "has_wizard_symptom": True,
                "is_wizard_country_blank": False,
                "wizard_country": "US",
                "contact_details": {"Id": "003OBJ002", "Wizard_Country__c": "US"},
            },
        )
        self.assertEqual(res.status, "escalation_required")
        node_ids = [s.get("graph_node_id") for s in steps]
        self.assertIn("TERMINAL_OBJ_MANUAL_REVIEW", node_ids)

    def test_object_access_issue_confirms_object_2(self):
        """Verify Object Access symptom confirms OBJECT-2A (CRUD permissions missing)."""
        res, ev, steps = self.flow.execute(
            target_identifier="sarah.connor@acme.corp",
            context={
                "domain": "OBJECT",
                "short_description": "Insufficient Privileges on Object",
                "description": "User cannot create or edit Account records due to missing object permissions",
                "has_wizard_symptom": False,
                "has_object_or_field_symptom": True,
                "is_object_access_issue": True,
            },
        )
        self.assertEqual(res.status, "confirmed")
        self.assertIn(res.issue_code, ["OBJECT-2A", "OBJECT-2"])
        node_ids = [s.get("graph_node_id") for s in steps]
        self.assertIn("NODE_OBJ_IS_OBJECT_ACCESS_ISSUE", node_ids)
        self.assertIn("NODE_OBJ_FETCH_MIRROR_USER", node_ids)
        self.assertIn("NODE_OBJ_COMPARE_OBJECT_PERMS", node_ids)
        self.assertIn("NODE_OBJ_DO_OBJECT_PERMS_DIFFER", node_ids)
        self.assertIn("TERMINAL_OBJ_OBJECT_ACCESS_ISSUE", node_ids)

    def test_object_field_access_issue_confirms_object_3(self):
        """Verify Field Access symptom confirms OBJECT-2B (FLS missing)."""
        res, ev, steps = self.flow.execute(
            target_identifier="sarah.connor@acme.corp",
            context={
                "domain": "OBJECT",
                "short_description": "Field not visible on Opportunity",
                "description": "User cannot view custom discount field FLS missing",
                "has_wizard_symptom": False,
                "has_object_or_field_symptom": True,
                "is_object_access_issue": False,
                "is_field_access_issue": True,
            },
        )
        self.assertEqual(res.status, "confirmed")
        self.assertIn(res.issue_code, ["OBJECT-2B", "OBJECT-3"])
        node_ids = [s.get("graph_node_id") for s in steps]
        self.assertIn("NODE_OBJ_IS_FIELD_ACCESS_ISSUE", node_ids)
        self.assertIn("NODE_OBJ_FETCH_MIRROR_FIELD", node_ids)
        self.assertIn("NODE_OBJ_COMPARE_FIELD_PERMS", node_ids)
        self.assertIn("NODE_OBJ_DO_FIELD_PERMS_DIFFER", node_ids)
        self.assertIn("TERMINAL_OBJ_FIELD_ACCESS_ISSUE", node_ids)

    def test_user_cannot_edit_account_details_confirms_object_2a(self):
        """Verify exact incident narrative 'cannot edit account details ... unable to edit some objects' confirms OBJECT-2A."""
        res, ev, steps = self.flow.execute(
            target_identifier="allaganesh@gmail.com",
            context={
                "domain": "OBJECT",
                "short_description": "cannot edit account details",
                "description": "cannot edit account details user allaganesh@gmail.com unable to edit some objects.",
            },
        )
        self.assertEqual(res.status, "confirmed")
        self.assertIn(res.issue_code, ["OBJECT-2A", "OBJECT-2"])
        node_ids = [s.get("graph_node_id") for s in steps]
        self.assertIn("NODE_OBJ_CLASSIFY_ISSUE_TYPE", node_ids)
        self.assertIn("NODE_OBJ_HAS_OBJECT_OR_FIELD_SYMPTOM", node_ids)
        self.assertIn("NODE_OBJ_IS_OBJECT_ACCESS_ISSUE", node_ids)
        self.assertIn("NODE_OBJ_FETCH_MIRROR_USER", node_ids)
        self.assertIn("NODE_OBJ_COMPARE_OBJECT_PERMS", node_ids)
        self.assertIn("NODE_OBJ_DO_OBJECT_PERMS_DIFFER", node_ids)
        self.assertIn("TERMINAL_OBJ_OBJECT_ACCESS_ISSUE", node_ids)

    def test_product_search_blank_wizard_country_confirms_object_3(self):
        """Verify Product Search issue with blank Wizard_Country__c confirms OBJECT-3."""
        res, ev, steps = self.flow.execute(
            target_identifier="sarah.connor@acme.corp",
            context={
                "domain": "OBJECT",
                "short_description": "Users Cannot Access Product Search Object",
                "description": "User cannot perform product search because wizard country is unpopulated",
                "contact_details": {"Id": "003OBJ003", "Wizard_Country__c": None},
            },
        )
        self.assertEqual(res.status, "confirmed")
        self.assertIn(res.issue_code, ["OBJECT-3", "OBJECT-1"])
        node_ids = [s.get("graph_node_id") for s in steps]
        self.assertIn("NODE_OBJ_RETRIEVE_CONTACT", node_ids)
        self.assertIn("NODE_OBJ_FETCH_MIRROR_WIZARD", node_ids)
        self.assertIn("TERMINAL_OBJ_WIZARD_COUNTRY_BLANK", node_ids)

    def test_object_inactive_user_routes_to_shared_login_flow(self):
        """Verify inactive user in Object domain routes to Login deactivation (LOGIN-3A)."""
        res, ev, steps = self.flow.execute(
            target_identifier="john.smith@acme.corp",
            context={
                "domain": "OBJECT",
                "short_description": "User reporting Wizard app issue but account inactive",
                "description": "Wizard app access issue",
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
