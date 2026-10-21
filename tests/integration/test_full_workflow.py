"""Integration tests for the full investigation workflow."""

import unittest

from app.orchestrator.agent import InvestigationOrchestrator
from app.tools.salesforce import reset_fixture_state, salesforce_get_user_details


class TestFullWorkflowIntegration(unittest.TestCase):
    def setUp(self):
        reset_fixture_state()
        self.orchestrator = InvestigationOrchestrator()

    def tearDown(self):
        reset_fixture_state()

    def test_full_login4_workflow(self):
        incident = {
            "incident_id": "INC_INT_001",
            "short_description": "User getting SAML SSO error when signing into Salesforce",
            "description": "User Jane Doe (jane.doe@acme.corp) cannot log in via Okta SSO. Federation ID not found.",
            "caller_email": "jane.doe@acme.corp",
        }

        final_state = self.orchestrator.run_investigation(incident, auto_approve=True)

        self.assertEqual(final_state["triage_result"]["domain"], "LOGIN")
        self.assertEqual(final_state["diagnosis_result"]["status"], "confirmed")
        self.assertEqual(final_state["diagnosis_result"]["issue_code"], "LOGIN-4")
        self.assertEqual(final_state["resolution_plan"]["status"], "executed")
        self.assertTrue(final_state["verification_result"]["verified"])
        self.assertEqual(final_state["servicenow_update"]["state"], "Resolved")

        # Confirm post-change state in Salesforce
        user = salesforce_get_user_details("005xx000001LOGIN4")
        self.assertEqual(user["FederationIdentifier"], "jane.doe@acme.corp")

    def test_full_login3_workflow(self):
        incident = {
            "incident_id": "INC_INT_002",
            "short_description": "Delegated admin cannot sign in after leave",
            "description": "User John Smith (john.smith@acme.corp) is locked out and cannot log in.",
            "caller_email": "john.smith@acme.corp",
        }

        final_state = self.orchestrator.run_investigation(incident, auto_approve=True)

        self.assertEqual(final_state["triage_result"]["domain"], "LOGIN")
        self.assertEqual(final_state["diagnosis_result"]["status"], "confirmed")
        self.assertEqual(final_state["diagnosis_result"]["issue_code"], "LOGIN-3")
        self.assertEqual(final_state["resolution_plan"]["proposed_action"]["target_field"], "RITMGuidance")
        self.assertEqual(final_state["resolution_plan"]["status"], "executed")
        self.assertTrue(final_state["verification_result"]["verified"])
        self.assertEqual(final_state["servicenow_update"]["state"], "Resolved")
        self.assertIn("RITM", final_state["communication_draft"])

        # Confirm post-change state in Salesforce: No direct write per policy, remains False
        user = salesforce_get_user_details("005xx000002LOGIN3A")
        self.assertFalse(user["IsActive"])


    def test_full_login8_workflow(self):
        incident = {
            "incident_id": "INC_INT_003",
            "short_description": "User unable to log in to Salesforce mobile app",
            "description": "User Alex Taylor (alex.taylor@acme.corp) cannot log into the Salesforce mobile application on iPhone.",
            "caller_email": "alex.taylor@acme.corp",
        }

        final_state = self.orchestrator.run_investigation(incident, auto_approve=True)

        self.assertEqual(final_state["triage_result"]["domain"], "LOGIN")
        self.assertEqual(final_state["diagnosis_result"]["status"], "confirmed")
        self.assertEqual(final_state["diagnosis_result"]["issue_code"], "LOGIN-8")
        self.assertEqual(final_state["resolution_plan"]["status"], "executed")
        self.assertEqual(final_state["resolution_plan"]["proposed_action"]["target_field"], "SetupGuide")
        self.assertEqual(final_state["resolution_plan"]["proposed_action"]["action_type"], "COMMUNICATION_GUIDANCE")
        self.assertTrue(final_state["verification_result"]["verified"])
        self.assertEqual(final_state["servicenow_update"]["state"], "Resolved")
        self.assertIn("Mobile App Setup Guide", final_state["servicenow_update"]["notes"])
        self.assertIn("Mobile App Setup Guide", final_state["communication_draft"])


if __name__ == "__main__":
    unittest.main()
