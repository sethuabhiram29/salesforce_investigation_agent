---
issue_code: LOGIN-4
title: Federation ID Missing
domains:
  - LOGIN
version: 1
---

# Purpose
The user cannot authenticate via SSO because their Salesforce user record is missing a Federation ID (FederationIdentifier field). This prevents the identity provider from matching the user to their Salesforce account.

# Diagnosis

## Required Evidence
- The caller's identity must be uniquely resolved to a single Salesforce user record
- The FederationIdentifier field on that user record must be confirmed as null or empty
- The user's IsActive status should be confirmed as true (if inactive, a different issue applies)

## Investigation Procedure
1. Extract the username or email from the incident
2. Search for the Salesforce user using the extracted identifier
3. Verify the search returns exactly one matching user
4. Retrieve the user's FederationIdentifier and IsActive fields
5. Confirm FederationIdentifier is null/empty AND IsActive is true

## Permitted Diagnostic Tools
- salesforce_user_search: Search users by username or email
- salesforce_get_user_details: Retrieve full user record

## Confirmation Criteria
- Exactly one user matched
- FederationIdentifier is null or empty string
- User IsActive is true
- All three conditions must be met from actual tool responses

## Alternative Explanations
- If FederationIdentifier is present, this issue does not apply — consider other LOGIN issues
- If IsActive is false, investigate LOGIN-3A (deactivation) instead
- If multiple users match, the identity is ambiguous — request clarification

## Insufficient Evidence Behavior
- If the user search returns no results, do not assume the user exists
- If the tool call fails, do not treat the error as evidence
- Report insufficient evidence and recommend clarification

# Resolution

## Required Confirmed Diagnosis
- issue_code: LOGIN-4
- status: confirmed
- Evidence must show FederationIdentifier is null/empty for the identified user

## Remediation Procedure
1. Determine the correct Federation ID value (typically the user's SSO email or corporate ID)
2. Propose updating the FederationIdentifier field on the confirmed user record
3. Submit the proposal for HITL approval

## Preconditions and Permitted Operations
- Only the FederationIdentifier field may be modified
- The target user must be the same user confirmed in diagnosis
- The new value must follow the organization's Federation ID format

## Expected Result
- FederationIdentifier is populated with the approved value
- User can authenticate via SSO

## Failure and Rollback Handling
- If the update fails, record the error and escalate
- If the wrong value was set, the field can be corrected with a new approved change

# HITL

## When Approval Is Required
- Always required before modifying any Salesforce user record

## Information to Present
- Incident number and caller identity
- Confirmed Salesforce user (Username, Name, Id)
- Current FederationIdentifier value (null/empty)
- Proposed new FederationIdentifier value
- Evidence references supporting the diagnosis

## Risks and Expected Impact
- Risk: Setting incorrect Federation ID could map SSO to wrong user
- Impact: User will be able to authenticate via SSO after change

## Valid Approval
- Approver must confirm the specific user and proposed value
- Generic "approved" without reviewing details is not sufficient

# Verification

## Expected Post-Remediation State
- FederationIdentifier is populated with the approved value on the target user

## Checks Required
1. Retrieve the user record after the change
2. Confirm FederationIdentifier matches the approved value
3. Confirm IsActive is still true

## Failure and Escalation
- If FederationIdentifier does not match, flag as failed remediation
- If user became inactive during the process, escalate

# Safety Rules
- Never invent a Federation ID value
- Never assume a user exists without a successful search
- Never treat a tool error as evidence that the field is empty
- Never modify any field other than FederationIdentifier
- Escalate when evidence or authorization is insufficient
