"""Tests for Salesforce investigation tools."""

import unittest

from app.tools.salesforce import (
    salesforce_user_search,
    salesforce_get_user_details,
    salesforce_get_object_permissions,
    salesforce_update_user,
    get_diagnosis_tools,
    get_resolution_tools,
    reset_fixture_state,
)


class TestSalesforceTools(unittest.TestCase):
    def setUp(self):
        reset_fixture_state()

    def tearDown(self):
        reset_fixture_state()

    def test_user_search_exact_and_partial(self):
        # Exact match
        results = salesforce_user_search("jane.doe@acme.corp")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["Username"], "jane.doe@acme.corp")
        self.assertEqual(results[0]["Id"], "005xx000001LOGIN4")

        # Partial match
        partial = salesforce_user_search("acme.corp")
        self.assertGreaterEqual(len(partial), 3)

        # Non-existent
        none = salesforce_user_search("nonexistent@acme.corp")
        self.assertEqual(len(none), 0)

    def test_get_user_details(self):
        # LOGIN-4 user has null FederationIdentifier
        user = salesforce_get_user_details("005xx000001LOGIN4")
        self.assertNotIn("error", user)
        self.assertIsNone(user["FederationIdentifier"])
        self.assertTrue(user["IsActive"])

        # LOGIN-3A user is deactivated
        deact_user = salesforce_get_user_details("005xx000002LOGIN3A")
        self.assertFalse(deact_user["IsActive"])
        self.assertTrue(deact_user["DelegatedAdmin"])

    def test_get_object_permissions(self):
        perms = salesforce_get_object_permissions("005xx000003OBJECT1", "Account")
        self.assertTrue(perms["PermissionsRead"])
        self.assertFalse(perms["PermissionsEdit"])

    def test_update_user_field_whitelist(self):
        # FederationIdentifier is permitted
        res = salesforce_update_user("005xx000001LOGIN4", "FederationIdentifier", "jane.doe@acme.corp")
        self.assertTrue(res["success"])
        self.assertEqual(res["new_value"], "jane.doe@acme.corp")

        # Verify updated in state
        updated = salesforce_get_user_details("005xx000001LOGIN4")
        self.assertEqual(updated["FederationIdentifier"], "jane.doe@acme.corp")

        # Unauthorized field is blocked by safety boundary
        bad_res = salesforce_update_user("005xx000001LOGIN4", "ProfileId", "00exxHACK")
        self.assertFalse(bad_res["success"])
        self.assertIn("permitted write whitelist", bad_res["error"])

    def test_tool_scoping_boundaries(self):
        diag_tools = get_diagnosis_tools()
        diag_tool_names = [t.name if hasattr(t, "name") else t.__name__ for t in diag_tools]

        # Diagnosis must NEVER contain write tool
        self.assertNotIn("salesforce_update_user", diag_tool_names)
        self.assertIn("salesforce_user_search", diag_tool_names)
        self.assertIn("salesforce_get_user_details", diag_tool_names)

        # Resolution tools contain update tool
        res_tools = get_resolution_tools()
        res_tool_names = [t.name if hasattr(t, "name") else t.__name__ for t in res_tools]
    def test_sosl_and_soql_execution(self):
        from app.tools.salesforce import salesforce_execute_sosl, salesforce_execute_soql

        # SOSL search
        sosl_results = salesforce_execute_sosl("FIND {jane.doe} IN ALL FIELDS")
        self.assertGreaterEqual(len(sosl_results), 1)
        self.assertEqual(sosl_results[0]["Email"], "jane.doe@acme.corp")

        # SOQL query
        soql_results = salesforce_execute_soql("SELECT Id FROM User WHERE Email = 'sarah.connor@acme.corp'")
        self.assertGreaterEqual(len(soql_results), 1)
        self.assertEqual(soql_results[0]["Username"], "sarah.connor@acme.corp")

    def test_record_access_and_comparison(self):
        from app.tools.salesforce import (
            salesforce_get_record_access,
            salesforce_compare_user_access,
            salesforce_get_user_permission_sets,
        )

        # Check Sarah Connor record access on Opportunity
        access = salesforce_get_record_access("005xx000003OBJECT1", "006xx000001OPP")
        self.assertFalse(access.get("HasReadAccess"))

        # Check permission sets for Alex Taylor
        alex_ps = salesforce_get_user_permission_sets("005xx000004HEALTHY")
        self.assertIn("CC360 Community User", alex_ps)

        # Compare Sarah Connor against mirror Alex Taylor
        diff = salesforce_compare_user_access("005xx000003OBJECT1", "005xx000004HEALTHY", object_name="Account")
        self.assertIn("missing_permission_sets", diff)
        self.assertFalse(diff["object_permissions_match"])


if __name__ == "__main__":
    unittest.main()
