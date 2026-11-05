---
issue_code: RECORD-2A
title: User Unable to Access Opportunity or Case - Missing Object-Level Access
domains:
  - RECORD
version: 2
aliases:
  - RECORD-OBJ-PERM-OPP-CASE
---

# Purpose
The user is unable to access or create Opportunity or Case records because their Profile or assigned Permission Sets lack basic Object-level Read or Create permissions for the Opportunity or Case object, as confirmed by comparing against a mirror user.

# Diagnosis

## Required Evidence
- User exists in NA Org and `User.IsActive == True`.
- Affected Object identified as Opportunity or Case.
- Mirror user identified for access baseline comparison.
- `ObjectPermissions` for Opportunity or Case lacks required access (`PermissionsRead`, `PermissionsCreate`, or `PermissionsEdit` is `False`).

## Investigation Procedure / Analysis Logic
1. Retrieve incident and caller details from ServiceNow (`get_incident`, `get_caller`).
2. Verify user exists in NA Org and is active (`salesforce_user_search`, `salesforce_get_user_details`).
3. Compare Profile and Permission Sets with mirror user (reach out to ticket owner if mirror user is not cited).
4. Review `ObjectPermissions` for Opportunity or Case.
5. Verify Read/Create/Edit/Delete permissions against mirror user.
6. Identify missing object-level access (object-level access must be validated before record sharing).
7. Request user to raise Manage User Access RITM for required permission assignment.
8. Update ServiceNow work notes with findings and next steps.

## Permitted Diagnostic Tools
- ServiceNow REST Table API - `get_incident`.
- ServiceNow REST Table API - `get_caller`.
- Salesforce MCP SOQL Tool - User Detail Lookup (`salesforce_get_user_details`).
- Salesforce MCP SOQL Tool - PermissionSetAssignment (`salesforce_get_permission_set_assignments`).
- Salesforce MCP SOQL Tool - ObjectPermissions (`salesforce_get_object_permissions`).
- ServiceNow REST Table API - `update_incident`.

## Confirmation Criteria
- User is active in NA Org.
- Object-level access for Opportunity or Case is confirmed missing.
- Disparity confirmed against mirror user baseline.

# Resolution

## Remediation Procedure
1. Document the exact missing Opportunity or Case object permissions and required Permission Set.
2. Formulate resolution instructions directing the requester to submit a **Manage User Access RITM** in the ServiceNow Service Catalog.
3. Update ServiceNow incident work notes with findings and RITM guidance.

## Permitted Operations
- Direct automated modification of ObjectPermissions without approved RITM is strictly prohibited.
- Communication Guidance (`RITMGuidance`) must be delivered to requester.

## Safety Preconditions
- User exists in NA Org.
- User `IsActive == True`.
- Object permission missing confirmed prior to reviewing record sharing.

## HITL Requirements
- Human operator authorization required to transmit Manage User Access RITM guidance to requester.

