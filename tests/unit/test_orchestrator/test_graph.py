"""Tests for the outer LangGraph orchestrator."""

import unittest

from app.orchestrator.agent import InvestigationOrchestrator
from app.tools.salesforce import reset_fixture_state, salesforce_get_user_details


class TestOuterGraph(unittest.TestCase):
    def setUp(self):
        reset_fixture_state()
        self.orchestrator = InvestigationOrchestrator()

    def tearDown(self):
        reset_fixture_state()

    def test_full_successful_lifecycle_login4(self):
        incident = {
            "incident_id": "INC_TEST_001",
            "short_description": "Cannot login via SSO",
            "description": "User jane.doe@acme.corp reports SAML error when authenticating.",
            "caller_email": "jane.doe@acme.corp",
        }

        # Run with auto_approve=True to simulate HITL approval in unit test
        final_state = self.orchestrator.run_investigation(incident, auto_approve=True)

        # 1. Triage verified
        self.assertEqual(final_state["triage_result"]["domain"], "LOGIN")
        self.assertEqual(final_state["affected_user"]["Username"], "jane.doe@acme.corp")

        # 2. Diagnosis confirmed LOGIN-4
        self.assertEqual(final_state["diagnosis_result"]["status"], "confirmed")
        self.assertEqual(final_state["diagnosis_result"]["issue_code"], "LOGIN-4")

        # 3. Resolution executed
        self.assertEqual(final_state["resolution_plan"]["status"], "executed")

        # 4. Verification succeeded
        self.assertTrue(final_state["verification_result"]["verified"])

        # 5. ServiceNow updated and closed
        self.assertEqual(final_state["servicenow_update"]["state"], "Resolved")
        self.assertIn("Automated resolution completed", final_state["servicenow_update"]["notes"])

        # 6. Salesforce post-state verified in fixture
        user = salesforce_get_user_details("005xx000001LOGIN4")
        self.assertEqual(user["FederationIdentifier"], "jane.doe@acme.corp")

        # 7. Trace events recorded all stages
        stages = [e["stage"] for e in final_state["trace_events"]]
        self.assertIn("triage", stages)
        self.assertIn("diagnosis", stages)
        self.assertIn("resolution", stages)
        self.assertIn("execution", stages)
        self.assertIn("verification", stages)
        self.assertIn("communication", stages)

    def test_ambiguous_incident_routes_to_escalation(self):
        vague_incident = {
            "incident_id": "INC_TEST_002",
            "short_description": "Salesforce is broken",
            "description": "Can't access salesforce at all",
            "caller_email": "someone@acme.corp",
        }

        final_state = self.orchestrator.run_investigation(vague_incident)

        # Ambiguous ticket must not auto-execute arbitrary fixes
        self.assertTrue(final_state["triage_result"]["is_ambiguous"])
        self.assertEqual(final_state["servicenow_update"]["state"], "Escalated")
        self.assertNotIn("resolution_plan", final_state)


if __name__ == "__main__":
    unittest.main()
