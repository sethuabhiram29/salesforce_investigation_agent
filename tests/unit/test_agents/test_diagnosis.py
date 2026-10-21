"""Tests for the Diagnosis Agent."""

import unittest

from app.agents.diagnosis.agent import DiagnosisAgent
from app.agents.diagnosis.tool_graph import DiagnosisToolGraph
from app.models.state import InvestigationState
from app.tools.salesforce import reset_fixture_state


class TestDiagnosisAgent(unittest.TestCase):
    def setUp(self):
        reset_fixture_state()
        self.agent = DiagnosisAgent()
        self.tool_graph = DiagnosisToolGraph()

    def tearDown(self):
        reset_fixture_state()

    def test_login4_diagnosis_confirmed(self):
        # Jane Doe has missing FederationIdentifier and is active
        state: InvestigationState = {
            "incident": {
                "incident_id": "INC1001",
                "short_description": "Cannot login with SSO",
                "description": "User jane.doe@acme.corp gets SAML authentication error",
                "caller_email": "jane.doe@acme.corp",
            },
            "affected_user": {
                "Email": "jane.doe@acme.corp",
                "Username": "jane.doe@acme.corp",
            },
            "skill_refs": {"issue_code": "LOGIN-4", "stage": "diagnosis"},
        }

        updated_state = self.agent.run(state)
        diag = updated_state.get("diagnosis_result", {})

        self.assertEqual(diag.get("status"), "confirmed")
        self.assertEqual(diag.get("issue_code"), "LOGIN-4")
        self.assertGreater(len(diag.get("findings", [])), 0)

        # Verify evidence grounding
        evidence_ids = {e["evidence_id"] for e in updated_state.get("evidence", [])}
        for finding in diag.get("findings", []):
            for ref in finding.get("evidence_refs", []):
                self.assertIn(ref, evidence_ids)

    def test_login3a_diagnosis_confirmed(self):
        # John Smith is deactivated delegated admin
        state: InvestigationState = {
            "incident": {
                "incident_id": "INC1002",
                "short_description": "Delegated admin cannot sign in",
                "description": "john.smith@acme.corp cannot login after leave",
                "caller_email": "john.smith@acme.corp",
            },
            "affected_user": {
                "Email": "john.smith@acme.corp",
                "Username": "john.smith@acme.corp",
            },
            "skill_refs": {"issue_code": "LOGIN-3", "stage": "diagnosis"},
        }

        updated_state = self.agent.run(state)
        diag = updated_state.get("diagnosis_result", {})

        self.assertEqual(diag.get("status"), "confirmed")
        self.assertEqual(diag.get("issue_code"), "LOGIN-3")
        self.assertEqual(diag.get("observed_values", {}).get("deactivation_actor"), "Delegated Administrator")
        self.assertEqual(diag.get("recommended_action"), "resolution")

    def test_dynamic_investigation_pivot(self):
        # John Smith is actually inactive (LOGIN-3), but initial hypothesis is LOGIN-4
        state: InvestigationState = {
            "incident": {
                "incident_id": "INC1003",
                "short_description": "Login problem",
                "description": "john.smith@acme.corp cannot sign in",
                "caller_email": "john.smith@acme.corp",
            },
            "affected_user": {
                "Email": "john.smith@acme.corp",
            },
            # Intentionally pass LOGIN-4 as initial candidate
            "skill_refs": {"issue_code": "LOGIN-4", "stage": "diagnosis"},
        }

        updated_state = self.agent.run(state)
        diag = updated_state.get("diagnosis_result", {})

        # Should dynamically pivot from LOGIN-4 to LOGIN-3 because user is inactive!
        self.assertEqual(diag.get("status"), "confirmed")
        self.assertEqual(diag.get("issue_code"), "LOGIN-3")
        self.assertEqual(diag.get("observed_values", {}).get("deactivation_actor"), "Delegated Administrator")

    def test_ambiguous_or_missing_user_does_not_fabricate(self):
        state: InvestigationState = {
            "incident": {
                "incident_id": "INC1004",
                "short_description": "Can't login",
                "description": "unknown_ghost_user@acme.corp cannot login",
                "caller_email": "unknown_ghost_user@acme.corp",
            },
            "affected_user": {
                "Email": "unknown_ghost_user@acme.corp",
            },
            "skill_refs": {"issue_code": "LOGIN-4", "stage": "diagnosis"},
        }

        updated_state = self.agent.run(state)
        diag = updated_state.get("diagnosis_result", {})
        self.assertEqual(diag.get("status"), "ambiguous_identity")
        self.assertEqual(len(diag.get("findings", [])), 0)
        self.assertEqual(diag.get("recommended_action"), "escalate")

    def test_cross_domain_fallback_for_vague_ticket(self):
        # Sarah Connor has general "Cannot access salesforce" ticket.
        # She is active and has FederationIdentifier (contradicting LOGIN domain),
        # but she lacks Edit permissions on Account.
        state: InvestigationState = {
            "incident": {
                "incident_id": "INC1005",
                "short_description": "Cannot access salesforce at all",
                "description": "User sarah.connor@acme.corp cannot access salesforce at all. Please help.",
                "caller_email": "sarah.connor@acme.corp",
            },
            "affected_user": {
                "Email": "sarah.connor@acme.corp",
            },
            "triage_result": {
                "domain": "LOGIN",  # Initial domain assigned to general access ticket
                "is_ambiguous": False,
            },
        }

        updated_state = self.agent.run(state)
        diag = updated_state.get("diagnosis_result", {})

        # Should fall back from LOGIN to OBJECT and confirm OBJECT-1!
        self.assertEqual(diag.get("status"), "confirmed")
        self.assertIn(diag.get("issue_code"), ["OBJECT-1", "OBJECT-2"])
        self.assertEqual(diag.get("recommended_action"), "resolution")

    def test_record_level_access_diagnosis(self):
        # Sarah Connor cannot access specific Opportunity 006xx000001OPP
        state: InvestigationState = {
            "incident": {
                "incident_id": "INC1006",
                "short_description": "Cannot view Opportunity record",
                "description": "User sarah.connor@acme.corp cannot access Opportunity 006xx000001OPP.",
                "caller_email": "sarah.connor@acme.corp",
            },
            "affected_user": {
                "Email": "sarah.connor@acme.corp",
            },
            "triage_result": {
                "domain": "RECORD",
                "is_ambiguous": False,
                "extracted_entities": {"record_ids": ["006xx000001OPP"]},
            },
        }

        updated_state = self.agent.run(state)
        diag = updated_state.get("diagnosis_result", {})

        self.assertEqual(diag.get("status"), "confirmed")
        self.assertIn(diag.get("issue_code"), ["RECORD-3", "RECORD-2"])
        self.assertEqual(diag.get("recommended_action"), "resolution")

    def test_application_permission_set_diagnosis(self):
        # Sarah Connor cannot access CC360 app (missing CC360 Community User permission set)
        state: InvestigationState = {
            "incident": {
                "incident_id": "INC1007",
                "short_description": "CC360 community application portal blocked",
                "description": "User sarah.connor@acme.corp cannot access CC360 portal.",
                "caller_email": "sarah.connor@acme.corp",
            },
            "affected_user": {
                "Email": "sarah.connor@acme.corp",
            },
            "triage_result": {
                "domain": "APPLICATION",
                "is_ambiguous": False,
            },
        }

        updated_state = self.agent.run(state)
        diag = updated_state.get("diagnosis_result", {})

        self.assertEqual(diag.get("status"), "confirmed")
        self.assertEqual(diag.get("issue_code"), "APPLICATION-1")
        self.assertEqual(diag.get("recommended_action"), "resolution")

    def test_mobile_app_guidance_diagnosis(self):
        # Active user reports mobile app login failure -> confirms LOGIN-8 per SOP LOGIN-008
        state: InvestigationState = {
            "incident": {
                "incident_id": "INC1008",
                "short_description": "Salesforce app on my phone will not sign in",
                "description": "I installed the Salesforce mobile app on my phone. It spins for a while and says login failed.",
                "caller_email": "sarah.connor@acme.corp",
            },
            "affected_user": {
                "Email": "sarah.connor@acme.corp",
            },
            "triage_result": {
                "domain": "LOGIN",
                "is_ambiguous": False,
            },
        }

        updated_state = self.agent.run(state)
        diag = updated_state.get("diagnosis_result", {})

        self.assertEqual(diag.get("status"), "confirmed")
        self.assertEqual(diag.get("issue_code"), "LOGIN-8")
        self.assertEqual(diag.get("recommended_action"), "resolution")

    def test_mobile_app_diagnosis_with_sop_3digit_code_and_short_summary(self):
        # Explicitly tests 3-digit candidate code "LOGIN-008" with exact phrase from user
        diag_res, _ = self.tool_graph.run(
            candidate_issue_code="LOGIN-008",
            target_identifier="sarah.connor@acme.corp",
            context={
                "incident_summary": "Cannot sign in salesforce mobile app",
                "incident_description": "User cannot sign in salesforce mobile app",
            },
        )
        self.assertEqual(diag_res.status, "confirmed")
        self.assertEqual(diag_res.issue_code, "LOGIN-8")
        self.assertEqual(diag_res.recommended_action, "resolution")


if __name__ == "__main__":
    unittest.main()
