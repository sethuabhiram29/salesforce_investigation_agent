---
issue_code: LOGIN-1B
title: User Found in Another Salesforce Organization
domains:
  - LOGIN
version: 1
---

# Purpose
The user cannot log in to the primary North America Salesforce organization (`bdx.my.salesforce.com`) because their user account resides in an alternate enterprise Salesforce organization (EMEA `bd2my.salesforce.com`, ACE/GA `bdxga.my.salesforce.com`, or ServiceMax `bdsmx.my.salesforce.com`).

# Diagnosis
## Required evidence
- Target caller or affected user identity (email, username, employee ID).
- Result of user search across enterprise organizations:
  - Absent in NA Main Org (`bdx.my.salesforce.com`).
  - Present in alternate enterprise org (e.g. EMEA `bd2my.salesforce.com`, ACE/GA `bdxga.my.salesforce.com`, or SMAX `bdsmx.my.salesforce.com`).

## Investigation procedure
1. Search primary North America Salesforce instance (`bdx.my.salesforce.com`).
2. If user is absent from primary instance, execute cross-org directory search across secondary enterprise orgs:
   - EMEA (`https://bd2my.salesforce.com`)
   - ACE/GA (`https://bdxga.my.salesforce.com`)
   - ServiceMax (`https://bdsmx.my.salesforce.com`)
3. Record the target user identity, absent org status, and matched secondary org as evidence.

## Permitted diagnostic tools
- Salesforce user search (`salesforce_user_search`).
- Cross-org directory lookup (`cross_org_user_search`).
- ServiceNow ticket inspection.

## Confirmation criteria
Confirmed only when:
- Target user does not exist in primary NA instance, AND
- Target user record is located in an alternate enterprise organization.

# Resolution
## Required confirmed diagnosis
`status: confirmed`, `issue_code: LOGIN-1B`.

## Remediation procedure
No Salesforce record update in primary org is required. Provide cross-org routing guidance:
1. Provide the user with the correct regional/functional login URL for their organization:
   - For EMEA: `https://bd2my.salesforce.com` (or `https://bd2.my.salesforce.com`)
   - For ACE/GA: `https://bdxga.my.salesforce.com`
   - For ServiceMax: `https://bdsmx.my.salesforce.com`
2. Update ServiceNow ticket work notes with the identified target organization and redirection instructions.
3. If the user requires access to the North America org as well, guide them to submit a cross-org provisioning request.

# HITL
- Approval required: No Salesforce metadata write is required. Routing guidance to user only.
- Present to operator: Incident ID, user identity, target organization identified, canonical login URL.
- Valid approval: Explicit confirmation to notify user with target org login URL.

# Verification
- Expected state: Guidance documented in incident work note and communicated to caller.
- Checks: Confirm caller is provided official regional URL for their assigned organization.
- Failure handling: If user reports ongoing issues after using regional URL, verify active status in target organization.

# Safety Rules
- Never invent evidence or org affiliations.
- Never create a duplicate account in the primary org without an approved cross-org provisioning request.
- Verify whether the user actually has an active account in the secondary organization.
