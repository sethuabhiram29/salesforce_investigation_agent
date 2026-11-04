---
issue_code: APP-CC360-PS-MISSING
title: CC360 Community User Permission Set Not Assigned
domains:
  - APPLICATION
version: 1
user_type: "External / Portal (check User.IsPortalEnabled == True)"
permission_set_label: "CC360 Community User"
portal_admin: "Heather McKelvey (Heather.Mckelvey@bd.com)"
assignment_group: "TCS-America-SFDC"
portal_url: "https://bdx.my.site.com/cc360/"
condition: "User exists in NA Org AND IsActive = True AND CC360 Community User Permission Set Not Assigned"
---

# Purpose
An active user cannot access or view features of the Customer 360 (CC360) application because the required **"CC360 Community User"** Permission Set is not assigned to their Salesforce user record.

# Key Architecture & Domain Guidelines
- **User Type Differentiation**: Use the `IsPortalEnabled` field on the User record to differentiate between internal users and external portal users.
- **Application Portal URL**: `https://bdx.my.site.com/cc360/`
- **Permission Set Name/Label**: `CC360 Community User`
- **Portal Admin**: Heather McKelvey (`Heather.Mckelvey@bd.com`)
- **Designated Assignment Group**: `TCS-America-SFDC`
- **Request Mechanism**: Caller must create a **Manage User Access RITM** to assign this permission set.

# Safety Rules & Preconditions
> [!IMPORTANT]
> - User must exist in the primary NA Organization and be verified as active (`IsActive == True`) before CC360 access validation is performed.
> - Any login or account deactivation issues must be resolved first through the Login investigation process.

# Diagnosis

## Required Evidence
1. User uniquely identified and exists in NA Org.
2. `User.IsActive == True`.
3. Ticket narrative reports CC360 access failure.
4. SOQL query on `PermissionSetAssignment` confirms `CC360 Community User` is not in the user's assigned permission sets.
5. User `IsPortalEnabled` status inspected.

## Investigation Procedure
1. Retrieve incident and caller details from ServiceNow (`servicenow_get_incident`, `servicenow_get_caller`).
2. Extract Email ID, Federation ID, Username, Employee ID, or Full Name.
3. Execute Salesforce SOSL search in NA Org using available identifiers (`salesforce_user_search`).
4. If user not found in NA, follow Login-1A/Login-1B process.
5. Retrieve Salesforce User details and verify account is active (`User.IsActive == True`).
6. If user is inactive, follow Login-3 investigation process.
7. Retrieve assigned Permission Sets using `PermissionSetAssignment` (`salesforce_get_user_permission_sets`).
8. Verify whether the `CC360 Community User` Permission Set is assigned.
9. If `CC360 Community User` is not assigned, classify as CC360 App Access Issue (`APP-CC360-PS-MISSING`).
10. Instruct requester to create a **Manage User Access RITM** for assignment of `CC360 Community User` and route to `TCS-America-SFDC`.
11. Update incident work notes with findings and required action (`servicenow_add_work_notes`).

## Permitted Diagnostic Tools
- `servicenow_get_incident`
- `servicenow_get_caller`
- `salesforce_user_search`
- `salesforce_get_user_details`
- `salesforce_get_user_permission_sets`
- `servicenow_add_work_notes`

## Confirmation Criteria
Confirmed only when:
- User is uniquely resolved in NA Org and `User.IsActive == True`.
- Incident concerns Customer 360 (CC360) access.
- `CC360 Community User` Permission Set is absent from user's `PermissionSetAssignment`.

# Resolution

## Remediation Procedure
1. Verify whether the **"CC360 Community User"** Permission Set is assigned.
2. If the Permission Set is not assigned:
   - Instruct the user/requestor to create a **Manage User Access RITM**.
   - Route the request to assignment group: **TCS-America-SFDC**.
   - Provide Portal Admin contact: **Heather McKelvey (Heather.Mckelvey@bd.com)**.
   - Provide CC360 portal URL: `https://bdx.my.site.com/cc360/`.
3. Update ServiceNow incident work notes with complete findings, RITM guidance, assignment group, and portal admin details.
