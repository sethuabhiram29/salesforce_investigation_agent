---
issue_code: LOGIN-6
title: Federation ID Not Synced With Azure (Re-hire Process)
domains:
  - LOGIN
version: 1
---

# Purpose
A rehired user cannot sign in because the Federation ID in Salesforce does not match the one tagged to their new employee ID in Azure. Applies when the user is present and active in SFDC NA and the incident suggests a rehire, a new employee ID, or an Azure identity mismatch.

# Diagnosis
## Required evidence
- User present and active in SFDC NA.
- Current Federation ID in Salesforce.
- The correct Federation ID tagged to the new employee ID, as confirmed by the Azure team (this value is not derivable from Salesforce alone).
- Evidence the user is a rehire or has a new employee ID (from the incident or ServiceNow user data).

## Investigation procedure
1. Retrieve the incident and caller profile from ServiceNow (read-only); note the current employee number.
2. Search SFDC NA for the user. Require a unique match that is active; if not found switch to LOGIN-1, if inactive switch to LOGIN-3.
3. Read the Federation ID and check whether it is correct for the current employee ID.
4. If a correct Federation ID cannot be established from available evidence, flag that the Azure team point of contact must provide it.
5. Record the Azure team's response as evidence when received.

## Permitted diagnostic tools
- Salesforce user search and detail retrieval (read-only).
- ServiceNow: retrieve incident, user (read-only).
- Historical incidents and knowledge graph lookups (context only).

## Confirmation criteria
Confirmed only when:
- The user is found, unique and active, AND
- The Federation ID in Salesforce is observed and verified as incorrect against the Azure-confirmed value, or the Azure team confirms the correct value differs.

## Alternative explanations
- Federation ID simply missing or not equal to the Employee ID: LOGIN-4.
- Federation ID is correct: not this issue; investigate other causes.
- Not a rehire: lower confidence; request clarification.
- Multiple matches: `ambiguous_identity`.

## Insufficient-evidence behavior
- No Azure confirmation available: status `insufficient_evidence`, request the Azure contact; never infer or fabricate the correct Federation ID.

# Resolution
## Required confirmed diagnosis
`status: confirmed`, `issue_code: LOGIN-6`, with evidence refs for the Salesforce state and Azure confirmation.

## Remediation procedure
1. Contact the Azure team point of contact to get the correct Federation ID tagged to the new employee ID (via ServiceNow assignment or notification).
2. Add a work note documenting the current value, the mismatch and the request.
3. Any Salesforce update of the Federation ID follows the approved process and is not performed by the agent unless a supported operation and approval exist.

## Preconditions and permitted operations
- Permitted: ServiceNow work notes and notification or assignment to the Azure team.
- Prohibited: writing a Federation ID value not confirmed by the Azure team.

## Expected result
The correct Federation ID is obtained from the Azure team and the user's Salesforce record is aligned through the approved process.

## Failure and rollback handling
No Salesforce change by the agent. If the Azure team does not respond within the escalation window, escalate to a human operator.

# HITL
- Approval required: always before any Salesforce update; the update itself is only possible if a supported operation exists.
- Present to approver: incident ID, user, current Federation ID, Azure-confirmed value, employee ID, reason, risk of linking the wrong identity.
- Valid approval: explicit and bound to this exact proposal and value.

# Verification
- Expected state: Salesforce Federation ID equals the Azure-confirmed value and the user is active.
- Checks: re-read the user record after the update; confirm the user can authenticate if the user confirms.
- Failure and escalation: mismatch persists, or the Azure value is revised, goes to a human operator.

# Safety Rules
- Never invent evidence or user identifiers.
- Never treat historical similarity as proof.
- Never execute unauthorized changes.
- Escalate when evidence or authorization is insufficient.
- Never derive the correct Federation ID without Azure team confirmation.
