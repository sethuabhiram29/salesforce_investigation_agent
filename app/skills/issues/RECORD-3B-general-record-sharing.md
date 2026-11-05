---
issue_code: RECORD-3B
title: User Unable to Access Salesforce Record - Missing Record-Level Sharing
domains:
  - RECORD
version: 2
aliases:
  - RECORD-3
  - RECORD-003
  - RECORD-SHARING-MISSING
---

# Purpose
The user has confirmed Object-level access to the SObject type, but cannot access a specific record because row-level sharing is missing (`UserRecordAccess.HasReadAccess == False`), and no active sharing path exists through Owner, OWD, Sharing Rules, Public Groups, Queues, Teams, Manual Sharing, Territory Assignments, or Role Hierarchy.

# Diagnosis

## Required Evidence
- User exists in NA Org and `User.IsActive == True`.
- Affected Record ID and SObject type identified.
- Object-level access confirmed present (`PermissionsRead == True`).
- `UserRecordAccess.HasReadAccess == False`.
- Review of standard object share table (e.g. `AccountShare`, `*__Share`) and row cause confirms missing sharing path.

## Investigation Procedure / Analysis Logic
1. Retrieve incident and caller details from ServiceNow (`get_incident`, `get_caller`).
2. Verify user exists and is active (`salesforce_get_user_details`).
3. Collect affected Record ID.
4. Execute `UserRecordAccess` validation (review sharing only after object access is confirmed).
5. Verify record ownership.
6. Review OWD, Sharing Rules, Public Groups, Queues, Teams, Manual Sharing, Territory Assignments, and Role Hierarchy.
7. Compare user access with a working user (inspect org-wide sharing and territory sharing causes on working user).
8. Identify missing access path (inspect standard share object e.g. `AccountShare` for `UserOrGroupId` and `RowCause`).
9. Grant required access through approved process.
10. Re-run `UserRecordAccess` validation.
11. Update ServiceNow work notes with findings and actions performed.

## Permitted Diagnostic Tools
- ServiceNow REST Table API - `get_incident`.
- ServiceNow REST Table API - `get_caller`.
- Salesforce MCP SOQL Tool - UserRecordAccess (`salesforce_get_record_access`).
- Salesforce MCP SOQL Tool - GroupMember (`salesforce_query`).
- Salesforce Record Sharing Queries (`salesforce_get_record_sharing`, `*Share` tables).
- ServiceNow REST Table API - `update_incident`.

## Confirmation Criteria
- User is active in NA Org.
- Object access is confirmed present.
- `UserRecordAccess.HasReadAccess == False`.
- Sharing table review confirms absence of valid row-level grant.

# Resolution

## Remediation Procedure
1. Identify the appropriate record sharing mechanism (Public Group, Queue, Territory, Team, or Manual Share on `*Share` table).
2. Formulate resolution action requesting or granting required record sharing access per approved organizational security process.
3. Verify that `UserRecordAccess.HasReadAccess` becomes `True` post-assignment.
4. Update ServiceNow incident work notes with sharing cause details.

## Permitted Operations
- Procedural Guidance (`Guidance`) or authorized record share update.

## Safety Preconditions
- User exists in NA Org.
- User `IsActive == True`.
- Object-level access verified before record sharing remediation.

## HITL Requirements
- Human operator authorization required before executing or transmitting record sharing updates.
