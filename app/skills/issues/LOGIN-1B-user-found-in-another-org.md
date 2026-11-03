---
issue_code: LOGIN-1B
title: User Found in Another Salesforce Organization
domains:
  - LOGIN
version: 2
---

# Purpose
The user's authentication fails on the primary North America Salesforce instance (`bdx.my.salesforce.com`) or regional portal because their account is provisioned in a secondary enterprise Salesforce organization, or they are accessing a secondary environment supported by a dedicated regional team.

### Applicable Scenarios:
1. **User accessed Main Org URL (`bdx.my.salesforce.com`)**, but their user account actually resides in an alternate enterprise org (EMEA, ACE/GA, or ServiceMax).
2. **User accessed a secondary org URL (`bd2my`, `bdxga`, `bdsmx`)** and their account exists in that organization, which is supported by a dedicated regional support team (out of NA support scope).
3. **User accessed a secondary org URL**, but their account resides in a different secondary enterprise organization.

# Diagnosis
## Required evidence
- Target caller or affected user identity (email, username, employee ID).
- Result of cross-organization directory search:
  - Absent in Main Org (`bdx.my.salesforce.com`) or accessed a secondary org.
  - Located in a specific secondary enterprise organization:
    - EMEA: `https://bd2my.salesforce.com` (`OrgId: 00Dxx000000EMEA`)
    - ACE/GA: `https://bdxga.my.salesforce.com` (`OrgId: 00Dxx000000ACEGA`)
    - ServiceMax: `https://bdsmx.my.salesforce.com` (`OrgId: 00Dxx000000SMAX`)

## Investigation procedure
1. Validate the provided login URL and identify which organization it is mapped to.
2. If the URL points to a secondary organization (e.g. EMEA `bd2my`):
   - Check if the affected user exists in that specific organization.
   - If user exists in that secondary org: confirm **LOGIN-1B** (Regional Scope Reroute).
   - If user does not exist in that secondary org: check Main Org (NA) first:
     - If user exists in Main Org: route per **LOGIN-2** (provide `https://bdx.my.salesforce.com`).
     - If user does not exist in Main Org: search remaining secondary orgs. If located in another secondary org, confirm **LOGIN-1B**. If missing across all orgs, route per **LOGIN-1** (RITM via HCL Service Desk).
3. If the URL points to the Main Organization (`bdx.my.salesforce.com`), but the user is missing in Main Org:
   - Search secondary enterprise orgs (EMEA, ACE/GA, ServiceMax).
   - If located in a secondary org: confirm **LOGIN-1B**.
   - If missing across all orgs: route per **LOGIN-1** (RITM via HCL Service Desk).

## Permitted diagnostic tools
- Salesforce user search (`salesforce_user_search`).
- Cross-org directory search (`cross_org_user_search`).
- Neo4j Knowledge Graph approved orgs repository (`get_approved_orgs`).
- ServiceNow ticket inspection.

## Confirmation criteria
Confirmed only when:
- Target user record is located in an alternate secondary organization (EMEA, ACE/GA, ServiceMax).

# Resolution
## Required confirmed diagnosis
`status: confirmed`, `issue_code: LOGIN-1B`, with evidence references for the identified secondary organization and its approved login URL.

## Remediation procedure
No Salesforce record update is performed in the primary organization. Execute cross-organization routing:
1. Update ServiceNow ticket work notes explaining:
   - The user account was located in an alternate Salesforce organization (e.g. EMEA, ACE/GA, or ServiceMax).
   - The approved login URL corresponding to that organization (e.g. `https://bd2my.salesforce.com`).
   - The findings from the cross-organization verification.
2. Inform the user in the customer-facing update to access Salesforce using their dedicated organization's URL.
3. Reroute the ServiceNow ticket to the dedicated service desk or Salesforce support team responsible for that specific organization.
4. If the user requires access to the North America organization as well, advise them to raise a formal cross-org user provisioning request (RITM).

# HITL
- Approval required: No Salesforce metadata write is involved. Rerouting approval only if mandated by policy.
- Present to operator: Incident ID, user identity, identified organization, canonical login URL, target assignment group.
- Valid approval: Explicit confirmation to notify user and reroute incident to the dedicated regional support team.

# Verification
- Expected state: Work notes updated with cross-org findings and approved URL; incident reassigned to the target organization's support group.
- Checks: Re-query ServiceNow incident to confirm documentation and reassignment.

# Safety Rules
- Never invent evidence or org affiliations.
- Never directly provision an account in the primary org without an approved RITM.
- If a user is not found in ANY organization, never classify as LOGIN-1B; route to LOGIN-1 for HCL Service Desk RITM fulfillment.
