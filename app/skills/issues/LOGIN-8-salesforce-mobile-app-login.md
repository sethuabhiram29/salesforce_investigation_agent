---
issue_code: LOGIN-8
title: Unable to Log In Using Salesforce Mobile App
domains:
  - LOGIN
version: 1
---

# Purpose
The caller cannot sign in through the Salesforce Mobile app. Applies when the incident names the mobile app and the user exists in SFDC NA. The common causes are an incorrect Federation ID or incorrect mobile setup.

# Diagnosis
## Required evidence
- User present in SFDC NA.
- Employee ID for the user.
- Current Federation ID in Salesforce.
- Evidence that the issue is specific to the mobile app (from the incident or user).

## Investigation procedure
1. Retrieve the incident and caller profile from ServiceNow (read-only).
2. Confirm the symptom is mobile-app specific.
3. Search SFDC NA for the user. Require a unique match; if not found, switch to LOGIN-1.
4. Read the Federation ID and compare with the Employee ID. The Federation ID should always be the Employee ID.
5. If they match, treat the likely cause as setup and provide the mobile setup document.
6. Record the evidence for each step.

## Permitted diagnostic tools
- Salesforce user search and detail retrieval (read-only).
- ServiceNow: retrieve incident, user (read-only).
- Historical incidents and knowledge graph lookups (context only).

## Confirmation criteria
Two supported outcomes:
- Federation ID mismatch or missing: confirmed finding that the Federation ID is incorrect (follow LOGIN-4 for correction).
- Federation ID matches the Employee ID: finding that Federation ID is not the cause; the user is directed to the mobile setup document. Confirm as LOGIN-8 only on that evidence plus the mobile-specific symptom.

## Alternative explanations
- User inactive: LOGIN-3.
- Federation ID suspended: LOGIN-5.
- Wrong URL or server on the device: LOGIN-2.
- Setup is not the cause and nothing else is found: `escalation_required`.

## Insufficient-evidence behavior
- Failed lookup: `insufficient_evidence`; never infer a mismatch.
- Unclear whether the issue is mobile specific: ask the user to clarify.

# Resolution
## Required confirmed diagnosis
`status: confirmed`, `issue_code: LOGIN-8`, with evidence refs for the user record and the Federation ID comparison.

## Remediation procedure
1. If the Federation ID is wrong, hand off to the LOGIN-4 resolution path, with its HITL approval.
2. If correct, send the user the Salesforce mobile setup document and instructions.
3. Add a work note describing the finding and what was sent.

## Preconditions and permitted operations
- Permitted: ServiceNow work note, sending the approved setup document.
- Prohibited: any Salesforce write by this skill itself.

## Expected result
The user has either a corrected Federation ID (via LOGIN-4) or the setup guidance.

## Failure and rollback handling
If sending fails, retry once, then escalate. Communication cannot be rolled back, but a follow-up note can be added.

# HITL
- Approval required: no, for sending the standard setup document unless policy requires it. A Federation ID update requires approval under LOGIN-4.
- Present to approver (if invoked): incident ID, user, comparison, proposed action.
- Valid approval: explicit and bound to the specific proposal.

# Verification
- Expected state: setup document sent and recorded, or Federation ID corrected under LOGIN-4.
- Checks: re-read the incident; re-read the user record if corrected; ask the user to confirm login.
- Failure and escalation: if the user still cannot log in, reopen Diagnosis or escalate to a human operator.

# Safety Rules
- Never invent evidence or user identifiers.
- Never treat historical similarity as proof.
- Never execute unauthorized changes.
- Escalate when evidence or authorization is insufficient.
- Never claim setup is the cause without having checked the Federation ID first.
