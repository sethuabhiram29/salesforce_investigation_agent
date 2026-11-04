---
issue_code: APP-COMMUNITY-PS-MISSING
title: Only PS Community User Permission Set Missing
domains:
  - APPLICATION
version: 1
user_type: Any
condition: "User exists AND IsActive = True AND Issue relates to Pharma/Community App AND Only PS Community User Permission Set NOT Assigned"
---

# Purpose
An active user attempting to access the Pharma System / Community portal encounters access denied errors because the 'Only PS Community User' (or Pharma Community User) permission set has not been assigned.

# Diagnosis

## Required Evidence
- User exists in Salesforce organization.
- `User.IsActive == True`.
- Incident classified as Pharma App / Community portal issue.
- User lacks 'Only PS Community User' permission set assignment in Salesforce.

## Investigation Procedure
1. Retrieve incident narrative and caller details.
2. Verify user active status (`IsActive == True`).
3. Query assigned permission sets for the user (`salesforce_get_user_permission_sets`).
4. Classify issue type from ticket description keywords (Pharma / Community).
5. Check if 'Only PS Community User' permission set is assigned.
6. If not assigned, confirm root cause as `APP-COMMUNITY-PS-MISSING`.
7. Formulate resolution plan to assign the required Community permission set.

## Confirmation Criteria
Confirmed only when:
- User is active in Salesforce.
- Issue relates to Pharma System / Community application.
- 'Only PS Community User' permission set is absent from user's assignments.

# Resolution

## Remediation Procedure
1. Formulate remediation proposal to assign `Only_PS_Community_User` permission set to the user.
2. Submit proposal to human operator approval gate (HITL).
3. Upon approval, execute assignment via Salesforce API/MCP.
4. Verify assignment in `PermissionSetAssignment`.
5. Update ServiceNow work notes and resolve ticket.
