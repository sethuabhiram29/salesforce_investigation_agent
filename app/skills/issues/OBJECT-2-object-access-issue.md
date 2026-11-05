---
issue_code: OBJECT-2
title: Object Access Issue (Missing CRUD Permissions)
domains:
  - OBJECT
version: 1
---

# Purpose
The user is unable to create, read, edit, or delete records of a specific Salesforce object because their Profile or assigned Permission Sets lack the required Object-level permissions.

# Diagnosis

## Required Evidence
- Caller identity resolved to a Salesforce User in target Org (NA Org).
- User `IsActive` is `True`.
- Affected Salesforce Object name identified (e.g., Account, Contact, Opportunity, custom objects `*__c`).
- Effective Object Permissions query shows missing permission (`PermissionsRead`, `PermissionsCreate`, `PermissionsEdit`, or `PermissionsDelete` is `False`).

## Investigation Procedure
1. Retrieve incident description and identify the target Salesforce Object and requested action.
2. Confirm user exists and is active in NA Org.
3. Query `ObjectPermissions` for user's Profile and assigned Permission Sets:
   `SELECT SobjectType, PermissionsRead, PermissionsCreate, PermissionsEdit, PermissionsDelete FROM ObjectPermissions WHERE ParentId IN (:parentIds) AND SobjectType = :objectName`.
4. If the required permission is absent across all assigned permission sets and profile, confirm diagnosis as `OBJECT-2`.

## Permitted Diagnostic Tools
- Salesforce MCP SOQL Tool - ObjectPermissions Lookup.
- Salesforce MCP SOQL Tool - PermissionSetAssignment.
- ServiceNow REST Table API - `update_incident` (work notes).

## Confirmation Criteria
- User is active in NA Org.
- Incident mentions Object Access symptoms or error ("Insufficient Privileges" on object).
- Effective object permissions lack the requested CRUD capability.

# Resolution

## Remediation Procedure
1. Determine appropriate Permission Set granting the required object-level CRUD access.
2. If standard company permission set exists, instruct requester to submit a Manage User Access RITM for permission set assignment, routing to TCS-America-SFDC.
3. If HITL approval granted for direct permission set assignment in lower environments/POC, assign the required permission set.
4. Update incident work notes with diagnosed root cause, object name, and exact permission set requested.

## HITL Requirements
- Approval required before adding or modifying permission sets.

## Verification
- Re-query `ObjectPermissions` after assignment to verify `PermissionsRead`/`PermissionsCreate`/`PermissionsEdit` is `True`.

