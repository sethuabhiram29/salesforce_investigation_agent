"""E2E test: LOGIN-4 Federation ID Missing scenario.

Full workflow from ServiceNow incident intake to verified resolution.
"""

import unittest

from app.orchestrator.agent import InvestigationOrchestrator
from app.tools.salesforce import reset_fixture_state, salesforce_get_user_details


class TestLogin4ScenarioE2E(unittest.TestCase):
    def setUp(self):
        reset_fixture_state()
        self.orchestrator = InvestigationOrchestrator()

    def tearDown(self):
        reset_fixture_state()

    def test_e2e_login4_scenario(self):
        ticket = {
            "incident_id": "INC10001",
            "short_description": "User cannot sign in via Okta SSO",
            "description": "User jane.doe@acme.corp reports SAML SSO authentication failure. Federation ID missing.",
            "caller_email": "jane.doe@acme.corp",
        }

        # Verify initial state: FederationIdentifier is None
        user_before = salesforce_get_user_details("005xx000001LOGIN4")
        self.assertIsNone(user_before["FederationIdentifier"])

        final_state = self.orchestrator.run_investigation(ticket, auto_approve=True)

        # Verify end-to-end outcome
        self.assertEqual(final_state["diagnosis_result"]["issue_code"], "LOGIN-4")
        self.assertEqual(final_state["resolution_plan"]["status"], "executed")
        self.assertTrue(final_state["verification_result"]["verified"])
        self.assertEqual(final_state["servicenow_update"]["state"], "Resolved")

        # Verify post-remediation Salesforce record
        user_after = salesforce_get_user_details("005xx000001LOGIN4")
        self.assertEqual(user_after["FederationIdentifier"], "jane.doe@acme.corp")


if __name__ == "__main__":
    unittest.main()
