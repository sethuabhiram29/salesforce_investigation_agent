---
issue_code: RECORD-OBJ-PERM-MISSING
title: Missing Object Permissions for Record Access
domains:
  - RECORD
version: 1
---

# Purpose
The user cannot access records (such as Reports, Dashboards, Opportunities, Cases, or custom objects) because their Profile or Permission Sets do not grant basic Object-level Read or Create permissions.

# Diagnosis

## Required Evidence
- Caller identity resolved to a Salesforce User in target Org (NA Org).
- User `IsActive` is `True`.
- Affected Object type identified.
- `ObjectPermissions` query reveals missing `PermissionsRead` or `PermissionsCreate`.

## Investigation Procedure
1. Identify affected Object type from incident description or Record ID prefix.
2. Query `ObjectPermissions` for user's Profile and Permission Sets.
3. If object permission is missing, confirm diagnosis as `RECORD-OBJ-PERM-MISSING`.

## Confirmation Criteria
- User is active in NA Org.
- Object-level permission is missing.

# Resolution

## Remediation Procedure
1. Request Manage User Access RITM for required Object permission set.
2. Update incident work notes.

