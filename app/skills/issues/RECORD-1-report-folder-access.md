---
issue_code: RECORD-1
title: Report or Dashboard Folder Access Missing
domains:
  - RECORD
version: 1
---

# Purpose
The user is unable to view or access a Report or Dashboard because they have not been granted access to the underlying Report or Dashboard Folder (via User, Public Group, or Role sharing).

# Diagnosis

## Required Evidence
- Caller identity resolved to a Salesforce User in target Org (NA Org).
- User `IsActive` is `True`.
- Affected Report or Dashboard ID and Folder ID identified.
- User possesses required Object permissions on Report / Dashboard objects (`PermissionsRunReports`, `PermissionsManageReports`).
- Folder Access check confirms user/group/role lacks `Viewer`, `Editor`, or `Manager` access to the Folder.

## Investigation Procedure
1. Identify the Report or Dashboard ID and target Folder from the ticket description.
2. Confirm user is active in NA Org.
3. Verify user profile has `Run Reports` or `View Dashboards in Public Folders` permission.
4. Query `FolderMember` or `Folder` sharing to determine if user, their Role, or Public Groups have access.
5. If Folder access is absent, confirm diagnosis as `RECORD-1`.

## Permitted Diagnostic Tools
- Salesforce MCP SOQL Tool - Folder & Report Lookup.
- Salesforce MCP SOQL Tool - GroupMember & UserRole.
- ServiceNow REST Table API - `update_incident`.

## Confirmation Criteria
- User is active in NA Org.
- Report/Dashboard object permission is granted.
- User has no access path to the folder.

# Resolution

## Remediation Procedure
1. Identify the Folder Manager / Owner.
2. Share the folder with the user or appropriate Public Group / Role with `Viewer` access.
3. Update ServiceNow incident work notes with folder details and sharing grant status.

## HITL Requirements
- Human operator approval required before modifying Folder sharing.

