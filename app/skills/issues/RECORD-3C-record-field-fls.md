---
issue_code: RECORD-3C
title: User Unable to Access Salesforce Record Field - Missing Field-Level Security (FLS)
domains:
  - RECORD
version: 2
aliases:
  - RECORD-4
  - RECORD-004
  - RECORD-FLS-MISSING
---

# Purpose
The user can successfully open and access the target Salesforce record, but specific fields on the record are not visible or editable because their Profile or assigned Permission Sets lack Field-Level Security (FLS) permissions, as confirmed by comparing against a mirror user.

# Diagnosis

## Required Evidence
- User exists in NA Org and `User.IsActive == True`.
- User possesses record-level access (`UserRecordAccess.HasReadAccess == True`).
- Impacted Record ID and Field API name identified.
- Working mirror user identified for baseline FLS comparison.
- `FieldPermissions` (`PermissionsRead` or `PermissionsEdit`) differs between caller and mirror user.

## Investigation Procedure / Analysis Logic
1. Retrieve incident and caller details from ServiceNow (`get_incident`, `get_caller`).
2. Verify user exists in NA Org and is active (`salesforce_get_user_details`).
3. Confirm user can access the record (`UserRecordAccess.HasReadAccess == True`) (record access exists but field visibility is restricted).
4. Identify impacted field from incident narrative or error logs.
5. Retrieve assigned Profiles and Permission Sets for target user.
6. Review `FieldPermissions` for the target field across assigned permission sets.
7. Compare access with mirror user (reach out to ticket owner if mirror user is not cited).
8. Identify missing field-level access (`PermissionsRead == False` or `PermissionsEdit == False`).
9. Request access adjustment through Manage User Access RITM.
10. Validate field visibility after access update.
11. Update ServiceNow work notes with findings and next steps.

## Permitted Diagnostic Tools
- ServiceNow REST Table API - `get_incident`.
- ServiceNow REST Table API - `get_caller`.
- Salesforce MCP SOQL Tool - PermissionSetAssignment (`salesforce_get_permission_set_assignments`).
- Salesforce MCP SOQL Tool - FieldPermissions (`salesforce_get_field_permissions`).
- ServiceNow REST Table API - `update_incident`.

## Confirmation Criteria
- User is active in NA Org.
- Record access is confirmed present (`HasReadAccess == True`).
- Target field FLS is confirmed missing when compared against mirror user.

# Resolution

## Remediation Procedure
1. Document the exact missing FieldPermissions and corresponding Permission Set or Profile difference identified during mirror user comparison.
2. Formulate resolution instructions directing the requester to submit a **Manage User Access RITM** in ServiceNow for the required field access.
3. Update ServiceNow incident work notes with findings and RITM guidance.

## Permitted Operations
- Direct automated modification of FieldPermissions without approved RITM is strictly prohibited.
- Communication Guidance (`RITMGuidance`) must be delivered to requester.

## Safety Preconditions
- User exists in NA Org.
- User `IsActive == True`.
- Record-level read access verified before field FLS remediation.

## HITL Requirements
- Human operator authorization required to transmit Manage User Access RITM guidance to requester.
