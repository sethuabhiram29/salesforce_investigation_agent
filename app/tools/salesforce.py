"""Salesforce investigation and remediation tools.

Connects to Salesforce via SalesforceMCPClient (Model Context Protocol),
supporting live MCP server tool execution (SOSL, SOQL, user searches, record inspection)
with automatic fixture fallback for PoC testing.

Tools:
- salesforce_user_search: Search users by username or email via SOSL/MCP
- salesforce_execute_sosl: Execute custom SOSL search queries via MCP
- salesforce_execute_soql: Execute custom SOQL queries via MCP
- salesforce_get_user_details: Retrieve full user record via MCP
- salesforce_get_object_permissions: Check object permissions via SOQL/MCP
- salesforce_get_record_access: Check UserRecordAccess for a specific record via SOQL/MCP
- salesforce_get_user_permission_sets: Retrieve assigned permission sets via SOQL/MCP
- salesforce_compare_user_access: Compare affected user against mirror user
- salesforce_get_contact_wizard_details: Retrieve WizardCountry and contact config
- salesforce_update_user: Execute approved user record update (resolution only)
"""

from typing import Any, Dict, List, Optional

from app.integrations.salesforce.client import salesforce_client


def reset_fixture_state():
    """Reset fixture users to initial state (useful in test teardown)."""
    salesforce_client.reset_fixtures()


def salesforce_user_search(query: str) -> List[Dict[str, Any]]:
    """Search for Salesforce users by exact or partial username or email via SOSL/MCP."""
    return salesforce_client.search_users(query)


def salesforce_execute_sosl(query: str) -> List[Dict[str, Any]]:
    """Execute a raw SOSL search query in Salesforce via MCP.

    Example:
        FIND {jane.doe} IN ALL FIELDS RETURNING User(Id, Username, Email, IsActive)
    """
    return salesforce_client.execute_sosl(query)


def salesforce_execute_soql(query: str) -> List[Dict[str, Any]]:
    """Execute a raw SOQL query in Salesforce via MCP.

    Example:
        SELECT Id, Username, Email, IsActive, FederationIdentifier FROM User WHERE Email = 'jane.doe@acme.corp'
    """
    return salesforce_client.execute_soql(query)


def salesforce_get_user_details(user_id: str) -> Dict[str, Any]:
    """Retrieve full details of a specific Salesforce user record by Id via MCP."""
    return salesforce_client.get_user_details(user_id)


def salesforce_get_object_permissions(user_id: str, object_name: str) -> Dict[str, Any]:
    """Check object CRUD permissions for a given user and Salesforce object via SOQL/MCP."""
    return salesforce_client.get_object_permissions(user_id, object_name)


def salesforce_get_record_access(user_id: str, record_id: str) -> Dict[str, Any]:
    """Check record-level access (UserRecordAccess) for a specific record via SOQL/MCP."""
    return salesforce_client.get_record_access(user_id, record_id)


def salesforce_get_user_permission_sets(user_id: str) -> List[str]:
    """Retrieve assigned Permission Sets for a user via SOQL/MCP."""
    return salesforce_client.get_user_permission_sets(user_id)


def salesforce_get_contact_wizard_details(user_id: str) -> Dict[str, Any]:
    """Retrieve Contact record details including WizardCountry field."""
    user = salesforce_client.get_user_details(user_id)
    if "error" in user:
        return user
    return {
        "user_id": user_id,
        "WizardCountry": user.get("WizardCountry"),
        "is_configured": user.get("WizardCountry") is not None,
    }


def salesforce_compare_user_access(
    user_id: str,
    mirror_user_id: str,
    object_name: Optional[str] = None
) -> Dict[str, Any]:
    """Compare access rights between the affected user and a working mirror user.

    Identifies differences in Profiles, Permission Sets, and Object Permissions.
    """
    user = salesforce_client.get_user_details(user_id)
    mirror = salesforce_client.get_user_details(mirror_user_id)

    if "error" in user:
        return {"error": f"Affected user error: {user['error']}"}
    if "error" in mirror:
        return {"error": f"Mirror user error: {mirror['error']}"}

    user_ps = set(user.get("PermissionSets", []))
    mirror_ps = set(mirror.get("PermissionSets", []))
    missing_ps = list(mirror_ps - user_ps)

    profile_match = user.get("Profile", {}).get("Name") == mirror.get("Profile", {}).get("Name")

    diff: Dict[str, Any] = {
        "affected_user": user.get("Email"),
        "mirror_user": mirror.get("Email"),
        "affected_profile": user.get("Profile", {}).get("Name"),
        "mirror_profile": mirror.get("Profile", {}).get("Name"),
        "profile_match": profile_match,
        "missing_permission_sets": missing_ps,
    }

    if object_name:
        user_obj = salesforce_client.get_object_permissions(user_id, object_name)
        mirror_obj = salesforce_client.get_object_permissions(mirror_user_id, object_name)
        diff["object_name"] = object_name
        diff["affected_object_permissions"] = user_obj
        diff["mirror_object_permissions"] = mirror_obj
        diff["object_permissions_match"] = user_obj == mirror_obj

    return diff


def salesforce_update_user(
    user_id: str,
    field_name: str,
    new_value: Any,
) -> Dict[str, Any]:
    """Execute an approved write operation to update a user record via MCP or authorized adapter."""
    return salesforce_client.update_user_field(user_id, field_name, new_value)


try:
    from langchain_core.tools import tool
    salesforce_user_search_tool = tool(salesforce_user_search)
    salesforce_execute_sosl_tool = tool(salesforce_execute_sosl)
    salesforce_execute_soql_tool = tool(salesforce_execute_soql)
    salesforce_get_user_details_tool = tool(salesforce_get_user_details)
    salesforce_get_object_permissions_tool = tool(salesforce_get_object_permissions)
    salesforce_get_record_access_tool = tool(salesforce_get_record_access)
    salesforce_get_user_permission_sets_tool = tool(salesforce_get_user_permission_sets)
    salesforce_compare_user_access_tool = tool(salesforce_compare_user_access)
    salesforce_get_contact_wizard_details_tool = tool(salesforce_get_contact_wizard_details)
    salesforce_update_user_tool = tool(salesforce_update_user)
except ImportError:
    salesforce_user_search_tool = salesforce_user_search
    salesforce_execute_sosl_tool = salesforce_execute_sosl
    salesforce_execute_soql_tool = salesforce_execute_soql
    salesforce_get_user_details_tool = salesforce_get_user_details
    salesforce_get_object_permissions_tool = salesforce_get_object_permissions
    salesforce_get_record_access_tool = salesforce_get_record_access
    salesforce_get_user_permission_sets_tool = salesforce_get_user_permission_sets
    salesforce_compare_user_access_tool = salesforce_compare_user_access
    salesforce_get_contact_wizard_details_tool = salesforce_get_contact_wizard_details
    salesforce_update_user_tool = salesforce_update_user


def get_diagnosis_tools() -> List[Any]:
    """Return strictly READ-ONLY tools permitted during the Diagnosis stage."""
    return [
        salesforce_user_search_tool,
        salesforce_execute_sosl_tool,
        salesforce_execute_soql_tool,
        salesforce_get_user_details_tool,
        salesforce_get_object_permissions_tool,
        salesforce_get_record_access_tool,
        salesforce_get_user_permission_sets_tool,
        salesforce_compare_user_access_tool,
        salesforce_get_contact_wizard_details_tool,
    ]


def get_resolution_tools() -> List[Any]:
    """Return tools permitted during the Resolution stage."""
    return [
        salesforce_get_user_details_tool,
        salesforce_update_user_tool,
    ]
