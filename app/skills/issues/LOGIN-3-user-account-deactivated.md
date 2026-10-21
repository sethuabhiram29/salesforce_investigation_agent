---
issue_code: LOGIN-3
title: User Account Deactivated
domains:
  - LOGIN
version: 1
---

# Purpose
The caller cannot sign in because their Salesforce user record exists in the NA org but is inactive. Applies to "account locked/disabled/can't log in" incidents where the user is found. The goal is to establish who or what deactivated the user, because the follow-up differs by actor.

Note: reconcile with the existing LOGIN-3A (delegated admin deactivation). LOGIN-3A should be treated as the DA branch of this procedure or kept as a separate skill, but the two must not give conflicting instructions.

# Diagnosis
## Required evidence
- User record present in the NA org (id, `IsActive`, identifiers).
- Deactivation details: when it happened and who or what performed it.
- For Mulesoft-driven cases: Kibana log evidence.

## Investigation procedure
1. Resolve caller identifiers from ServiceNow (as in LOGIN-1).
2. Look up the user in SFDC NA. If not found, stop and switch to LOGIN-1.
3. Read `IsActive`. If active, this skill does not apply; investigate LOGIN-4 or other causes.
4. If inactive, retrieve who deactivated the user and when (setup audit trail / deactivation history, as exposed by the available tools).
5. Classify the actor from the evidence:
   - Delegated Admin (DA) user.
   - Mulesoft integration user.
   - Other or unknown.
6. For the Mulesoft actor, query Kibana logs for the deactivation event and note the Workday-related trigger if present.

## Permitted diagnostic tools
- Salesforce user lookup and deactivation history (read-only).
- Kibana log search (read-only), when available.
- ServiceNow: retrieve incident, user (read-only).
- Historical incidents and knowledge graph lookups (context only).

## Confirmation criteria
Confirmed only when:
- The user exists in SFDC NA and `IsActive` is false (observed, not inferred), AND
- The deactivating actor is identified from audit evidence: DA user, or Mulesoft user with matching Kibana log evidence.

If the user is inactive but the actor cannot be established, report `insufficient_evidence` with the observed inactive status as a finding. Do not guess the actor.

## Alternative explanations
- User is active: not this issue.
- User not in NA: LOGIN-1.
- Deactivation caused by inactivity suspension: see the Federation ID suspended skill (LOGIN-5 in the SOP).
- Mulesoft deactivation may stem from an upstream Workday change (rehire, termination, data fix); do not assume.

## Insufficient-evidence behavior
- Audit history or Kibana unavailable: `insufficient_evidence`, escalate to the Mulesoft point of contact.
- Never treat a tool error as `IsActive = false`.

# Resolution
## Required confirmed diagnosis
`status: confirmed`, `issue_code: LOGIN-3`, with evidence refs for the inactive status and the actor.

## Remediation procedure
Per actor, no direct reactivation by the agent:
- DA-deactivated: tell the user to raise a Manage User RITM. Add a work note with the finding and RITM instructions.
- Mulesoft-deactivated: record the Kibana evidence, engage the Mulesoft and Workday teams to find the root cause, and assign or notify them via ServiceNow.
- Unknown actor: escalate to a human operator.

## Preconditions and permitted operations
- Permitted: ServiceNow work notes, user communication, assignment updates.
- Prohibited: reactivating the user or any Salesforce write unless a future approved operation is added to the policy layer.

## Expected result
The user is directed to the correct fulfilment path (RITM) or the incident is with the team able to find the root cause.

## Failure and rollback handling
Notes and assignment changes are reversible. If notification fails, retry once, then escalate.

# HITL
- Approval required: only for the team-routing or communication actions when policy demands. There is no Salesforce write.
- Present to approver (if invoked): incident ID, user, inactive status, actor and timestamp, Kibana evidence if used, proposed action.
- Valid approval: explicit and bound to this action proposal.

# Verification
- Expected state: work note and routing are recorded on the incident; the evidence matches what was reported.
- Checks: re-read the incident; for any reactivation done later by humans, re-read `IsActive`.
- Failure and escalation: missing note or assignment, or contradictory audit data, goes to a human operator.

# Safety Rules
- Never invent evidence or user identifiers.
- Never treat historical similarity as proof.
- Never execute unauthorized changes.
- Escalate when evidence or authorization is insufficient.
- Never name the deactivating actor without audit evidence.
