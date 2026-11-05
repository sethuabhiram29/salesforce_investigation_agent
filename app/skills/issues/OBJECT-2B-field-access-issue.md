---
issue_code: OBJECT-2B
title: User Does Not Have Access to a Particular Field - Missing Field Level Security (FLS)
domains:
  - OBJECT
version: 2
aliases:
  - OBJECT-3
  - OBJECT-003
  - OBJECT-FLS-MISSING
---

# Purpose
The user can access the target Salesforce record or object, but cannot view or edit a specific field because their Profile or assigned Permission Sets lack Field-Level Security (FLS) permissions, as confirmed by comparison against a working mirror user.

# Diagnosis

## Required Evidence
- User exists in NA Org and `User.IsActive == True`.
- Impacted Object and Field API name identified (e.g. `Opportunity.Discount_Rate__c`).
- Working mirror user identified for baseline FLS comparison.
- `FieldPermissions` (`PermissionsRead` or `PermissionsEdit`) differs between affected user and mirror user.

## Investigation Procedure / Analysis Logic
1. Retrieve incident and caller details from ServiceNow (`get_incident`, `get_caller`).
2. Execute Salesforce SOSL search in NA Org (`salesforce_user_search`).
3. If user is not found in NA Org, follow Login-1A/Login-1B process.
4. Verify `User.IsActive` status.
5. Obtain mirror user details (reach out to ticket owner if mirror user is not cited).
6. Compare User Profiles between affected user and mirror user.
7. Compare assigned Permission Sets (`salesforce_get_permission_set_assignments`).
8. Review Field-Level Security (FLS) for the impacted field.
9. Compare field permissions (`PermissionsRead`, `PermissionsEdit`) between affected user and mirror user.
10. Identify missing field access.
11. Document findings in incident investigation logs.
12. Request user to raise Manage User RITM for required field access.
13. Update ServiceNow work notes with findings and next steps.

## Permitted Diagnostic Tools
- ServiceNow REST Table API - `get_incident`.
- ServiceNow REST Table API - `get_caller`.
- Salesforce MCP SOSL Search Tool.
- Salesforce MCP SOQL Tool - User Detail Lookup (`salesforce_get_user_details`).
- Salesforce MCP SOQL Tool - PermissionSetAssignment (`salesforce_get_permission_set_assignments`).
- Salesforce MCP SOQL Tool - PermissionSet (`salesforce_query`).
- Salesforce MCP SOQL Tool - FieldPermissions (`salesforce_get_field_permissions`).
- ServiceNow REST Table API - `update_incident`.

## Confirmation Criteria
- `User.IsActive == True` in NA Org.
- Target field visibility or edit permission differs from mirror user.
- Missing FLS confirmed via `FieldPermissions`.

# Resolution

## Remediation Procedure
1. Document the exact missing FieldPermissions and corresponding Permission Set or Profile difference.
2. Formulate resolution instructions directing the requester to submit a **Manage User Access RITM** in ServiceNow for the required Permission Set assignment.
3. Update ServiceNow incident work notes with findings and RITM guidance.

## Permitted Operations
- Direct automated mutation of FieldPermissions without approved RITM is strictly prohibited.
- Communication Guidance (`RITMGuidance`) must be delivered to requester.

## Safety Preconditions
- User exists in NA Org.
- User `IsActive == True`.
- Missing FLS confirmed against mirror user baseline.

## HITL Requirements
- Human operator authorization required to transmit Manage User RITM guidance to requester.

