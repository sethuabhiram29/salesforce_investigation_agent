"""Tests for the Resolution Agent."""

import unittest

from app.agents.resolution.agent import ResolutionAgent
from app.models.state import InvestigationState
from app.tools.salesforce import reset_fixture_state, salesforce_get_user_details


class TestResolutionAgent(unittest.TestCase):
    def setUp(self):
        reset_fixture_state()
        self.agent = ResolutionAgent()

    def tearDown(self):
        reset_fixture_state()

    def test_plan_resolution_for_login4(self):
        state: InvestigationState = {
            "incident": {"incident_id": "INC201"},
            "affected_user": {
                "Id": "005xx000001LOGIN4",
                "Username": "jane.doe@acme.corp",
                "Email": "jane.doe@acme.corp",
            },
            "diagnosis_result": {
                "status": "confirmed",
                "issue_code": "LOGIN-4",
                "findings": [{"claim": "FederationIdentifier is null", "evidence_refs": ["ev_1"]}],
            },
        }

        updated = self.agent.plan_resolution(state)
        plan = updated.get("resolution_plan", {})

        self.assertEqual(plan.get("issue_code"), "LOGIN-4")
        self.assertTrue(plan.get("requires_approval"))
        action = plan.get("proposed_action", {})
        self.assertEqual(action.get("target_field"), "FederationIdentifier")
        self.assertEqual(action.get("proposed_value"), "jane.doe@acme.corp")
        self.assertEqual(updated.get("approval", {}).get("approval_status"), "pending")

    def test_refuses_to_plan_without_confirmed_diagnosis(self):
        state: InvestigationState = {
            "incident": {"incident_id": "INC202"},
            "affected_user": {"Id": "005xx000001LOGIN4"},
            "diagnosis_result": {
                "status": "insufficient_evidence",
                "issue_code": "LOGIN-4",
            },
        }

        updated = self.agent.plan_resolution(state)
        self.assertNotIn("resolution_plan", updated)

    def test_execute_remediation_requires_approval(self):
        state: InvestigationState = {
            "affected_user": {"Id": "005xx000001LOGIN4"},
            "resolution_plan": {
                "issue_code": "LOGIN-4",
                "proposed_action": {
                    "action_type": "UPDATE_USER_FIELD",
                    "target_record_id": "005xx000001LOGIN4",
                    "target_field": "FederationIdentifier",
                    "proposed_value": "jane.doe@acme.corp",
                },
                "status": "draft",
            },
            "approval": {"approval_status": "pending"},
        }

        # Execution should be blocked because status is pending
        updated = self.agent.execute_remediation(state)
        self.assertEqual(updated["resolution_plan"]["status"], "draft")

        # Now approve it
        state["approval"]["approval_status"] = "approved"
        executed_state = self.agent.execute_remediation(state)

        self.assertEqual(executed_state["resolution_plan"]["status"], "executed")
        # Verify in fixture state that field is actually updated
        user = salesforce_get_user_details("005xx000001LOGIN4")
        self.assertEqual(user["FederationIdentifier"], "jane.doe@acme.corp")


if __name__ == "__main__":
    unittest.main()
