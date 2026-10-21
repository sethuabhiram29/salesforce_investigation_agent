---
issue_code: LOGIN-7
title: External User Federation ID Not Synced With CIAM
domains:
  - LOGIN
version: 1
---

# Purpose
An external user cannot sign in because their Federation ID in Salesforce is not in sync with the CIAM system. Applies to external (non-employee) users who are present and active in SFDC NA.

# Diagnosis
## Required evidence
- User present and active in SFDC NA.
- Federation ID currently in Salesforce.
- The CIAM federation ID for the user, as provided by the CIAM team point of contact.

## Investigation procedure
1. Retrieve the incident and caller details from ServiceNow (read-only).
2. Search SFDC NA for the user. Require a unique, active match; otherwise switch to LOGIN-1 or LOGIN-3.
3. Confirm the user is external from the evidence (user type, email domain, or incident text).
4. Read the Federation ID in Salesforce.
5. Obtain the CIAM federation ID from the CIAM team and compare.
6. Record all lookups and the CIAM response as evidence.

## Permitted diagnostic tools
- Salesforce user search and detail retrieval (read-only).
- ServiceNow: retrieve incident, user (read-only).
- Historical incidents and knowledge graph lookups (context only).

## Confirmation criteria
Confirmed only when:
- The user is unique, active, and external, AND
- The Salesforce Federation ID is observed and differs from the CIAM federation ID provided by the CIAM team.

## Alternative explanations
- Employee user whose Federation ID differs from Employee ID: LOGIN-4.
- IDs match: this issue is contradicted; check other causes.
- User not active or not found: LOGIN-3 or LOGIN-1.
- Multiple matches: `ambiguous_identity`.

## Insufficient-evidence behavior
- No CIAM value available: `insufficient_evidence`, request it from the CIAM point of contact. Never assume the CIAM value.

# Resolution
## Required confirmed diagnosis
`status: confirmed`, `issue_code: LOGIN-7`, with evidence refs for both the Salesforce and CIAM values.

## Remediation procedure
1. Engage the CIAM team point of contact through ServiceNow assignment or notification, with the evidence.
2. Align the Federation ID with the CIAM value through the approved process. The agent only writes if a supported operation and approval exist.
3. Add a work note with the finding and actions.

## Preconditions and permitted operations
- Permitted: ServiceNow notes, assignment, notification.
- Prohibited: writing any Federation ID not confirmed by CIAM.

## Expected result
Federation ID in Salesforce equals the CIAM federation ID.

## Failure and rollback handling
No Salesforce change by default. If a later approved update fails, record the error and escalate; rollback restores the previous value only with approval.

# HITL
- Approval required: always before any Salesforce write.
- Present to approver: incident ID, user, current and CIAM values, reason, risk (wrong value breaks external login or links the wrong identity), expected outcome.
- Valid approval: explicit and bound to the exact proposal.

# Verification
- Expected state: Salesforce Federation ID equals the CIAM value.
- Checks: re-read the user record and compare to the CIAM-confirmed value.
- Failure and escalation: any mismatch, or CIAM revising the value, goes to a human operator.

# Safety Rules
- Never invent evidence or user identifiers.
- Never treat historical similarity as proof.
- Never execute unauthorized changes.
- Escalate when evidence or authorization is insufficient.
- Never use an employee ID as the Federation ID for external users unless the CIAM team confirms it.
