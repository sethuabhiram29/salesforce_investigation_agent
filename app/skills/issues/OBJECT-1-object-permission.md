---
issue_code: OBJECT-1
title: Object Permission Issue
domains:
  - OBJECT
version: 1
---

# Purpose
The user cannot access or edit a Salesforce object (e.g., Account, Contact) because their profile or permission set lacks the required object-level permissions (CRUD).

# Diagnosis

## Required Evidence
- The caller's identity must be uniquely resolved to a single Salesforce user record
- The specific object and operation (read, create, edit, delete) must be identified
- The user's profile and permission sets must be retrieved
- The relevant object permissions must be confirmed as missing

## Investigation Procedure
1. Extract the username and the object/operation from the incident
2. Search for the Salesforce user
3. Retrieve the user's profile and assigned permission sets
4. Check object-level permissions for the identified object
5. Confirm the required permission is missing

## Permitted Diagnostic Tools
- salesforce_user_search: Search users by username or email
- salesforce_get_user_details: Retrieve full user record including profile
- salesforce_get_object_permissions: Check object permissions for a user/profile

## Confirmation Criteria
- Exactly one user matched
- The specific object and required operation are identified
- The required permission is confirmed missing from the user's effective permissions

## Alternative Explanations
- If the user has the required permissions, investigate field-level security or sharing rules
- If the object name is wrong, request clarification

## Insufficient Evidence Behavior
- If the object or operation cannot be determined, request clarification
- Do not guess the object name from vague descriptions

# Resolution

## Required Confirmed Diagnosis
- issue_code: OBJECT-1
- status: confirmed
- Evidence must show the specific missing object permission

## Remediation Procedure
1. Determine whether to add the permission via permission set or profile update
2. Propose the specific permission grant
3. Submit for HITL approval

## Preconditions and Permitted Operations
- Only the identified missing permission may be granted
- Must use the least-privilege approach

## Expected Result
- User gains the required object permission
- User can perform the previously blocked operation

# HITL

## When Approval Is Required
- Always required before modifying permissions

## Information to Present
- Incident number and caller
- User, profile, and current permissions
- Missing permission and proposed grant method
- Evidence references

# Verification

## Expected Post-Remediation State
- The user's effective permissions include the granted permission

## Checks Required
1. Re-check the user's object permissions after the change
2. Confirm the required permission is now present

# Safety Rules
- Never grant permissions beyond what is required
- Never assume object names from vague descriptions
- Escalate when the permission model is unclear
