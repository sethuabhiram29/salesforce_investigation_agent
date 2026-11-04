---
issue_code: APP-CRM-CONTENT-DISABLED
title: Salesforce CRM Content User Checkbox Not Enabled
domains:
  - APPLICATION
version: 1
user_type: Internal
target_field: "User.UserPermissionsSFContentUser"
condition: "User exists in NA Org AND IsActive = True AND UserPermissionsSFContentUser = False"
requires_business_approval: true
support_team_direct_update_permitted: false
---

# Purpose
An active user attempting to use Conga CLM cannot access contract workspace documents or Content Version attachments because the **UserPermissionsSFContentUser** (Salesforce CRM Content User) feature checkbox is disabled (`False`) on their User record.

# Key Architecture & Domain Guidelines
- **Target Field**: `User.UserPermissionsSFContentUser`
- **Crucial Policy & Governance Boundary**:
  > [!WARNING]
  > **The support team CANNOT perform direct updates on user records in production without prior business approval and a valid Ticket/RITM.**
- **Access Management Process**: Must be routed through the approved access management process requiring business approval and valid RITM.

# Safety Rules & Preconditions
> [!IMPORTANT]
> - User must exist in NA Org and be active before Conga access validation is performed.
> - Direct write execution to enable `UserPermissionsSFContentUser` without pre-verified business approval and valid RITM is strictly prohibited.

# Diagnosis

## Required Evidence
1. User exists in NA Org and `User.IsActive == True`.
2. Incident narrative indicates Conga CLM document or Content Library access issues.
3. Query of User record confirms `UserPermissionsSFContentUser == False`.

## Investigation Procedure
1. Retrieve incident and caller details from ServiceNow.
2. Extract user identifiers and execute Salesforce SOSL search in NA Org.
3. If user not found in NA, follow Login-1A/Login-1B process.
4. Verify `User.IsActive`. If inactive, follow Login-3 investigation process.
5. Verify `UserPermissionsSFContentUser` on User record.
6. If `UserPermissionsSFContentUser = False`, verify existence of business approval and valid Ticket/RITM before proceeding with any user record update.
7. If approval is unavailable, classify root cause as `APP-CRM-CONTENT-DISABLED`.
8. Validate Conga application access.
9. Update incident work notes with findings and actions performed.

## Permitted Diagnostic Tools
- `servicenow_get_incident`
- `servicenow_get_caller`
- `salesforce_user_search`
- `salesforce_get_user_details`
- `servicenow_add_work_notes`

## Confirmation Criteria
Confirmed only when:
- User is active in NA Org.
- `UserPermissionsSFContentUser` is `False`.
- Business approval or approved RITM is not yet attached to the incident.

# Resolution

## Remediation Procedure
1. Verify whether `UserPermissionsSFContentUser` is enabled.
2. If `UserPermissionsSFContentUser = False`:
   - Inform requester that Salesforce CRM Content User access requires business approval and a valid Ticket/RITM.
   - Do **NOT** perform direct updates without approval.
   - Route request through the approved access management process.
3. Update ServiceNow work notes with findings and actions taken.
