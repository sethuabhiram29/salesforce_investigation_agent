---
issue_code: RECORD-1B
title: Report or Dashboard Access Issue - Report Folder Not Shared with User
domains:
  - RECORD
version: 2
aliases:
  - RECORD-1
  - RECORD-001
  - RECORD-FOLDER-ACCESS-MISSING
---

# Purpose
The user has valid Object-level permissions to the underlying objects, but cannot view or open the Report or Dashboard because the parent Report or Dashboard Folder has not been shared with the user, their Role, or their Public Groups.

# Diagnosis

## Required Evidence
- User exists in NA Org and `User.IsActive == True`.
- Object-level access to report objects is confirmed present.
- Impacted Report or Dashboard Folder identified.
- Folder sharing configuration confirms user, role, public group, or queue lacks access.

## Investigation Procedure / Analysis Logic
1. Retrieve incident and caller details from ServiceNow (`get_incident`, `get_caller`).
2. Verify user exists in NA Org and is active (`salesforce_user_search`, `salesforce_get_user_details`).
3. Confirm user has required object-level access (perform object access validation before folder sharing validation).
4. Identify impacted Report or Dashboard folder from ticket narrative.
5. Review folder sharing configuration.
6. Verify whether user, role, public group, or queue has access.
7. If folder access is missing, notify folder owner to share access.
8. Retest report/dashboard visibility.
9. Update ServiceNow incident work notes with findings and actions performed.

## Permitted Diagnostic Tools
- ServiceNow REST Table API - `get_incident`.
- ServiceNow REST Table API - `get_caller`.
- Salesforce Folder Query.
- Salesforce Folder Share Query.
- ServiceNow REST Table API - `update_incident`.

## Confirmation Criteria
- User is active in NA Org.
- Object-level access is confirmed present.
- Report or Dashboard folder access is missing.

# Resolution

## Remediation Procedure
1. Identify the respective folder owner (Folder can be shared by respective owners ONLY).
2. Contact and inform the folder owner to add required sharing access (Viewer/Editor) for the user or the user's Public Group / Role.
3. If user needs to create folders manually, guide user to go to reports and create folders.
4. Document the owner notification and sharing details in ServiceNow work notes.

## Permitted Operations
- Direct automated modification of folder shares across unauthorized owners is restricted.
- Procedural Guidance (`Guidance`) must be delivered to caller and folder owner.

## Safety Preconditions
- User exists in NA Org.
- User `IsActive == True`.
- Underlying Object access verified before folder sharing resolution.

## HITL Requirements
- Human operator authorization required to transmit folder sharing guidance and owner notification.
