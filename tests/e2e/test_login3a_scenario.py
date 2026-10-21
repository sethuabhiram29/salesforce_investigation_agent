"""E2E test: LOGIN-3A Delegated Admin Deactivation scenario.

Full workflow from ServiceNow incident intake to verified resolution.
"""

import unittest

from app.orchestrator.agent import InvestigationOrchestrator
from app.tools.salesforce import reset_fixture_state, salesforce_get_user_details


class TestLogin3aScenarioE2E(unittest.TestCase):
    def setUp(self):
        reset_fixture_state()
        self.orchestrator = InvestigationOrchestrator()

    def tearDown(self):
        reset_fixture_state()

    def test_e2e_login3a_scenario(self):
        ticket = {
            "incident_id": "INC10002",
            "short_description": "Delegated admin locked out",
            "description": "john.smith@acme.corp cannot sign in to Salesforce",
            "caller_email": "john.smith@acme.corp",
        }

        # Verify initial state: IsActive is False
        user_before = salesforce_get_user_details("005xx000002LOGIN3A")
        self.assertFalse(user_before["IsActive"])

        final_state = self.orchestrator.run_investigation(ticket, auto_approve=True)

        # Verify end-to-end outcome
        self.assertEqual(final_state["diagnosis_result"]["issue_code"], "LOGIN-3")
        self.assertEqual(final_state["diagnosis_result"]["observed_values"]["deactivation_actor"], "Delegated Administrator")
        self.assertEqual(final_state["resolution_plan"]["proposed_action"]["target_field"], "RITMGuidance")
        self.assertEqual(final_state["resolution_plan"]["status"], "executed")
        self.assertTrue(final_state["verification_result"]["verified"])
        self.assertEqual(final_state["servicenow_update"]["state"], "Resolved")
        self.assertIn("RITM", final_state["communication_draft"])

        # Verify post-remediation Salesforce record: No direct write per policy, remains False
        user_after = salesforce_get_user_details("005xx000002LOGIN3A")
        self.assertFalse(user_after["IsActive"])


if __name__ == "__main__":
    unittest.main()
