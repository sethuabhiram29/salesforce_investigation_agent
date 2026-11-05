---
issue_code: RECORD-4
title: Missing Field-Level Security (FLS) on Record
domains:
  - RECORD
version: 1
---

# Purpose
The user has read access to the record itself, but specific fields on the record are not visible or editable due to missing Field-Level Security (FLS) settings on their Profile or Permission Sets, as confirmed when compared against a baseline mirror user.

# Diagnosis

## Required Evidence
- Caller identity resolved to a Salesforce User in target Org (NA Org).
- User `IsActive` is `True`.
- Affected Record ID and Field Name identified.
- `UserRecordAccess.HasReadAccess` is `True` for the record.
- Comparison with mirror user reveals FLS difference (`PermissionsRead` or `PermissionsEdit` is `False` for caller).

## Investigation Procedure
1. Identify affected Record ID and target Field.
2. Confirm user can access the record (`UserRecordAccess.HasReadAccess == True`).
3. Query `FieldPermissions` for target user and compare against mirror user.
4. If field permission is missing for caller while present for mirror user, confirm diagnosis as `RECORD-4`.

## Permitted Diagnostic Tools
- Salesforce MCP SOQL Tool - FieldPermissions Lookup.
- Salesforce MCP SOQL Tool - Mirror User Profile/PermSet Comparator.
- ServiceNow REST Table API - `update_incident`.

## Confirmation Criteria
- User is active in NA Org.
- Record read access confirmed.
- Field is not visible/editable due to missing FLS.

# Resolution

## Remediation Procedure
1. Identify the Permission Set or Profile adjustment required to grant field visibility/editability.
2. Instruct requester to submit Manage User Access RITM for FLS permission set assignment.
3. Update ServiceNow work notes with findings and field permission gap.

## HITL Requirements
- Human operator approval required before modifying FLS or assigning new permission sets.

