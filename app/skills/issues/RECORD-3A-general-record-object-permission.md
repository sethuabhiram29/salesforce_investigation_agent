---
issue_code: RECORD-3A
title: User Unable to Access Salesforce Record - Missing Object Permission
domains:
  - RECORD
version: 2
aliases:
  - RECORD-OBJ-PERM-RECORD
---

# Purpose
The user is unable to open or access a specific Salesforce record because their Profile or assigned Permission Sets lack basic Object-level Read permission for the record's underlying SObject type, as confirmed by comparing against a mirror user.

# Diagnosis

## Required Evidence
- User exists in NA Org and `User.IsActive == True`.
- Affected Record ID and SObject type identified.
- Working mirror user identified for baseline access comparison.
- `ObjectPermissions` for the SObject type lacks required Read permission.

## Investigation Procedure / Analysis Logic
1. Retrieve incident and caller details from ServiceNow (`get_incident`, `get_caller`).
2. Verify user exists in NA Org and is active (`salesforce_user_search`, `salesforce_get_user_details`).
3. Collect affected Record ID and determine SObject type.
4. Review `ObjectPermissions` for user's Profile and Permission Sets (object access must be validated before record-sharing review).
5. Compare access with mirror user.
6. Identify missing object-level access (`PermissionsRead == False`).
7. Request required access assignment through Manage User Access RITM.
8. Validate access after assignment.

## Permitted Diagnostic Tools
- ServiceNow REST Table API - `get_incident`.
- ServiceNow REST Table API - `get_caller`.
- Salesforce MCP SOQL Tool - UserRecordAccess (`salesforce_get_record_access`).
- Salesforce MCP SOQL Tool - ObjectPermissions (`salesforce_get_object_permissions`).
- Salesforce MCP SOQL Tool - PermissionSetAssignment (`salesforce_get_permission_set_assignments`).
- ServiceNow REST Table API - `update_incident`.

## Confirmation Criteria
- User is active in NA Org.
- Object-level Read permission is confirmed missing.
- Disparity confirmed against mirror user baseline.

# Resolution

## Remediation Procedure
1. Document the exact missing Object permissions and required Permission Set for the SObject type.
2. Formulate resolution instructions directing the requester to submit a **Manage User Access RITM** in ServiceNow.
3. Update ServiceNow incident work notes with findings and RITM guidance.

## Permitted Operations
- Direct automated modification of ObjectPermissions without approved RITM is strictly prohibited.
- Communication Guidance (`RITMGuidance`) must be delivered to requester.

## Safety Preconditions
- User exists in NA Org.
- User `IsActive == True`.
- Missing object-level access verified before record sharing review.

## HITL Requirements
- Human operator authorization required to transmit Manage User Access RITM guidance to requester.
