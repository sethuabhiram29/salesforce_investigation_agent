---
issue_code: RECORD-1A
title: Report or Dashboard Access Issue - User Lacks Access to Underlying Object(s)
domains:
  - RECORD
version: 2
aliases:
  - RECORD-OBJ-PERM-MISSING
  - RECORD-OBJ-PERM-REPORT
---

# Purpose
The user is unable to run, view, or refresh a Report or Dashboard because their Profile or assigned Permission Sets lack basic Object-level Read access to one or more underlying Salesforce objects queried by the report or dashboard, as confirmed by comparing against a mirror user.

# Diagnosis

## Required Evidence
- User exists in NA Org and `User.IsActive == True`.
- Impacted Report or Dashboard identified from incident description.
- Underlying Salesforce objects used by the report/dashboard identified.
- Mirror user identified for access baseline comparison.
- `ObjectPermissions` for underlying report objects differ from mirror user (`PermissionsRead == False`).

## Investigation Procedure / Analysis Logic
1. Retrieve incident and caller details from ServiceNow (`get_incident`, `get_caller`).
2. Verify user exists in NA Org and is active (`salesforce_user_search`, `salesforce_get_user_details`).
3. Identify impacted Report/Dashboard and underlying Salesforce objects.
4. Obtain mirror user details (reach out to ticket owner if mirror user is not cited).
5. Compare User Profile assignments between caller and mirror user.
6. Compare assigned Permission Sets (`salesforce_get_permission_set_assignments`).
7. Review `ObjectPermissions` for all report-related objects.
8. Identify missing object-level access (`PermissionsRead`).
9. Document findings in incident investigation logs.
10. Request user to raise Manage User RITM for required Profile/Permission Set assignment.
11. Update ServiceNow work notes with findings and next steps.

## Permitted Diagnostic Tools
- ServiceNow REST Table API - `get_incident`.
- ServiceNow REST Table API - `get_caller`.
- Salesforce MCP SOSL Search Tool.
- Salesforce MCP SOQL Tool - User Detail Lookup (`salesforce_get_user_details`).
- Salesforce MCP SOQL Tool - PermissionSetAssignment (`salesforce_get_permission_set_assignments`).
- Salesforce MCP SOQL Tool - ObjectPermissions (`salesforce_get_object_permissions`).
- ServiceNow REST Table API - `update_incident`.

## Confirmation Criteria
- User is active in NA Org.
- Report/Dashboard cited in incident.
- Underlying object access is validated before reviewing folder sharing.
- Object permissions differ from mirror user.

# Resolution

## Remediation Procedure
1. Document the exact missing underlying object permissions and required Permission Set.
2. Formulate resolution instructions directing the requester to submit a **Manage User Access RITM** in ServiceNow for the required Profile or Permission Set assignment.
3. Update ServiceNow incident work notes with findings and RITM guidance.

## Permitted Operations
- Direct automated grant of ObjectPermissions without approved RITM is prohibited.
- Communication Guidance (`RITMGuidance`) must be delivered to requester.

## Safety Preconditions
- User exists in NA Org.
- User `IsActive == True`.
- Missing object-level access confirmed prior to reviewing folder sharing.

## HITL Requirements
- Human operator authorization required to transmit Manage User RITM guidance to requester.

