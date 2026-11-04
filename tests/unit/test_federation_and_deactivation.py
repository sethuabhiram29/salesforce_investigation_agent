"""Unit tests for the 6 canonical Federation and Deactivation scenarios:
1. Account intentionally deactivated by Delegated Administrator (LOGIN-3A)
2. Automated deactivation from MuleSoft integration process (LOGIN-3)
3. FederationIdentifier is blank or null in Salesforce User record (LOGIN-4)
4. FederationIdentifier contains suspended/frozen (LOGIN-5)
5. FederationIdentifier != EmployeeNumber (LOGIN-6 - Azure synchronization)
6. FederationIdentifier CIAM external mismatch (LOGIN-7)
"""

import unittest
from app.agents.diagnosis.structured_flow import StructuredDiagnosisFlow
from app.agents.resolution.agent import ResolutionAgent
from app.agents.verification.agent import VerificationAgent
from app.tools.salesforce import reset_fixture_state, salesforce_get_user_details


class TestFederationAndDeactivationScenarios(unittest.TestCase):
    def setUp(self):
        reset_fixture_state()
        self.flow = StructuredDiagnosisFlow()
        self.resolution = ResolutionAgent()
        self.verification = VerificationAgent()

    def tearDown(self):
        reset_fixture_state()

    def test_scenario_1_delegated_admin_deactivation(self):
        """1. Intentional deactivation by Delegated Administrator -> LOGIN-3A -> Manage User RITM."""
        ctx = {
            "incident_summary": "Account deactivated",
            "incident_description": "User john.smith@acme.corp cannot sign in because account is disabled by delegated admin",
        }
        # John Smith is deactivated with DelegatedAdmin profile
        diag, _, _ = self.flow.execute("john.smith@acme.corp", context=ctx)
        self.assertEqual(diag.status, "confirmed")
        self.assertEqual(diag.issue_code, "LOGIN-3A")
        self.assertIn("DelegateGroupMember", diag.decision_basis)

        # Plan resolution
        state = {
            "incident": {"incident_id": "INC1001"},
            "affected_user": salesforce_get_user_details("005xx000002LOGIN3A"),
            "diagnosis_result": diag.model_dump(),
            "skill_refs": {"issue_code": "LOGIN-3A"},
        }
        updated = self.resolution.plan_resolution(state)
        plan = updated["resolution_plan"]
        action = plan["proposed_action"]

        self.assertEqual(action["target_field"], "RITMGuidance")
        self.assertIn("Manage User RITM", action["proposed_value"])
        self.assertIn("Delegated Administrator", action["proposed_value"])

    def test_scenario_2_mulesoft_automated_deactivation(self):
        """2. Automated deactivation from MuleSoft integration process -> LOGIN-3-ESCALATE / MuleSoft."""
        ctx = {
            "incident_summary": "Account deactivated by MuleSoft",
            "incident_description": "User deactivated via automated MuleSoft integration sync process",
        }
        # Mock user details with MuleSoft actor
        cache = {
            "User": {
                "Id": "005xxMULESOFTUSER",
                "Username": "mule.user@acme.corp",
                "Email": "mule.user@acme.corp",
                "IsActive": False,
                "DeactivatedBy": "MuleSoft Integration User",
                "MuleSoftIntegrationUser": True,
            }
        }
        diag, _, _ = self.flow.execute("mule.user@acme.corp", context=ctx, evidence_cache=cache)
        self.assertEqual(diag.issue_code, "LOGIN-3")
        self.assertIn("MuleSoft", diag.decision_basis)

        # Plan resolution
        state = {
            "incident": {"incident_id": "INC1002"},
            "affected_user": cache["User"],
            "diagnosis_result": diag.model_dump(),
            "skill_refs": {"issue_code": "LOGIN-3"},
        }
        updated = self.resolution.plan_resolution(state)
        action = updated["resolution_plan"]["proposed_action"]
        self.assertEqual(action["target_field"], "Guidance")
        self.assertIn("MuleSoft", action["proposed_value"])

    def test_scenario_3_federation_id_blank(self):
        """3. FederationIdentifier is blank or null -> Update FederationIdentifier with EmployeeNumber."""
        ctx = {
            "incident_summary": "SSO Login Failure",
            "incident_description": "User jane.doe@acme.corp cannot sign in via SSO. Federation ID is blank.",
        }
        diag, _, _ = self.flow.execute("jane.doe@acme.corp", context=ctx)
        self.assertEqual(diag.status, "confirmed")
        self.assertEqual(diag.issue_code, "LOGIN-4")

        # Plan resolution
        user = salesforce_get_user_details("005xx000001LOGIN4")
        self.assertEqual(user["EmployeeNumber"], "EMP-00104")
        self.assertIsNone(user["FederationIdentifier"])

        state = {
            "incident": {"incident_id": "INC1004"},
            "affected_user": user,
            "diagnosis_result": diag.model_dump(),
            "skill_refs": {"issue_code": "LOGIN-4"},
        }
        updated = self.resolution.plan_resolution(state)
        action = updated["resolution_plan"]["proposed_action"]

        self.assertEqual(action["target_field"], "FederationIdentifier")
        # Must strictly be EmployeeNumber, NOT email or username!
        self.assertEqual(action["proposed_value"], "EMP-00104")
        self.assertNotIn("@", action["proposed_value"])

    def test_scenario_4_federation_id_suspended(self):
        """4. FederationIdentifier contains suspended/frozen -> Inform user to raise Manage User RITM."""
        ctx = {
            "incident_summary": "SSO account suspended",
            "incident_description": "User has suspended federation identifier",
        }
        cache = {
            "User": {
                "Id": "005xxSUSPENDED1",
                "Username": "suspended.user@acme.corp",
                "Email": "suspended.user@acme.corp",
                "EmployeeNumber": "EMP-99001",
                "IsActive": True,
                "UserType": "Standard",
                "FederationIdentifier": "SUSPENDED_INACTIVE_USER_99",
            }
        }
        diag, _, _ = self.flow.execute("suspended.user@acme.corp", context=ctx, evidence_cache=cache)
        self.assertEqual(diag.status, "confirmed")
        self.assertEqual(diag.issue_code, "LOGIN-5")
        self.assertIn("suspended", diag.decision_basis.lower())

        state = {
            "incident": {"incident_id": "INC1005"},
            "affected_user": cache["User"],
            "diagnosis_result": diag.model_dump(),
            "skill_refs": {"issue_code": "LOGIN-5"},
        }
        updated = self.resolution.plan_resolution(state)
        action = updated["resolution_plan"]["proposed_action"]

        self.assertEqual(action["target_field"], "RITMGuidance")
        self.assertIn("Manage User RITM", action["proposed_value"])

    def test_scenario_5_azure_workday_mismatch(self):
        """5. FederationIdentifier != EmployeeNumber -> LOGIN-6 Engage Azure Team."""
        user = salesforce_get_user_details("005xx000006LOGIN6")
        self.assertEqual(user["EmployeeNumber"], "EMP-20491")
        self.assertEqual(user["FederationIdentifier"], "EMP-10022")

        ctx = {
            "incident_summary": "Rehire login error",
            "incident_description": "User daniel.ortiz@acme.corp re-hire employee number is EMP-20491 but Salesforce has old ID",
        }
        diag, _, _ = self.flow.execute("daniel.ortiz@acme.corp", context=ctx)
        self.assertEqual(diag.status, "confirmed")
        self.assertEqual(diag.issue_code, "LOGIN-6")

        state = {
            "incident": {"incident_id": "INC1006"},
            "affected_user": user,
            "diagnosis_result": diag.model_dump(),
            "skill_refs": {"issue_code": "LOGIN-6"},
        }
        updated = self.resolution.plan_resolution(state)
        action = updated["resolution_plan"]["proposed_action"]
        self.assertEqual(action["target_field"], "FederationIdentifier")
        # Must strictly be EmployeeNumber
        self.assertEqual(action["proposed_value"], "EMP-20491")
        self.assertIn("Azure", action["justification"])

    def test_scenario_6_ciam_external_user(self):
        """6. External User with CIAM UUID mismatch -> LOGIN-7 Engage CIAM Team."""
        cache = {
            "User": {
                "Id": "005xxCIAMEXT1",
                "Username": "external.partner@partner.corp",
                "Email": "external.partner@partner.corp",
                "IsActive": True,
                "UserType": "PowerPartner",
                "FederationIdentifier": "ciam-uuid-88371-abc-invalid",
                "CIAMSyncMismatch": True,
            }
        }
        ctx = {
            "incident_summary": "Partner portal login failure",
            "incident_description": "External partner user cannot sign in",
        }
        diag, _, _ = self.flow.execute("external.partner@partner.corp", context=ctx, evidence_cache=cache)
        self.assertEqual(diag.issue_code, "LOGIN-7")

        state = {
            "incident": {"incident_id": "INC1007"},
            "affected_user": cache["User"],
            "diagnosis_result": diag.model_dump(),
            "skill_refs": {"issue_code": "LOGIN-7"},
        }
        updated = self.resolution.plan_resolution(state)
        action = updated["resolution_plan"]["proposed_action"]
        self.assertEqual(action["target_field"], "Guidance")
        self.assertIn("CIAM", action["proposed_value"])


if __name__ == "__main__":
    unittest.main()
