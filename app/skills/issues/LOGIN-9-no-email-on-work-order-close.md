---
issue_code: LOGIN-9
title: User Not Receiving Email While Closing Work Order
domains:
  - LOGIN
version: 1
---

# Purpose
A user does not receive an email when closing a work order. Applies when the user is present and active in SFDC NA and the issue is traced to an unverified email or a Federation ID that is out of sync with CIAM.

# Diagnosis
## Required evidence
- User present and active in SFDC NA.
- Email address on the user record and its verification status.
- Federation ID in Salesforce and the CIAM federation ID provided by the CIAM team.

## Investigation procedure
1. Retrieve the incident and caller details from ServiceNow (read-only).
2. Search SFDC NA for the user. Require a unique, active match; otherwise switch to LOGIN-1 or LOGIN-3.
3. Check whether the user's email is verified.
4. Read the Federation ID and compare it with the CIAM federation ID from the CIAM point of contact.
5. Record the evidence for each check.

## Permitted diagnostic tools
- Salesforce user search and detail retrieval (read-only).
- ServiceNow: retrieve incident, user (read-only).
- Historical incidents and knowledge graph lookups (context only).

## Confirmation criteria
Confirmed when the user is unique and active AND at least one of the following is observed:
- The email is not verified.
- The Federation ID differs from the CIAM federation ID.

State which condition(s) were found. Both can apply.

## Alternative explanations
- Email verified and IDs match: not this issue; consider mail delivery or work order configuration problems and escalate.
- User inactive or not found: LOGIN-3 or LOGIN-1.
- Multiple matches: `ambiguous_identity`.

## Insufficient-evidence behavior
- Verification status unavailable or no CIAM value: `insufficient_evidence`; request the CIAM contact. Never assume the email is unverified.

# Resolution
## Required confirmed diagnosis
`status: confirmed`, `issue_code: LOGIN-9`, with evidence refs for the email status and/or Federation ID comparison.

## Remediation procedure
1. Unverified email: ask the user to complete email verification and document the steps in a work note.
2. Federation ID mismatch: engage the CIAM team through ServiceNow; Salesforce alignment follows the approved process, as in LOGIN-7.
3. Add a work note with the findings and actions.

## Preconditions and permitted operations
- Permitted: ServiceNow work notes, user communication, assignment to the CIAM team.
- Prohibited: writing Federation ID or email values without approval and confirmation.

## Expected result
Email is verified and the Federation ID is in sync, so work order closure emails are delivered.

## Failure and rollback handling
If communication fails, retry once, then escalate. No Salesforce change by default.

# HITL
- Approval required: always before any Salesforce write. Not required for the standard user instructions unless policy demands it.
- Present to approver: incident ID, user, email status, Federation ID vs CIAM value, proposed action, risk, expected outcome.
- Valid approval: explicit and bound to the exact proposal.

# Verification
- Expected state: email shows as verified and the Federation ID matches CIAM, where those were the findings.
- Checks: re-read the user record, then ask the user to close a work order or confirm the email arrives.
- Failure and escalation: if the email still does not arrive, escalate to a human operator.

# Safety Rules
- Never invent evidence or user identifiers.
- Never treat historical similarity as proof.
- Never execute unauthorized changes.
- Escalate when evidence or authorization is insufficient.
- Never mark an email as verified on the user's word alone.
