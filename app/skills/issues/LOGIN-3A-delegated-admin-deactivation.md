---
issue_code: LOGIN-3A
title: Delegated Admin Deactivation
domains:
  - LOGIN
version: 1
---

# Purpose
A delegated admin user has been deactivated in Salesforce, preventing them from logging in. This issue applies when the user's IsActive field is false and they hold a delegated admin role.

# Diagnosis

## Required Evidence
- The caller's identity must be uniquely resolved to a single Salesforce user record
- The IsActive field on that user record must be confirmed as false
- The user's profile or role indicates delegated admin status

## Investigation Procedure
1. Extract the username or email from the incident
2. Search for the Salesforce user using the extracted identifier
3. Verify the search returns exactly one matching user
4. Retrieve the user's IsActive and Profile fields
5. Confirm IsActive is false AND the user has a delegated admin profile/role

## Permitted Diagnostic Tools
- salesforce_user_search: Search users by username or email
- salesforce_get_user_details: Retrieve full user record

## Confirmation Criteria
- Exactly one user matched
- IsActive is false
- User profile indicates delegated admin role
- All conditions must be met from actual tool responses

## Alternative Explanations
- If IsActive is true, this issue does not apply — consider other LOGIN issues
- If user is not a delegated admin, different reactivation procedures may apply
- If multiple users match, the identity is ambiguous — request clarification

## Insufficient Evidence Behavior
- If the user search returns no results, do not assume the user exists
- If the tool call fails, do not treat the error as evidence
- Report insufficient evidence and recommend clarification

# Resolution

## Required Confirmed Diagnosis
- issue_code: LOGIN-3A
- status: confirmed
- Evidence must show IsActive is false for the identified delegated admin user

## Remediation Procedure
1. Direct reactivation by the automated agent in Salesforce is prohibited per security policy.
2. Formulate resolution guidance notifying the requester that their account was deactivated by a Delegated Administrator.
3. Instruct the requester to submit a 'Manage User' Request Item (RITM) in ServiceNow to obtain authorized approval.
4. Record comprehensive work notes in ServiceNow and transmit notification email to requester.
5. Close/resolve the ServiceNow incident with status 'Resolved'.

## Preconditions and Permitted Operations
- Permitted: ServiceNow work notes, requester communication, incident closure.
- Prohibited: Modifying User.IsActive directly in Salesforce without approved RITM.

## Expected Result
- The user is notified of the exact reason and provided clear RITM submission instructions.
- Work notes and incident status are updated in ServiceNow.

## Failure and Rollback Handling
- If communication delivery fails, retry once, then escalate to human operator.

# HITL

## When Approval Is Required
- Always required before modifying any Salesforce user record

## Information to Present
- Incident number and caller identity
- Confirmed Salesforce user (Username, Name, Id, Profile)
- Current IsActive value (false)
- Proposed change: IsActive → true
- Evidence references supporting the diagnosis

## Risks and Expected Impact
- Risk: Reactivating a user who was intentionally deactivated
- Impact: User will regain access to Salesforce

## Valid Approval
- Approver must confirm the specific user and the reactivation action

# Verification

## Expected Post-Remediation State
- IsActive is true on the target user record

## Checks Required
1. Retrieve the user record after the change
2. Confirm IsActive is true
3. Confirm user profile/role is unchanged

## Failure and Escalation
- If IsActive is still false, flag as failed remediation
- Escalate to Salesforce admin if reactivation is blocked by org policy

# Safety Rules
- Never reactivate a user without confirmed delegated admin status
- Never assume a user is inactive without a successful lookup
- Never treat a tool error as evidence of user status
- Never modify any field other than IsActive
- Escalate when evidence or authorization is insufficient
