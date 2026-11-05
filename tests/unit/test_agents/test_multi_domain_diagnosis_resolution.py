"""End-to-End Multi-Domain Diagnosis and Resolution Agent Tests.

Verifies dynamic tool-calling from Salesforce MCP, root cause confirmation via
knowledge graph, canonical skill file loading, and remediation planning across
all domains: APPLICATION, OBJECT, and RECORD.
"""

import unittest
from app.agents.diagnosis.agent import DiagnosisAgent
from app.agents.resolution.agent import ResolutionAgent
from app.models.state import InvestigationState
from app.tools.salesforce import reset_fixture_state


class TestMultiDomainDiagnosisResolution(unittest.TestCase):
    def setUp(self):
        reset_fixture_state()
        self.diagnosis_agent = DiagnosisAgent()
        self.resolution_agent = ResolutionAgent()

    def tearDown(self):
        reset_fixture_state()

    def test_application_cc360_diagnosis_and_resolution(self):
        """Test APPLICATION domain: CC360 permission set missing diagnosis and RITM resolution."""
        state: InvestigationState = {
            "incident": {
                "incident_id": "INC-APP-101",
                "short_description": "User unable to access CC360 App",
                "description": "User sarah.connor@acme.corp cannot access CC360 portal",
                "caller_email": "sarah.connor@acme.corp",
            },
            "affected_user": {
                "Id": "005xx000003OBJECT1",
                "Email": "sarah.connor@acme.corp",
                "Username": "sarah.connor@acme.corp",
                "IsActive": True,
            },
            "triage_result": {
                "domain": "APPLICATION",
                "extracted_entities": {"objects": ["User"]},
            },
            "evidence_cache": {
                "permission_sets": [],
            },
        }

        # 1. Run Diagnosis Agent
        diag_state = self.diagnosis_agent.run(state)
        diag_res = diag_state.get("diagnosis_result", {})
        self.assertEqual(diag_res.get("status"), "confirmed")
        self.assertIn(diag_res.get("issue_code"), ["APP-CC360-PS", "APP-CC360-PS-MISSING"])

        # Verify evidence was emitted by dynamic tool calling
        tools_called = [e.get("tool_name") for e in diag_state.get("evidence", [])]
        self.assertIn("salesforce_get_user_permission_sets", tools_called)

        # 2. Run Resolution Planning Agent
        res_state = self.resolution_agent.plan_resolution(diag_state)
        plan = res_state.get("resolution_plan", {})
        self.assertIn(plan.get("issue_code"), ["APP-CC360-PS", "APP-CC360-PS-MISSING"])
        self.assertTrue(plan.get("requires_approval"))
        action = plan.get("proposed_action", {})
        self.assertEqual(action.get("target_field"), "RITMGuidance")
        self.assertIn("CC360 Community User", action.get("proposed_value", ""))
        self.assertIn("TCS-America-SFDC", action.get("proposed_value", ""))

        # Verify canonical skill file was loaded
        skill_ref = res_state.get("skill_refs", {})
        self.assertIn("APP-CC360-permission-set-missing.md", skill_ref.get("file_path", ""))

    def test_application_crm_content_diagnosis_and_resolution(self):
        """Test APPLICATION domain: CRM Content User checkbox disabled."""
        state: InvestigationState = {
            "incident": {
                "incident_id": "INC-APP-102",
                "short_description": "Cannot access CRM Content Library",
                "description": "User sarah.connor@acme.corp cannot view content library",
                "caller_email": "sarah.connor@acme.corp",
            },
            "affected_user": {
                "Id": "005xx000003OBJECT1",
                "Email": "sarah.connor@acme.corp",
                "Username": "sarah.connor@acme.corp",
                "IsActive": True,
            },
            "triage_result": {
                "domain": "APPLICATION",
            },
            "evidence_cache": {
                "permission_sets": ["CC360 Community User", "Cmty-PS Community User"],
                "package_licenses": ["Conga Contract Lifecycle Management"],
                "has_crm_content_symptom": True,
                "is_crm_content_user_enabled": False,
            },
        }

        # 1. Run Diagnosis Agent
        diag_state = self.diagnosis_agent.run(state)
        diag_res = diag_state.get("diagnosis_result", {})
        self.assertEqual(diag_res.get("status"), "confirmed")
        self.assertIn(diag_res.get("issue_code"), ["APP-CRM-CONTENT", "APP-CRM-CONTENT-DISABLED"])

        # 2. Run Resolution Planning Agent
        res_state = self.resolution_agent.plan_resolution(diag_state)
        plan = res_state.get("resolution_plan", {})
        action = plan.get("proposed_action", {})
        self.assertEqual(action.get("target_field"), "UserPermissionsSFContentUser")
        self.assertEqual(action.get("proposed_value"), True)

    def test_object_wizard_country_blank_diagnosis_and_resolution(self):
        """Test OBJECT domain: Blank Wizard_Country__c field on Contact."""
        state: InvestigationState = {
            "incident": {
                "incident_id": "INC-OBJ-201",
                "short_description": "User unable to search products in Wizard App",
                "description": "Wizard App product search returns error",
                "caller_email": "sarah.connor@acme.corp",
            },
            "affected_user": {
                "Id": "005xx000003OBJECT1",
                "Email": "sarah.connor@acme.corp",
                "Username": "sarah.connor@acme.corp",
                "Country": "US",
                "IsActive": True,
            },
            "triage_result": {
                "domain": "OBJECT",
            },
            "evidence_cache": {
                "has_wizard_symptom": True,
                "is_wizard_country_blank": True,
                "wizard_country": None,
            },
        }

        # 1. Run Diagnosis Agent
        diag_state = self.diagnosis_agent.run(state)
        diag_res = diag_state.get("diagnosis_result", {})
        self.assertEqual(diag_res.get("status"), "confirmed")
        self.assertEqual(diag_res.get("issue_code"), "OBJECT-1")

        # Verify dynamic tool call for contact wizard details
        tools_called = [e.get("tool_name") for e in diag_state.get("evidence", [])]
        self.assertIn("salesforce_get_contact_wizard_details", tools_called)

        # 2. Run Resolution Planning Agent
        res_state = self.resolution_agent.plan_resolution(diag_state)
        plan = res_state.get("resolution_plan", {})
        self.assertEqual(plan.get("issue_code"), "OBJECT-1")
        action = plan.get("proposed_action", {})
        self.assertEqual(action.get("target_field"), "WizardCountry")
        self.assertEqual(action.get("proposed_value"), "US")
        skill_ref = res_state.get("skill_refs", {})
        self.assertIn("OBJECT-1-wizard-country-blank.md", skill_ref.get("file_path", ""))

    def test_record_report_folder_access_diagnosis_and_resolution(self):
        """Test RECORD domain: Report folder access missing."""
        state: InvestigationState = {
            "incident": {
                "incident_id": "INC-REC-301",
                "short_description": "Cannot view quarterly sales report",
                "description": "Report access error folder permission missing",
                "caller_email": "sarah.connor@acme.corp",
            },
            "affected_user": {
                "Id": "005xx000003OBJECT1",
                "Email": "sarah.connor@acme.corp",
                "Username": "sarah.connor@acme.corp",
                "IsActive": True,
            },
            "triage_result": {
                "domain": "RECORD",
            },
            "evidence_cache": {
                "rec_is_report_dashboard": True,
                "rec_missing_obj_perms_report": False,
                "rec_is_folder_info_avail": True,
                "rec_folder_access_missing": True,
            },
        }

        # 1. Run Diagnosis Agent
        diag_state = self.diagnosis_agent.run(state)
        diag_res = diag_state.get("diagnosis_result", {})
        self.assertEqual(diag_res.get("status"), "confirmed")
        self.assertEqual(diag_res.get("issue_code"), "RECORD-1")

        # 2. Run Resolution Planning Agent
        res_state = self.resolution_agent.plan_resolution(diag_state)
        plan = res_state.get("resolution_plan", {})
        self.assertEqual(plan.get("issue_code"), "RECORD-1")
        action = plan.get("proposed_action", {})
        self.assertEqual(action.get("target_field"), "Guidance")
        self.assertIn("Folder", action.get("proposed_value", ""))
        skill_ref = res_state.get("skill_refs", {})
        self.assertTrue("RECORD-1B-report-folder-access.md" in skill_ref.get("file_path", "") or "RECORD-1-report-folder-access.md" in skill_ref.get("file_path", ""))

    def test_record_opp_case_sharing_diagnosis_and_resolution(self):
        """Test RECORD domain: Opportunity record sharing missing."""
        state: InvestigationState = {
            "incident": {
                "incident_id": "INC-REC-302",
                "short_description": "Cannot open Opportunity 006xx000001",
                "description": "User cannot access Opportunity record Insufficient Privileges",
                "caller_email": "sarah.connor@acme.corp",
            },
            "affected_user": {
                "Id": "005xx000003OBJECT1",
                "Email": "sarah.connor@acme.corp",
                "Username": "sarah.connor@acme.corp",
                "IsActive": True,
            },
            "triage_result": {
                "domain": "RECORD",
            },
            "evidence_cache": {
                "rec_is_report_dashboard": False,
                "rec_is_opp_case": True,
                "rec_missing_obj_perms_opp_case": False,
                "rec_opp_case_cannot_access": True,
                "rec_opp_case_has_read_access": False,
                "rec_opp_case_missing_sharing_path": True,
            },
        }

        # 1. Run Diagnosis Agent
        diag_state = self.diagnosis_agent.run(state)
        diag_res = diag_state.get("diagnosis_result", {})
        self.assertEqual(diag_res.get("status"), "confirmed")
        self.assertEqual(diag_res.get("issue_code"), "RECORD-2")

        # 2. Run Resolution Planning Agent
        res_state = self.resolution_agent.plan_resolution(diag_state)
        plan = res_state.get("resolution_plan", {})
        self.assertEqual(plan.get("issue_code"), "RECORD-2")
        action = plan.get("proposed_action", {})
        self.assertEqual(action.get("target_field"), "Guidance")
        self.assertIn("Opportunity Team", action.get("proposed_value", ""))
        skill_ref = res_state.get("skill_refs", {})
        self.assertTrue("RECORD-2B-opp-case-sharing.md" in skill_ref.get("file_path", "") or "RECORD-2-opp-case-sharing.md" in skill_ref.get("file_path", ""))


if __name__ == "__main__":
    unittest.main()
