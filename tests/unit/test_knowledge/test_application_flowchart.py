"""Unit tests for Master Multi-Domain Triage & Application Issues Decision Tree Knowledge Graph."""

import unittest
from app.knowledge.neo4j_repository import neo4j_repository
from app.agents.diagnosis.structured_flow import StructuredDiagnosisFlow
from app.tools.salesforce import reset_fixture_state


class TestApplicationFlowchartKnowledgeGraph(unittest.TestCase):
    """Test suite for Master Triage Agent routing and Application Issues Decision Tree."""

    def setUp(self):
        reset_fixture_state()
        self.flow = StructuredDiagnosisFlow()

    def test_master_triage_agent_root_node(self):
        """Verify NODE_TRIAGE_AGENT is the master root node and routes to LOGIN and APPLICATION."""
        master_root = neo4j_repository.get_triage_master_node()
        self.assertEqual(master_root["id"], "NODE_TRIAGE_AGENT")
        self.assertEqual(master_root["name"], "Triage Agent")

        transitions = neo4j_repository.get_node_transitions("NODE_TRIAGE_AGENT")
        self.assertIn("domain_routes", transitions)
        routes = transitions["domain_routes"]
        self.assertEqual(routes.get("LOGIN"), "NODE_TRIAGE_RESULT")
        self.assertEqual(routes.get("APPLICATION"), "NODE_APP_TRIAGE_RESULT")

    def test_domain_start_nodes_retrieval(self):
        """Verify each domain resolves to its respective starting node from the knowledge graph."""
        login_start = neo4j_repository.get_flowchart_start_node("LOGIN")
        self.assertEqual(login_start["id"], "NODE_TRIAGE_RESULT")

        app_start = neo4j_repository.get_flowchart_start_node("APPLICATION")
        self.assertEqual(app_start["id"], "NODE_APP_TRIAGE_RESULT")
        self.assertEqual(app_start["domain"], "APPLICATION")

    def test_app_flow_inactive_user_routes_to_login(self):
        """Verify inactive user in Application domain is routed to Login Issue terminal node."""
        res, ev, steps = self.flow.execute(
            target_identifier="john.smith@acme.corp",
            context={
                "domain": "APPLICATION",
                "short_description": "User cannot open CC360 portal",
                "description": "User account inactive when checking CC360",
            },
        )
        self.assertEqual(res.issue_code, "LOGIN-ISSUE-INACTIVE")
        terminal_steps = [s for s in steps if s.get("graph_node_id") == "TERMINAL_APP_LOGIN_ISSUE"]
        self.assertTrue(len(terminal_steps) > 0)

    def test_app_flow_cc360_permission_missing(self):
        """Verify active user with CC360 issue and no permission set confirms APP-CC360-PS-MISSING."""
        res, ev, steps = self.flow.execute(
            target_identifier="cc360.user@acme.corp",
            context={
                "domain": "APPLICATION",
                "short_description": "User unable to access CC360 app",
                "description": "Caller reports permission error accessing Customer 360",
            },
        )
        self.assertEqual(res.status, "confirmed")
        self.assertEqual(res.issue_code, "APP-CC360-PS-MISSING")

    def test_app_flow_community_permission_missing(self):
        """Verify active user with Pharma app issue and no community set confirms APP-COMMUNITY-PS-MISSING."""
        res, ev, steps = self.flow.execute(
            target_identifier="community.user@acme.corp",
            context={
                "domain": "APPLICATION",
                "short_description": "User cannot access Pharma System app",
                "description": "Pharma pure fishing community user permission missing",
            },
        )
        self.assertEqual(res.status, "confirmed")
        self.assertEqual(res.issue_code, "APP-COMMUNITY-PS-MISSING")

    def test_app_flow_clm_license_missing(self):
        """Verify Conga CLM new user onboarding symptom confirms APP-CLM-LICENSE-MISSING."""
        res, ev, steps = self.flow.execute(
            target_identifier="clm.user@acme.corp",
            context={
                "domain": "APPLICATION",
                "short_description": "CLM New User Onboarding Issue",
                "description": "User needs Conga CLM package license for onboarding",
            },
        )
        self.assertEqual(res.status, "confirmed")
        self.assertEqual(res.issue_code, "APP-CLM-LICENSE-MISSING")

    def test_app_flow_crm_content_user_disabled(self):
        """Verify CRM Content symptom with disabled flag confirms APP-CRM-CONTENT-DISABLED."""
        res, ev, steps = self.flow.execute(
            target_identifier="crmcontent.user@acme.corp",
            context={
                "domain": "APPLICATION",
                "short_description": "Conga CLM CRM Content Library Issue",
                "description": "User cannot access CRM Content workspace library in Conga",
            },
        )
        self.assertEqual(res.status, "confirmed")
        self.assertEqual(res.issue_code, "APP-CRM-CONTENT-DISABLED")

    def test_app_flow_xauthor_permission_missing(self):
        """Verify Conga X-Author related issue confirms APP-XAUTHOR-PS-MISSING."""
        res, ev, steps = self.flow.execute(
            target_identifier="xauthor.user@acme.corp",
            context={
                "domain": "APPLICATION",
                "short_description": "Conga X-Author Excel Add-in Error",
                "description": "User reports X-Author related issue when opening contract templates",
            },
        )
        self.assertEqual(res.status, "confirmed")
        self.assertEqual(res.issue_code, "APP-XAUTHOR-PS-MISSING")

    def test_app_flow_bu_missing(self):
        """Verify Conga user with missing Business Unit confirms APP-BU-MISSING."""
        res, ev, steps = self.flow.execute(
            target_identifier="bumissing.user@acme.corp",
            context={
                "domain": "APPLICATION",
                "short_description": "Conga Agreement Access",
                "description": "User has X-Author permission but BU missing in profile",
            },
        )
        self.assertEqual(res.status, "confirmed")
        self.assertEqual(res.issue_code, "APP-BU-MISSING")

    def test_app_flow_apttus_permission_missing(self):
        """Verify Conga user with valid BU but missing Apttus permission confirms APP-APTTUS-PS-MISSING."""
        res, ev, steps = self.flow.execute(
            target_identifier="apttus.user@acme.corp",
            context={
                "domain": "APPLICATION",
                "short_description": "Conga Apttus Agreement Permission Issue",
                "description": "User cannot view Apttus agreement records in Conga",
            },
        )
        self.assertEqual(res.status, "confirmed")
        self.assertEqual(res.issue_code, "APP-APTTUS-PS-MISSING")

    def test_app_flow_unhandled_app_routes_to_l3_queue(self):
        """Verify unhandled application routes to L3 Queue Resolver."""
        res, ev, steps = self.flow.execute(
            target_identifier="alex.taylor@acme.corp",
            context={
                "domain": "APPLICATION",
                "short_description": "Custom Billing Engine Error",
                "description": "Error in non-Conga unhandled finance billing module",
            },
        )
        self.assertEqual(res.issue_code, "OUT-OF-SCOPE-L3-QUEUE")

    def test_app_flow_full_permissions_routes_to_l3_group(self):
        """Verify user with all CC360 permissions already present routes to L3 Group Resolver."""
        res, ev, steps = self.flow.execute(
            target_identifier="alex.taylor@acme.corp",
            context={
                "domain": "APPLICATION",
                "short_description": "CC360 Internal Server Error",
                "description": "User already has CC360 Community User permission set but gets unexpected 500 error",
            },
        )
        self.assertEqual(res.issue_code, "OUT-OF-SCOPE-L3-GROUP")


if __name__ == "__main__":
    unittest.main()
