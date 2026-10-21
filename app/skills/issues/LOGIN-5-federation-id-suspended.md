---
issue_code: LOGIN-5
title: User Federation ID Suspended
domains:
  - LOGIN
version: 1
---

# Purpose
The caller cannot sign in because their Federation ID has been suspended due to inactivity in the application. Applies when the user exists in the SFDC NA org and the symptom points to a suspended or inactivity-related federation state.

# Diagnosis
## Required evidence
- User record found in SFDC NA (uniquely identified).
- Evidence that the Federation ID is suspended due to inactivity (suspension indicator and last-activity evidence as exposed by the available tools).
- Employee ID for the user.

## Investigation procedure
1. Retrieve the incident and caller profile from ServiceNow (read-only) to obtain identifiers and Employee ID.
2. Search SFDC NA for the user (global-search equivalent). Require a unique match; if not found, switch to LOGIN-1.
3. Read the user's Federation ID state, active status and last-login/last-activity data.
4. Determine whether the suspension is due to inactivity, using the evidence returned, not assumption.
5. Record each lookup as evidence with its reference ID.

## Permitted diagnostic tools
- Salesforce user search and user detail retrieval, including login history if permitted (read-only).
- ServiceNow: retrieve incident, user (read-only).
- Historical incidents and knowledge graph lookups (context only).

## Confirmation criteria
Confirmed only when:
- Exactly one user is found in SFDC NA, AND
- The Federation ID is observed as suspended, AND
- The evidence attributes the suspension to inactivity.

## Alternative explanations
- Federation ID missing or mismatched: LOGIN-4.
- User deactivated: LOGIN-3.
- Suspended for a reason other than inactivity: report `insufficient_evidence` or `escalation_required`; do not label it inactivity.
- Multiple matches: `ambiguous_identity`.

## Insufficient-evidence behavior
- If the suspension cause cannot be determined from available data, do not confirm; escalate.
- A failed lookup is never evidence that the Federation ID is not suspended.

# Resolution
## Required confirmed diagnosis
`status: confirmed`, `issue_code: LOGIN-5`, with evidence refs for the user record and the suspension state.

## Remediation procedure
No direct Salesforce change by the agent:
1. Request the user to raise a Manage User RITM to update the Federation ID to the Employee ID.
2. Add a work note with the finding, the Employee ID and the RITM instructions.

## Preconditions and permitted operations
- Permitted: ServiceNow work note and user communication.
- Prohibited: modifying the Federation ID or any other Salesforce field.

## Expected result
The user has clear instructions to raise the RITM and the incident documents the evidence.

## Failure and rollback handling
If the notification fails, retry once, then escalate. No Salesforce change exists to roll back.

# HITL
- Approval required: only if policy requires it before sending communication or reassigning. No Salesforce write.
- Present to approver (if invoked): incident ID, user, suspension evidence, proposed message.
- Valid approval: explicit and bound to this specific proposal.

# Verification
- Expected state: work note and user communication are recorded on the incident.
- Checks: re-read the incident. After the user's RITM is fulfilled by the owning team, a re-read of the user should show the Federation ID equal to the Employee ID.
- Failure and escalation: missing note, or the state is unchanged after the RITM, goes to a human operator.

# Safety Rules
- Never invent evidence or user identifiers.
- Never treat historical similarity as proof.
- Never execute unauthorized changes.
- Escalate when evidence or authorization is insufficient.
- Never claim inactivity as the cause without supporting evidence.
