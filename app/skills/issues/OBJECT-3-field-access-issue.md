---
issue_code: OBJECT-3
title: Field Access Issue (Missing Field-Level Security)
domains:
  - OBJECT
version: 1
---

# Purpose
The user can access an object record, but specific fields are hidden or read-only because their Profile or Permission Sets do not grant Field-Level Security (FLS) permissions (`PermissionsRead` or `PermissionsEdit` on `FieldPermissions`).

# Diagnosis

## Required Evidence
- Caller identity resolved to a Salesforce User in target Org (NA Org).
- User `IsActive` is `True`.
- Specific Field name and SObject identified (e.g., `Account.Custom_Field__c`).
- `FieldPermissions` query confirms `PermissionsRead` or `PermissionsEdit` is `False` for the user.

## Investigation Procedure
1. Retrieve incident description and identify affected object and field names.
2. Confirm user is active in NA Org.
3. Query `FieldPermissions`:
   `SELECT SobjectType, Field, PermissionsRead, PermissionsEdit FROM FieldPermissions WHERE ParentId IN (:parentIds) AND SobjectType = :objectName AND Field = :fieldName`.
4. If field permissions are missing for the required action (read or edit), confirm diagnosis as `OBJECT-3`.

## Permitted Diagnostic Tools
- Salesforce MCP SOQL Tool - FieldPermissions Lookup.
- Salesforce MCP SOQL Tool - PermissionSetAssignment.
- ServiceNow REST Table API - `update_incident` (work notes).

## Confirmation Criteria
- User is active in NA Org.
- Incident mentions field not visible or cannot edit field.
- FLS query confirms user lacks read or edit access on the field.

# Resolution

## Remediation Procedure
1. Identify Permission Set or Profile adjustment providing the required FLS.
2. Instruct requester to create a Manage User Access RITM for FLS permission set assignment, or request admin profile adjustment via TCS-America-SFDC.
3. Update incident work notes with diagnosed field name, parent object, and remediation recommendation.

## HITL Requirements
- Human approval required before modifying FLS or assigning new permission sets.

## Verification
- Re-query `FieldPermissions` to verify field visibility and editability.

