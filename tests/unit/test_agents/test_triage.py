"""Tests for the Triage Agent, 4-Domain Classification, and Identity Resolution."""

import unittest
from unittest.mock import patch

from app.agents.triage.agent import TriageAgent
from app.models.state import InvestigationState
from app.tools.salesforce import reset_fixture_state


class TestTriageAgent(unittest.TestCase):
    def setUp(self):
        reset_fixture_state()
        self.agent = TriageAgent()

    @patch("app.agents.triage.agent.fetch_historical_context_for_state")
    def test_login_classification(self, mock_history):
        mock_history.return_value = [{"incident_id": "INC01", "root_cause": "LOGIN-4"}]

        state: InvestigationState = {
            "incident": {
                "incident_id": "INC101",
                "short_description": "Single sign on error",
                "description": "User jane.doe@acme.corp cannot authenticate with Okta SAML SSO",
                "caller_email": "jane.doe@acme.corp",
            }
        }

        res = self.agent.run(state)
        triage = res.get("triage_result", {})

        self.assertEqual(triage.get("domain"), "LOGIN")
        self.assertFalse(triage.get("is_ambiguous"))
        self.assertIn("jane.doe@acme.corp", triage.get("extracted_entities", {}).get("emails", []))
        self.assertEqual(res.get("affected_user", {}).get("Username"), "jane.doe@acme.corp")

    @patch("app.agents.triage.agent.fetch_historical_context_for_state")
    def test_affected_user_resolution_different_from_caller(self, mock_history):
        mock_history.return_value = []

        # IT Manager Bob is calling on behalf of Jane Doe
        state: InvestigationState = {
            "incident": {
                "incident_id": "INC102",
                "short_description": "Employee cannot log in",
                "description": "Please check access for my team member jane.doe@acme.corp. She is blocked.",
                "caller_email": "bob.manager@acme.corp",
            }
        }

        res = self.agent.run(state)
        self.assertEqual(res.get("affected_user", {}).get("Username"), "jane.doe@acme.corp")
        self.assertTrue(res.get("affected_user", {}).get("resolution_source", "").startswith("description"))

    @patch("app.agents.triage.agent.fetch_historical_context_for_state")
    def test_affected_user_via_on_behalf_field(self, mock_history):
        mock_history.return_value = []

        # Caller is IT Helpdesk, ticket has on_behalf_of field
        state: InvestigationState = {
            "incident": {
                "incident_id": "INC102B",
                "short_description": "Login failure reported",
                "description": "User reported SSO federation failure this morning.",
                "caller_email": "helpdesk@acme.corp",
                "on_behalf_of": "jane.doe@acme.corp",
            }
        }

        res = self.agent.run(state)
        self.assertEqual(res.get("affected_user", {}).get("Username"), "jane.doe@acme.corp")
        self.assertEqual(res.get("affected_user", {}).get("resolution_source"), "on_behalf_incident_field")

    @patch("app.agents.triage.agent.fetch_historical_context_for_state")
    def test_object_domain_classification(self, mock_history):
        mock_history.return_value = []

        state: InvestigationState = {
            "incident": {
                "incident_id": "INC103",
                "short_description": "Insufficient privileges on Account",
                "description": "User sarah.connor@acme.corp cannot edit Account record billing address",
                "caller_email": "sarah.connor@acme.corp",
            }
        }

        res = self.agent.run(state)
        triage = res.get("triage_result", {})
        self.assertEqual(triage.get("domain"), "OBJECT")
        self.assertIn("Account", triage.get("extracted_entities", {}).get("objects", []))

    @patch("app.agents.triage.agent.fetch_historical_context_for_state")
    def test_record_domain_classification(self, mock_history):
        mock_history.return_value = []

        state: InvestigationState = {
            "incident": {
                "incident_id": "INC105",
                "short_description": "Report and dashboard sharing access",
                "description": "User sarah.connor@acme.corp cannot access executive Q3 sales dashboard and reports",
                "caller_email": "sarah.connor@acme.corp",
            }
        }

        res = self.agent.run(state)
        triage = res.get("triage_result", {})
        self.assertEqual(triage.get("domain"), "RECORD")

    @patch("app.agents.triage.agent.fetch_historical_context_for_state")
    def test_application_domain_classification(self, mock_history):
        mock_history.return_value = []

        state: InvestigationState = {
            "incident": {
                "incident_id": "INC106",
                "short_description": "CC360 App Community portal access error",
                "description": "User sarah.connor@acme.corp cannot access CC360 community application portal",
                "caller_email": "sarah.connor@acme.corp",
            }
        }

        res = self.agent.run(state)
        triage = res.get("triage_result", {})
        self.assertEqual(triage.get("domain"), "APPLICATION")

    @patch("app.agents.triage.agent.fetch_historical_context_for_state")
    def test_mirror_user_extraction_in_object_ticket(self, mock_history):
        mock_history.return_value = []

        # Sarah Connor cannot edit Account, but mentions comparison with Alex Taylor
        state: InvestigationState = {
            "incident": {
                "incident_id": "INC107",
                "short_description": "Cannot edit account details",
                "description": (
                    "User sarah.connor@acme.corp lacks permission to edit Account records. "
                    "Working fine for alex.taylor@acme.corp with same sales profile."
                ),
                "caller_email": "sarah.connor@acme.corp",
            }
        }

        res = self.agent.run(state)
        triage = res.get("triage_result", {})
        self.assertEqual(triage.get("domain"), "OBJECT")

        # Affected user must be Sarah Connor
        self.assertEqual(res.get("affected_user", {}).get("Email"), "sarah.connor@acme.corp")

        # Mirror user must be Alex Taylor
        mirror = res.get("mirror_user")
        self.assertIsNotNone(mirror)
        self.assertEqual(mirror.get("Email"), "alex.taylor@acme.corp")
        self.assertTrue(mirror.get("is_mirror_user"))

    @patch("app.agents.triage.agent.fetch_historical_context_for_state")
    def test_vague_description_ambiguity(self, mock_history):
        mock_history.return_value = []

        state: InvestigationState = {
            "incident": {
                "incident_id": "INC104",
                "short_description": "Can't access salesforce",
                "description": "Cannot access",
                "caller_email": "jane.doe@acme.corp",
            }
        }

        res = self.agent.run(state)
        triage = res.get("triage_result", {})
        self.assertTrue(triage.get("is_ambiguous"))

    @patch("app.agents.triage.agent.fetch_historical_context_for_state")
    def test_affected_user_resolution_via_full_name(self, mock_history):
        mock_history.return_value = []

        # IT support ticket mentions full name "John Smith" without an email
        state: InvestigationState = {
            "incident": {
                "incident_id": "INC105",
                "short_description": "Cannot login to Salesforce",
                "description": "Raising this for a team member, John Smith. He cannot access Salesforce since this morning.",
                "caller_email": "helpdesk@acme.corp",
            }
        }

        res = self.agent.run(state)
        # Should resolve John Smith's user record from Salesforce
        self.assertEqual(res.get("affected_user", {}).get("Email"), "john.smith@acme.corp")
        self.assertEqual(res.get("affected_user", {}).get("Id"), "005xx000002LOGIN3A")
        self.assertEqual(res.get("affected_user", {}).get("resolution_source"), "description_named_entity")


    def test_extract_login_url_from_narrative(self):
        # 1. Bookmarked invalid URL
        desc1 = "User jane.doe@acme.corp is trying to log into Salesforce using bookmarked URL https://old-portal.invalid.com/login instead of production org bdx.my.salesforce.com."
        url1 = self.agent._extract_login_url(desc1)
        self.assertEqual(url1, "https://old-portal.invalid.com/login")

        # 2. Main production org
        desc2 = "User emma.watson@acme.corp reports login failure on main org bdx.my.salesforce.com."
        url2 = self.agent._extract_login_url(desc2)
        self.assertEqual(url2, "https://bdx.my.salesforce.com")

        # 3. Portal URL
        desc3 = "User cannot access portal bdx.my.site.com/BDPharmSystems/s/."
        url3 = self.agent._extract_login_url(desc3)
        self.assertEqual(url3, "https://bdx.my.site.com/BDPharmSystems/s/")

        # 4. Explicit label
        desc4 = "User issue. Login URL: https://bd2my.salesforce.com"
        url4 = self.agent._extract_login_url(desc4)
        self.assertEqual(url4, "https://bd2my.salesforce.com")

        # 5. No URL in narrative
        desc5 = "User cannot access account details."
        url5 = self.agent._extract_login_url(desc5)
        self.assertIsNone(url5)

    @patch("app.agents.triage.agent.fetch_historical_context_for_state")
    def test_triage_run_populates_extracted_url_from_description(self, mock_history):
        mock_history.return_value = []
        state: InvestigationState = {
            "incident": {
                "incident_id": "INC109",
                "short_description": "User login failure",
                "description": "User jane.doe@acme.corp is trying to log into Salesforce using bookmarked URL https://old-portal.invalid.com/login instead of production.",
                "caller_email": "jane.doe@acme.corp",
            }
        }
        res = self.agent.run(state)
        self.assertEqual(res.get("login_url"), "https://old-portal.invalid.com/login")
        self.assertEqual(res.get("triage_result", {}).get("login_url"), "https://old-portal.invalid.com/login")


    @patch("app.agents.triage.agent.fetch_historical_context_for_state")
    def test_domain_confidence_distribution_clear_ticket(self, mock_history):
        mock_history.return_value = []
        state: InvestigationState = {
            "incident": {
                "incident_id": "INC110",
                "short_description": "Single sign on error",
                "description": "User jane.doe@acme.corp cannot sign into Salesforce using Okta SAML SSO login gateway.",
                "caller_email": "jane.doe@acme.corp",
            }
        }
        res = self.agent.run(state)
        triage = res.get("triage_result", {})
        self.assertEqual(triage.get("domain"), "LOGIN")
        self.assertFalse(triage.get("is_ambiguous"))
        confidences = triage.get("domain_confidences", {})
        self.assertGreaterEqual(confidences.get("LOGIN", 0), 0.75)
        self.assertLess(confidences.get("APPLICATION", 0), 0.20)
        self.assertLess(confidences.get("OBJECT", 0), 0.20)
        self.assertLess(confidences.get("RECORD", 0), 0.20)

    @patch("app.agents.triage.agent.fetch_historical_context_for_state")
    def test_domain_confidence_distribution_ambiguous_ticket(self, mock_history):
        mock_history.return_value = []
        state: InvestigationState = {
            "incident": {
                "incident_id": "INC111",
                "short_description": "Access issue",
                "description": "User jane.doe@acme.corp cannot access salesforce at all. Please investigate.",
                "caller_email": "jane.doe@acme.corp",
            }
        }
        res = self.agent.run(state)
        triage = res.get("triage_result", {})
        self.assertEqual(triage.get("domain"), "LOGIN")
        self.assertTrue(triage.get("is_ambiguous"))
        confidences = triage.get("domain_confidences", {})
        self.assertGreaterEqual(confidences.get("LOGIN", 0), 0.40)
        self.assertGreaterEqual(confidences.get("APPLICATION", 0), 0.20)
        # Low confidence domains < 20%
        self.assertLess(confidences.get("OBJECT", 0), 0.20)
        self.assertLess(confidences.get("RECORD", 0), 0.20)


    @patch("app.agents.triage.agent.fetch_historical_context_for_state")
    def test_pir_domain_classification(self, mock_history):
        mock_history.return_value = []
        state: InvestigationState = {
            "incident": {
                "incident_id": "INC112",
                "short_description": "User Not Able to Create PIR",
                "description": "User sarah.connor@acme.corp cannot create PIR due to missing C2C training and Simplified PIR Permission Set.",
                "caller_email": "sarah.connor@acme.corp",
            }
        }
        res = self.agent.run(state)
        triage = res.get("triage_result", {})
        self.assertEqual(triage.get("domain"), "PIR")
        self.assertFalse(triage.get("is_ambiguous"))

    @patch("app.agents.triage.agent.fetch_historical_context_for_state")
    def test_outlook_plugin_domain_classification(self, mock_history):
        mock_history.return_value = []
        state: InvestigationState = {
            "incident": {
                "incident_id": "INC113",
                "short_description": "Salesforce Outlook Add-in Disabled",
                "description": "User sarah.connor@acme.corp reports Salesforce Outlook Add-in is disabled and Einstein Activity Capture is not syncing.",
                "caller_email": "sarah.connor@acme.corp",
            }
        }
        res = self.agent.run(state)
        triage = res.get("triage_result", {})
        self.assertEqual(triage.get("domain"), "OUTLOOK_PLUGIN")
        self.assertFalse(triage.get("is_ambiguous"))

    @patch("app.agents.triage.agent.fetch_historical_context_for_state")
    def test_unknown_domain_non_salesforce_scope(self, mock_history):
        mock_history.return_value = []
        state: InvestigationState = {
            "incident": {
                "incident_id": "INC114",
                "short_description": "Office supplies request",
                "description": "Printer on 3rd floor is out of paper and toner. Please replace.",
                "caller_email": "jane.doe@acme.corp",
            }
        }
        res = self.agent.run(state)
        triage = res.get("triage_result", {})
        self.assertEqual(triage.get("domain"), "UNKNOWN")
        self.assertEqual(triage.get("confidence"), 0.0)
        self.assertNotEqual(triage.get("domain"), "LOGIN")


if __name__ == "__main__":
    unittest.main()
