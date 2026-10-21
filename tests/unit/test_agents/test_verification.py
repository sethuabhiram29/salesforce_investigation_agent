"""Tests for the Verification Agent."""

import unittest

from app.agents.verification.agent import VerificationAgent
from app.models.state import InvestigationState
from app.tools.salesforce import reset_fixture_state, salesforce_update_user


class TestVerificationAgent(unittest.TestCase):
    def setUp(self):
        reset_fixture_state()
        self.agent = VerificationAgent()

    def tearDown(self):
        reset_fixture_state()

    def test_verification_success(self):
        # Update user in fixture first
        salesforce_update_user("005xx000001LOGIN4", "FederationIdentifier", "jane.doe@acme.corp")

        state: InvestigationState = {
            "resolution_plan": {
                "issue_code": "LOGIN-4",
                "proposed_action": {
                    "action_type": "UPDATE_USER_FIELD",
                    "target_record_id": "005xx000001LOGIN4",
                    "target_field": "FederationIdentifier",
                    "proposed_value": "jane.doe@acme.corp",
                },
                "status": "executed",
            }
        }

        updated = self.agent.run(state)
        v = updated.get("verification_result", {})
        self.assertTrue(v.get("verified"))
        self.assertEqual(v.get("actual_state", {}).get("FederationIdentifier"), "jane.doe@acme.corp")

    def test_verification_failure_when_mismatched(self):
        # State expects jane.doe@acme.corp, but fixture still has None
        state: InvestigationState = {
            "resolution_plan": {
                "issue_code": "LOGIN-4",
                "proposed_action": {
                    "action_type": "UPDATE_USER_FIELD",
                    "target_record_id": "005xx000001LOGIN4",
                    "target_field": "FederationIdentifier",
                    "proposed_value": "jane.doe@acme.corp",
                },
                "status": "executed",
            }
        }

        updated = self.agent.run(state)
        v = updated.get("verification_result", {})
        self.assertFalse(v.get("verified"))


if __name__ == "__main__":
    unittest.main()
