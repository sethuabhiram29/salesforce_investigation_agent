---
issue_code: OBJECT-2A
title: User Cannot Edit or Delete Records of a Specific Object - Missing Object-Level Permission
domains:
  - OBJECT
version: 2
aliases:
  - OBJECT-2
  - OBJECT-002
  - OBJECT-ACCESS-MISSING
---

# Purpose
The user is unable to create, read, edit, or delete records of a specific Salesforce object because their Profile or assigned Permission Sets lack the required Object-level permissions (CRUD), as confirmed by comparison against a working mirror user.

# Diagnosis

## Required Evidence
- User exists in NA Org and `User.IsActive == True`.
- Impacted Salesforce Object identified from incident description or error message.
- Working mirror user identified from same role, profile, business unit, or department.
- Object permissions (`PermissionsRead`, `PermissionsCreate`, `PermissionsEdit`, `PermissionsDelete`) differ between affected user and mirror user.

## Investigation Procedure / Analysis Logic
1. Retrieve incident and caller details from ServiceNow (`get_incident`, `get_caller`).
2. Execute Salesforce SOSL search in NA Org (`salesforce_user_search`).
3. If user is not found in NA Org, follow Login-1A/Login-1B process.
4. Verify `User.IsActive` status.
5. Obtain mirror user details (reach out to ticket owner if mirror user is not cited).
6. Compare User Profile assignments between affected user and mirror user.
7. Compare assigned Permission Sets (`salesforce_get_permission_set_assignments`).
8. Compare Object Permissions (`PermissionsRead`, `PermissionsCreate`, `PermissionsEdit`, `PermissionsDelete`) between affected user and mirror user for the affected object.
9. Identify missing object-level access.
10. Document findings in incident investigation logs.
11. Request user to raise Manage User RITM for required permission assignment.
12. Update ServiceNow work notes with findings and next steps.

## Permitted Diagnostic Tools
- ServiceNow REST Table API - `get_incident`.
- ServiceNow REST Table API - `get_caller`.
- Salesforce MCP SOSL Search Tool.
- Salesforce MCP SOQL Tool - User Detail Lookup (`salesforce_get_user_details`).
- Salesforce MCP SOQL Tool - PermissionSetAssignment (`salesforce_get_permission_set_assignments`).
- Salesforce MCP SOQL Tool - PermissionSet (`salesforce_query`).
- Salesforce MCP SOQL Tool - ObjectPermissions (`salesforce_get_object_permissions`).
- ServiceNow REST Table API - `update_incident`.

## Confirmation Criteria
- `User.IsActive == True` in NA Org.
- Object permissions differ from mirror user on the target object.
- Missing CRUD permission confirmed via `ObjectPermissions`.

# Resolution

## Remediation Procedure
1. Document the exact missing Object permissions and corresponding Permission Set or Profile difference identified during mirror user comparison.
2. Formulate resolution instructions directing the requester to submit a **Manage User Access RITM** in the ServiceNow Service Catalog for the required Permission Set assignment.
3. Update ServiceNow incident work notes with findings and RITM guidance.
4. Direct ticket to user for RITM creation.

## Permitted Operations
- Direct automated modification of ObjectPermissions or Profile in production without approved RITM is strictly prohibited.
- Communication Guidance (`RITMGuidance`) must be provided to the requester.

## Safety Preconditions
- User exists in NA Org.
- User `IsActive == True`.
- Missing object permission confirmed against mirror user baseline.

## HITL Requirements
- Human operator authorization required to transmit Manage User RITM guidance to requester.

