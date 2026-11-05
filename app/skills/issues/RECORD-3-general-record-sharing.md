---
issue_code: RECORD-3
title: Missing Salesforce Record Sharing
domains:
  - RECORD
version: 1
---

# Purpose
The user has object-level permissions to a standard or custom object, but cannot access a specific record because row-level sharing is missing (OWD is Private, user is not record owner, not above in role hierarchy, and no sharing rule or manual share exists).

# Diagnosis

## Required Evidence
- Caller identity resolved to a Salesforce User in target Org (NA Org).
- User `IsActive` is `True`.
- Affected Record ID identified.
- User possesses Object Read permission for the object type.
- `UserRecordAccess.HasReadAccess` is `False`.
- Comprehensive sharing audit (Owner, OWD, Role Hierarchy, Sharing Rules, Public Groups, Manual Sharing) confirms no grant path.

## Investigation Procedure
1. Identify affected Record ID and SObject type.
2. Confirm user has Object-level Read permission.
3. Query `UserRecordAccess` for `(UserId, RecordId)`.
4. If `HasReadAccess == False`, inspect `*__Share` or standard share table.
5. If no valid sharing path exists, confirm diagnosis as `RECORD-3`.

## Permitted Diagnostic Tools
- Salesforce MCP SOQL Tool - UserRecordAccess Lookup.
- Salesforce MCP SOQL Tool - Object Share Table Lookup.
- ServiceNow REST Table API - `update_incident`.

## Confirmation Criteria
- User is active in NA Org.
- Object permissions present.
- `HasReadAccess == False`.
- Missing row-level sharing path confirmed.

# Resolution

## Remediation Procedure
1. Review record owner and sharing rules.
2. Direct requester or admin to grant access via Manual Share, Public Group addition, or territory/team assignment.
3. Update ServiceNow work notes with findings and remediation path.

## HITL Requirements
- Human operator approval required before granting record-level access.

