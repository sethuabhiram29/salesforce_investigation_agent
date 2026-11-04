---
issue_code: APP-CC360-PS-MISSING
title: CC360 Permission Set Missing in Salesforce User Record
domains:
  - APPLICATION
version: 1
user_type: Any
condition: "User exists AND IsActive = True AND Issue relates to CC360 AND CC360 Permission Set NOT Assigned"
---

# Purpose
An active Salesforce user cannot access or view features of Customer 360 (CC360 / Cloud Customer 360) because the required CC360 Permission Set (`CloudCustomer360` / `CC360_User`) has not been assigned to their user account.

# Diagnosis

## Required Evidence
- User exists in Salesforce organization.
- `User.IsActive == True`.
- Incident classified as CC360 application issue.
- Querying `PermissionSetAssignment` reveals that CC360 Permission Set is missing from user's assigned permission sets.

## Investigation Procedure
1. Retrieve incident and caller details.
2. Ingest triage result and verify user active status (`IsActive == True`).
3. Query assigned permission sets for the user via SOQL/MCP (`salesforce_get_user_permission_sets`).
4. Classify issue type from ticket description keywords (CC360 / Customer 360).
5. Check if CC360 Permission Set is assigned.
6. If not assigned, confirm root cause as `APP-CC360-PS-MISSING`.
7. Formulate resolution plan to assign the required CC360 permission set.

## Confirmation Criteria
Confirmed only when:
- User is active in Salesforce.
- Issue relates to Customer 360 application.
- CC360 Permission Set is confirmed absent from user's `PermissionSetAssignment`.

# Resolution

## Remediation Procedure
1. Formulate remediation proposal to assign `CloudCustomer360` permission set to the user.
2. Submit proposal to human operator approval gate (HITL).
3. Upon approval, execute assignment via Salesforce API/MCP.
4. Verify assignment in `PermissionSetAssignment`.
5. Update ServiceNow work notes and notify user.
