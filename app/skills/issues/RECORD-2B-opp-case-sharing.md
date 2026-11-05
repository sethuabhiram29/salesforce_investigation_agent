---
issue_code: RECORD-2B
title: User Unable to Access Opportunity or Case - Missing Record-Level Sharing
domains:
  - RECORD
version: 2
aliases:
  - RECORD-2
  - RECORD-002
  - RECORD-OPP-CASE-SHARING-MISSING
---

# Purpose
The user has valid Object-level access to the Opportunity or Case object, but cannot access a specific record because row-level record sharing is missing (`UserRecordAccess.HasReadAccess == False`), and no active sharing path exists through Owner, OWD, Role Hierarchy, Sharing Rules, Public Groups, Opportunity/Case Teams, Territories, or Manual Sharing.

# Diagnosis

## Required Evidence
- User exists in NA Org and `User.IsActive == True`.
- Object-level Read access exists for Opportunity or Case (`PermissionsRead == True`).
- Affected Record ID identified.
- `UserRecordAccess.HasReadAccess` is confirmed `False`.
- Comprehensive sharing audit confirms no active sharing grant path.

## Investigation Procedure / Analysis Logic
1. Retrieve incident and caller details from ServiceNow (`get_incident`, `get_caller`).
2. Verify user exists and is active (`salesforce_get_user_details`).
3. Verify object-level access exists (applicable only when object access exists but record access is missing).
4. Execute `UserRecordAccess` validation for `(UserId, RecordId)`.
5. If `UserRecordAccess` returns `HasReadAccess = False`, review record ownership.
6. Review Org-Wide Defaults (OWD) configuration (Private or Public Read Only).
7. Review Role Hierarchy, Sharing Rules, Public Groups, Queue Membership, Opportunity Teams, Case Teams, Territory Assignments, and Manual Sharing.
8. Identify missing access path.
9. Request appropriate RITM or sharing update.
10. Revalidate `UserRecordAccess`.
11. Update ServiceNow work notes with findings and next steps.

## Permitted Diagnostic Tools
- ServiceNow REST Table API - `get_incident`.
- ServiceNow REST Table API - `get_caller`.
- Salesforce MCP SOQL Tool - ObjectPermissions (`salesforce_get_object_permissions`).
- Salesforce MCP SOQL Tool - UserRecordAccess (`salesforce_get_record_access`).
- Salesforce MCP SOQL Tool - GroupMember (`salesforce_query`).
- ServiceNow REST Table API - `update_incident`.

## Confirmation Criteria
- User is active in NA Org.
- Object-level access is `True`.
- `UserRecordAccess.HasReadAccess == False`.
- Sharing audit confirms missing sharing path.

# Resolution

## Remediation Procedure
1. Identify the appropriate sharing path for the affected Opportunity or Case (Opportunity Team, Case Team, Public Group, Territory, or Manual Share).
2. Formulate resolution instructions requesting access addition via the approved team/group or sharing update.
3. Update ServiceNow incident work notes with record sharing details and next steps.

## Permitted Operations
- Procedural Guidance (`Guidance`) or Team assignment instructions must be delivered to requester.

## Safety Preconditions
- User exists in NA Org.
- User `IsActive == True`.
- Object-level access confirmed prior to record sharing remediation.

## HITL Requirements
- Human operator authorization required to transmit sharing update guidance to requester.
