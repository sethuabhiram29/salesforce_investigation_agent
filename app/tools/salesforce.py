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

import os
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


def salesforce_get_basic_user(user_id: str) -> Dict[str, Any]:
    """Retrieve only minimal core identity fields of a Salesforce user (Id, Username, Email, Name, IsActive)."""
    full_user = salesforce_client.get_user_details(user_id)
    if not isinstance(full_user, dict) or "error" in full_user:
        return full_user
    return {
        "Id": full_user.get("Id"),
        "Username": full_user.get("Username"),
        "Email": full_user.get("Email"),
        "Name": full_user.get("Name") or f"{full_user.get('FirstName', '')} {full_user.get('LastName', '')}".strip(),
        "IsActive": full_user.get("IsActive", False),
    }


def salesforce_get_user_field(user_id: str, field_name: str) -> Any:
    """Retrieve a specific single field from a Salesforce user record on demand."""
    full_user = salesforce_client.get_user_details(user_id)
    if not isinstance(full_user, dict) or "error" in full_user:
        return None
    return full_user.get(field_name)


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

def salesforce_get_user_package_licenses(user_id: str) -> List[str]:
    """Retrieve assigned UserPackageLicenses for a user via SOQL/MCP."""
    return salesforce_client.get_user_package_licenses(user_id)


def salesforce_get_user_public_groups(user_id: str) -> List[str]:
    """Retrieve assigned Public Groups for a user via SOQL/MCP."""
    return salesforce_client.get_user_public_groups(user_id)


def salesforce_add_user_to_public_group(user_id: str, group_name: str) -> Dict[str, Any]:
    """Add a user to a Public Group (support team is authorized)."""
    return salesforce_client.add_user_to_public_group(user_id, group_name)


def salesforce_get_contact_wizard_details(user_id: str) -> Dict[str, Any]:
    """Retrieve Contact record details including WizardCountry / Wizard_Country__c field."""
    user = salesforce_client.get_user_details(user_id)
    if not isinstance(user, dict) or "error" in user:
        return user if isinstance(user, dict) else {}
    wiz_val = user.get("WizardCountry") or user.get("Wizard_Country__c")
    return {
        "user_id": user_id,
        "WizardCountry": wiz_val,
        "Wizard_Country__c": wiz_val,
        "is_configured": wiz_val is not None and str(wiz_val).strip() != "",
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


def salesforce_find_peer_mirror_user(target_user: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Discover a peer mirror user in Salesforce to benchmark internal status and federation attributes.

    When no mirror user is provided in the incident ticket narrative, this tool finds an active
    colleague in the same organization sharing similar profile or standard user licensing.
    """
    target_id = target_user.get("Id") or ""
    profile_id = target_user.get("ProfileId")

    # Priority 1: Search active peer in Salesforce with matching Profile
    if profile_id:
        soql_profile = (
            f"SELECT Id, Username, Email, FirstName, LastName, Name, IsActive, "
            f"EmployeeNumber, FederationIdentifier, UserType, Profile.Name, Profile.UserLicense.Name, ContactId, UserRoleId "
            f"FROM User WHERE IsActive = true AND Id != '{target_id}' AND ProfileId = '{profile_id}' LIMIT 1"
        )
        records = salesforce_client.execute_soql(soql_profile)
        if records:
            peer_id = records[0].get("Id")
            return salesforce_client.get_user_details(peer_id)

    # Priority 2: Search active peer with UserType = 'Standard' and non-empty FederationIdentifier
    soql_fed = (
        f"SELECT Id, Username, Email, FirstName, LastName, Name, IsActive, "
        f"EmployeeNumber, FederationIdentifier, UserType, Profile.Name, Profile.UserLicense.Name, ContactId, UserRoleId "
        f"FROM User WHERE IsActive = true AND Id != '{target_id}' AND UserType = 'Standard' "
        f"AND FederationIdentifier != null LIMIT 1"
    )
    records = salesforce_client.execute_soql(soql_fed)
    if records:
        peer_id = records[0].get("Id")
        return salesforce_client.get_user_details(peer_id)

    # Priority 3: Any active standard user in org
    soql_std = (
        f"SELECT Id, Username, Email, FirstName, LastName, Name, IsActive, "
        f"EmployeeNumber, FederationIdentifier, UserType, Profile.Name, Profile.UserLicense.Name, ContactId, UserRoleId "
        f"FROM User WHERE IsActive = true AND Id != '{target_id}' AND UserType = 'Standard' LIMIT 1"
    )
    records = salesforce_client.execute_soql(soql_std)
    if records:
        peer_id = records[0].get("Id")
        return salesforce_client.get_user_details(peer_id)

    # Priority 4: Offline / Fixture fallback (Alex Taylor)
    for u in getattr(salesforce_client, "_working_fixtures", []):
        if u.get("Id") != target_id and u.get("IsActive"):
            import copy
            return copy.deepcopy(u)

    return None


def salesforce_update_user(
    user_id: str,
    field_name: str,
    new_value: Any,
) -> Dict[str, Any]:
    """Execute an approved write operation to update a user record via MCP or authorized adapter."""
    return salesforce_client.update_user_field(user_id, field_name, new_value)

def salesforce_validate_login_url(url: str) -> Dict[str, Any]:
    """Validate any provided Salesforce login URL against approved enterprise MyDomain endpoints.

    Approved endpoints:
    - Main Org (NA): bdx.my.salesforce.com (Official Primary)
    - Main Org (Developer PoC): Active connected Developer Org from .env
      (orgfarm-9053409114-dev-ed.develop.my.salesforce.com)
    - EMEA: bd2my.salesforce.com
    - ACE/GA: bdxga.my.salesforce.com
    - ServiceMax (SMAX): bdsmx.my.salesforce.com
    """
    if not url:
        return {
            "is_provided": False,
            "is_approved": False,
            "is_main_org": False,
            "org_name": None,
            "main_url": "https://bdx.my.salesforce.com",
        }
    clean_url = str(url).strip().lower()

    # =========================================================================
    # [POC DEVELOPER ORG ENABLER - REMOVABLE FOR PRODUCTION DEPLOYMENT]
    # Recognizes the connected Salesforce Developer Edition org from .env as Main Org
    # =========================================================================
    dev_instance = os.environ.get("SALESFORCE_INSTANCE_URL") or os.environ.get("SALESFORCE_LOGIN_URL") or "https://orgfarm-9053409114-dev-ed.develop.my.salesforce.com"
    dev_domain = dev_instance.replace("https://", "").replace("http://", "").split("/")[0].strip().lower()

    mapping = {
        # Primary Enterprise NA Main Org
        "bdx.my.salesforce.com": {"org_name": "Main Org (NA)", "is_main_org": True, "domain": "bdx.my.salesforce.com", "main_url": "https://bdx.my.salesforce.com"},
        # [POC] Active connected Developer Org also recognized as Main Org alongside NA
        dev_domain: {"org_name": "Main Org (Developer PoC)", "is_main_org": True, "domain": dev_domain, "main_url": dev_instance},
        "orgfarm-9053409114-dev-ed.develop.lightning.force.com": {"org_name": "Main Org (Developer PoC)", "is_main_org": True, "domain": dev_domain, "main_url": dev_instance},
        # Secondary Regional Enterprise Orgs
        "bd2my.salesforce.com": {"org_name": "EMEA Salesforce Org", "is_main_org": False, "domain": "bd2my.salesforce.com", "main_url": "https://bdx.my.salesforce.com"},
        "bdxga.my.salesforce.com": {"org_name": "ACE/GA Salesforce Org", "is_main_org": False, "domain": "bdxga.my.salesforce.com", "main_url": "https://bdx.my.salesforce.com"},
        "bdsmx.my.salesforce.com": {"org_name": "ServiceMax (SMAX) Org", "is_main_org": False, "domain": "bdsmx.my.salesforce.com", "main_url": "https://bdx.my.salesforce.com"},
    }

    for domain_key, info in mapping.items():
        if domain_key in clean_url:
            return {
                "is_provided": True,
                "is_approved": True,
                "is_main_org": info["is_main_org"],
                "org_name": info["org_name"],
                "domain": info["domain"],
                "main_url": info.get("main_url", "https://bdx.my.salesforce.com"),
            }

    # Match standard developer edition pattern for PoC testing
    if "-dev-ed." in clean_url or "develop.my.salesforce.com" in clean_url:
        return {
            "is_provided": True,
            "is_approved": True,
            "is_main_org": True,
            "org_name": "Main Org (Developer PoC)",
            "domain": clean_url,
            "main_url": dev_instance,
        }

    return {
        "is_provided": True,
        "is_approved": False,
        "is_main_org": False,
        "org_name": None,
        "domain": clean_url,
        "main_url": "https://bdx.my.salesforce.com",
    }


def salesforce_cross_org_user_search(target_user: str) -> Optional[Dict[str, Any]]:
    """Search registered enterprise secondary organizations (EMEA, ACE/GA, ServiceMax) for target user identity."""
    return salesforce_client.search_other_orgs(target_user)


def salesforce_audit_trail_search(user_id: Optional[str] = None, action_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Query SetupAuditTrail for deactivation events, permission assignments, or administrative modifications."""
    soql = "SELECT Id, Action, CreatedById, CreatedDate, Display FROM SetupAuditTrail"
    conditions = []
    if action_filter:
        conditions.append(f"Action LIKE '%{action_filter}%'")
    if conditions:
        soql += " WHERE " + " AND ".join(conditions)
    soql += " ORDER BY CreatedDate DESC LIMIT 10"
    return salesforce_execute_soql(soql)


def salesforce_check_delegated_admin(actor_id: str) -> Dict[str, Any]:
    """Inspect DelegateGroupMember to verify if an actor holds Delegated Administrator authority."""
    soql = f"SELECT Id, UserOrGroupId FROM DelegateGroupMember WHERE UserOrGroupId = '{actor_id}'"
    results = salesforce_execute_soql(soql)
    is_da = bool(results)
    return {"actor_id": actor_id, "is_delegated_admin": is_da, "records": results}


def identity_team_engage(system: str, user_identifier: str, issue_code: str, reason: str) -> Dict[str, Any]:
    """Engage an enterprise external identity team (Azure, CIAM, Workday, MuleSoft) for identity synchronization."""
    from datetime import datetime, timezone
    return {
        "engaged": True,
        "system": system,
        "user_identifier": user_identifier,
        "issue_code": issue_code,
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "engaged_pending_sync",
    }




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
    salesforce_find_peer_mirror_user_tool = tool(salesforce_find_peer_mirror_user)
    salesforce_update_user_tool = tool(salesforce_update_user)
    salesforce_get_basic_user_tool = tool(salesforce_get_basic_user)
    salesforce_get_user_field_tool = tool(salesforce_get_user_field)
    salesforce_validate_login_url_tool = tool(salesforce_validate_login_url)
    salesforce_cross_org_user_search_tool = tool(salesforce_cross_org_user_search)
    salesforce_audit_trail_search_tool = tool(salesforce_audit_trail_search)
    salesforce_check_delegated_admin_tool = tool(salesforce_check_delegated_admin)
    identity_team_engage_tool = tool(identity_team_engage)
    salesforce_get_user_package_licenses_tool = tool(salesforce_get_user_package_licenses)
    salesforce_get_user_public_groups_tool = tool(salesforce_get_user_public_groups)
    salesforce_add_user_to_public_group_tool = tool(salesforce_add_user_to_public_group)
except ImportError:
    salesforce_user_search_tool = salesforce_user_search
    salesforce_execute_sosl_tool = salesforce_execute_sosl
    salesforce_execute_soql_tool = salesforce_execute_soql
    salesforce_get_user_details_tool = salesforce_get_user_details
    salesforce_get_basic_user_tool = salesforce_get_basic_user
    salesforce_get_user_field_tool = salesforce_get_user_field
    salesforce_get_object_permissions_tool = salesforce_get_object_permissions
    salesforce_get_record_access_tool = salesforce_get_record_access
    salesforce_get_user_permission_sets_tool = salesforce_get_user_permission_sets
    salesforce_compare_user_access_tool = salesforce_compare_user_access
    salesforce_get_contact_wizard_details_tool = salesforce_get_contact_wizard_details
    salesforce_find_peer_mirror_user_tool = salesforce_find_peer_mirror_user
    salesforce_update_user_tool = salesforce_update_user
    salesforce_validate_login_url_tool = salesforce_validate_login_url
    salesforce_cross_org_user_search_tool = salesforce_cross_org_user_search
    salesforce_audit_trail_search_tool = salesforce_audit_trail_search
    salesforce_check_delegated_admin_tool = salesforce_check_delegated_admin
    identity_team_engage_tool = identity_team_engage
    salesforce_get_user_package_licenses_tool = salesforce_get_user_package_licenses
    salesforce_get_user_public_groups_tool = salesforce_get_user_public_groups
    salesforce_add_user_to_public_group_tool = salesforce_add_user_to_public_group


def get_diagnosis_tools() -> List[Any]:
    """Return strictly READ-ONLY tools permitted during the Diagnosis stage."""
    return [
        salesforce_user_search_tool,
        salesforce_get_basic_user_tool,
        salesforce_get_user_field_tool,
        salesforce_execute_sosl_tool,
        salesforce_execute_soql_tool,
        salesforce_get_user_details_tool,
        salesforce_find_peer_mirror_user_tool,
        salesforce_get_object_permissions_tool,
        salesforce_get_record_access_tool,
        salesforce_get_user_permission_sets_tool,
        salesforce_get_user_package_licenses_tool,
        salesforce_get_user_public_groups_tool,
        salesforce_compare_user_access_tool,
        salesforce_get_contact_wizard_details_tool,
        salesforce_validate_login_url_tool,
        salesforce_cross_org_user_search_tool,
        salesforce_audit_trail_search_tool,
        salesforce_check_delegated_admin_tool,
        identity_team_engage_tool,
    ]


def get_resolution_tools() -> List[Any]:
    """Return tools permitted during the Resolution stage."""
    return [
        salesforce_get_user_details_tool,
        salesforce_update_user_tool,
        salesforce_add_user_to_public_group_tool,
    ]
