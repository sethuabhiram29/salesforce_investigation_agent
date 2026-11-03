---
issue_code: LOGIN-1
title: User Account Not Available Across Enterprise Organizations
domains:
  - LOGIN
version: 2
---

# Purpose
The caller cannot sign in because no Salesforce user record exists for them across registered corporate organizations. Applies when:
1. The incident reports a missing or unknown user account, and cross-org user lookups return zero matches.
2. An unapproved URL was used, and subsequent verification confirms the user has no provisioned account in the Main Organization.
3. A cross-org or Main Org URL was used, but the user does not exist in any registered organization (NA, EMEA, ACE/GA, ServiceMax).

# Diagnosis
## Required evidence
- Caller identity from ServiceNow: at least one of Federation ID, email, username, or employee number.
- Result of user search in the primary Main Org (NA: `bdx.my.salesforce.com`).
- Result of user search across secondary organizations: EMEA (`bd2my.salesforce.com`), ACE/GA (`bdxga.my.salesforce.com`), and ServiceMax (`bdsmx.my.salesforce.com`).

## Investigation procedure
1. Retrieve incident and resolve caller profile to obtain target email, username, and employee ID.
2. Search the primary North America Salesforce instance (`bdx.my.salesforce.com`).
3. If not found in Main Org, repeat search across secondary organizations (EMEA, ACE/GA, ServiceMax), recording search results per organization.
4. If an unapproved URL was cited in the incident, verify if the user exists in the Main Organization before concluding. If absent from the Main Org as well, classify under this skill.

## Permitted diagnostic tools
- ServiceNow: retrieve incident, retrieve user (read-only).
- Salesforce: user search per org (`salesforce_user_search`, `cross_org_user_search`).
- Historical incidents and knowledge graph lookups (read-only).

## Confirmation criteria
Confirmed only when:
- Caller identifier was resolved.
- Searches completed successfully across all registered organizations (NA, EMEA, ACE/GA, ServiceMax).
- Every search confirmed zero matching users (account is absent everywhere), OR user used an unapproved URL and is absent from Main Org.

## Alternative explanations
- User exists in Main Org (NA): investigate account deactivation (LOGIN-3) or Federation ID (LOGIN-4 / LOGIN-6).
- User exists in another organization (EMEA / ACE/GA / ServiceMax): route per LOGIN-1B.
- User exists in Main Org but used an unapproved URL: route per LOGIN-2.

# Resolution
## Required confirmed diagnosis
`status: confirmed`, `issue_code: LOGIN-1`, with evidence references for all organizations checked.

## Remediation procedure
No Salesforce metadata mutation is permitted (account creation requires standard HR/IT onboarding).
1. Add a comprehensive work note to the ServiceNow incident detailing:
   - The user identifiers checked (email, employee ID).
   - The complete list of Salesforce organizations searched (NA `bdx`, EMEA `bd2my`, ACE/GA `bdxga`, SMAX `bdsmx`) and the zero-match verification outcome.
2. Inform the user in ticket communication that no active account was located in any enterprise Salesforce organization. No RITM request is required from the caller at this stage; the incident is being rerouted directly to the HCL Service Desk for further handling.
3. Reassign and reroute the incident ticket to the **HCL Service Desk** assignment group for further assistance.

## Preconditions and permitted operations
- Permitted: ServiceNow work note update, incident customer notification, assignment group reassignment to HCL Service Desk.
- Prohibited: direct creation of user records in Salesforce without an approved onboarding workflow.

# HITL
- Approval required: only if policy mandates approval for cross-department incident rerouting. No Salesforce writes involved.
- Present to operator: Incident ID, organizations searched, verification results, target assignment group (HCL Service Desk).
- Valid approval: Explicit confirmation to notify user and reroute to HCL Service Desk.

# Verification
- Expected state: Incident contains complete cross-org search work note, user communication, and reassignment to HCL Service Desk.
- Checks: Re-query ServiceNow incident to confirm work note and assignment group updates.

# Safety Rules
- Never invent evidence or user identifiers.
- Never conclude a user is absent from a tool error or timeout.
- Never directly create user accounts in production without an authorized onboarding workflow.
