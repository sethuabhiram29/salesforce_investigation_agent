---
issue_code: LOGIN-2
title: Wrong URL Used to Access Salesforce
domains:
  - LOGIN
version: 1
---

# Purpose
The caller cannot reach or sign in to Salesforce because they are using a login URL that does not point to SFDC NA or another approved commercial org. Applies when the incident mentions a URL, bookmark, redirect, or "page not found / wrong login page" symptom, or when the user record and Federation ID are healthy but access still fails.

# Diagnosis
## Required evidence
- Caller identity (Federation ID / email / username), obtained as in LOGIN-1.
- The login URL the user reports using (from incident description, work notes or user reply).

## Investigation procedure
1. Retrieve the incident and caller details (read-only ServiceNow tools).
2. Extract the login URL from the incident text. If none is present, request it from the user; do not guess.
3. Compare the URL host against the approved login URL catalogue (SFDC NA and approved commercial orgs). The catalogue is configuration data, not hardcoded in this skill.
4. Record the URL, the matched or unmatched catalogue entry, and the catalogue version as evidence.

## Permitted diagnostic tools
- ServiceNow: retrieve incident, retrieve user (read-only).
- Approved-URL catalogue lookup (read-only).
- Historical incidents and knowledge graph lookups (context only).

## Confirmation criteria
Confirmed only when:
- A concrete URL from the incident or the user is recorded as evidence, AND
- It does not match SFDC NA or any approved commercial org in the catalogue.

## Alternative explanations
- URL is correct: this skill does not apply. Re-investigate LOGIN-1, LOGIN-3, LOGIN-4.
- URL points to a different but approved commercial org where the user has no account: consider LOGIN-1.
- URL is a typo or truncated: record it, ask for a screenshot or exact URL before confirming.

## Insufficient-evidence behavior
- No URL available: status `insufficient_evidence`, request clarification from the caller.
- Catalogue lookup failed: do not confirm; escalate.

# Resolution
## Required confirmed diagnosis
`status: confirmed`, `issue_code: LOGIN-2`, with the evidence ref for the URL comparison.

## Remediation procedure
No Salesforce change. Route the ticket to the Help Desk team:
1. Add a work note with the incorrect URL, the finding, and the correct login URL guidance.
2. Reassign the incident to the Help Desk assignment group.

## Preconditions and permitted operations
- Permitted: ServiceNow work note and assignment-group update.
- Prohibited: any Salesforce write.

## Expected result
Incident is documented and reassigned to Help Desk with the evidence attached.

## Failure and rollback handling
If reassignment fails, retry once, then escalate to a human operator. Reassignment can be reverted by reassigning back.

# HITL
- Approval required: only if policy requires approval for reassignment. No Salesforce write is involved.
- Present to approver (if invoked): incident ID, URL used, catalogue comparison, target assignment group.
- Valid approval: explicit and tied to this specific reassignment proposal.

# Verification
- Expected state: incident carries the work note and is assigned to Help Desk.
- Checks: re-read the incident and confirm both.
- Failure and escalation: if either is missing, retry once, then escalate.

# Safety Rules
- Never invent evidence or user identifiers.
- Never treat historical similarity as proof.
- Never execute unauthorized changes.
- Escalate when evidence or authorization is insufficient.
- Never assume a URL is wrong without a recorded URL from the incident or user.
