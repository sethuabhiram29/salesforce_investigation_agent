---
issue_code: APP-BU-MISSING
title: Business Unit (BU) or Access Level Missing in Configuration
domains:
  - APPLICATION
version: 1
user_type: Any
condition: "User exists AND IsActive = True AND Business Unit or Access Level NOT Determinable"
---

# Purpose
A user cannot access contract agreements, business division catalogs, or specific application functions because their Business Unit (BU) or Access Level is unconfigured or missing.

# Diagnosis

## Required Evidence
- User exists and `User.IsActive == True`.
- Incident involves Conga / CLM access.
- User's Business Unit (BU) or Access Level cannot be determined from user profile, contact wizard, or ticket details.

## Investigation Procedure
1. Retrieve incident narrative and analyze user profile.
2. Verify user active status in Salesforce.
3. Attempt to determine Business Unit (BU) and Access Level from User profile / Contact record / description.
4. If BU or Access Level is blank or indeterminable, confirm root cause as `APP-BU-MISSING`.
5. Update work notes and inform user to provide Business Unit details or raise Manage User RITM.

## Confirmation Criteria
Confirmed only when:
- User is active in Salesforce.
- Business Unit or Access Level is missing or unresolvable.

# Resolution

## Remediation Procedure
1. Notify requester that Business Unit configuration is missing.
2. Advise user to raise a Manage User RITM specifying their designated Business Unit and required Access Level.
3. Log findings into ServiceNow work notes and set ticket state appropriately.
