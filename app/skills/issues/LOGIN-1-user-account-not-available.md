---
issue_code: LOGIN-1
title: User Account Not Available
domains:
  - LOGIN
version: 1
---

# Purpose
The caller cannot sign in because no Salesforce user record exists for them. Applies when the incident reports a missing or unknown account, and when ambiguous access incidents ("can't access Salesforce") have a user lookup that returns no match.

Does not apply when a user record is found (use LOGIN-3, LOGIN-4 or other skills).

# Diagnosis
## Required evidence
- Caller identity from ServiceNow: at least one of Federation ID, email, username (or employee number).
- Result of user search in the SFDC NA org.
- Result of the same search in each other org: EMEA, GA, ServiceMax, RIM.

## Investigation procedure
1. Retrieve the incident (`servicenow_get_incident`) and read `caller_id`.
2. Resolve the caller's profile (`servicenow_get_user`) to obtain Federation ID / email / username / employee number.
3. Search the SFDC NA org by those identifiers (global-search equivalent).
4. If not found, repeat the search in EMEA, GA, ServiceMax and RIM, one org at a time.
5. Record each search as evidence, including the identifier used and the org searched.

## Permitted diagnostic tools
- ServiceNow: retrieve incident, retrieve user (read-only).
- Salesforce: user search per org (read-only).
- Historical incidents and knowledge graph lookups (read-only, context only).

## Confirmation criteria
Confirmed only when ALL hold:
- A usable caller identifier was obtained.
- Searches completed successfully (no tool error) in NA, EMEA, GA, ServiceMax and RIM.
- Every search returned zero matching users.

## Alternative explanations
- Identifier differs from the one stored in Salesforce (name change, alias, typo): retry with each other available identifier before concluding.
- Multiple matches: status `ambiguous_identity`, do not choose one.
- User exists in NA but is inactive: switch to LOGIN-3.
- User exists but Federation ID is missing or mismatched: switch to LOGIN-4.

## Insufficient-evidence behavior
- A failed or timed-out search is NOT evidence of absence. Report `insufficient_evidence`.
- Missing caller identifiers: request clarification or escalate; never invent identifiers.
- Not all five orgs searched: do not confirm.

# Resolution
## Required confirmed diagnosis
`status: confirmed`, `issue_code: LOGIN-1`, with evidence refs for all five org searches.

## Remediation procedure
No Salesforce write is permitted. The outcome is a documented finding and hand-off:
1. Add a work note to the incident listing the identifiers and orgs searched, with results.
2. Proceed with onboarding/provisioning follow-up per the team's process (user needs an account created via the standard request route).
3. Route or notify as the incident process requires.

## Preconditions and permitted operations
- Permitted: ServiceNow work note, permitted incident field updates.
- Prohibited: creating or modifying Salesforce users.

## Expected result
Incident documents that the user does not exist in any org, with next-step guidance to the requester or owning team.

## Failure and rollback handling
No Salesforce change to roll back. If the work note fails, retry once, then escalate.

# HITL
- Approval required: no Salesforce write exists. Approval only if policy requires it before closing or reassigning the incident.
- Present to approver (if invoked): incident ID, identifiers searched, per-org search results, proposed incident update.
- Valid approval: explicit, tied to the specific incident update proposal.

# Verification
- Expected state: work note recorded on the incident with the search evidence.
- Checks: re-read the incident and confirm the note and any field updates exist.
- Failure and escalation: if the note is missing, or a later search finds the user, reopen Diagnosis (user may have been provisioned in the meantime).

# Safety Rules
- Never invent evidence or user identifiers.
- Never treat historical similarity as proof.
- Never execute unauthorized changes.
- Escalate when evidence or authorization is insufficient.
- Never conclude "user not present" from a tool error or an empty response with an error status.
