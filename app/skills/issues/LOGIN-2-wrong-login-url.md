---
issue_code: LOGIN-2
title: Wrong URL Used to Access Salesforce
domains:
  - LOGIN
version: 3
---

# Purpose
The caller cannot reach or sign in to Salesforce because they are using an unauthorized, invalid, or misdirected login URL. Applies when:
1. The incident mentions an unapproved or outdated login URL (e.g. `test.salesforce.com`, bookmarks, custom portals).
2. A Main Organization employee mistakenly attempts to log in via a secondary cross-org URL (e.g. `bd2my.salesforce.com`, `bdxga.my.salesforce.com`, or `bdsmx.my.salesforce.com`).

# Diagnosis
## Required evidence
- Caller or affected user identity (email, username, employee ID).
- The login URL or endpoint the user reports using (from incident description, work notes, or URL parameter).
- Verification of user account existence in the Main Salesforce Organization (`bdx.my.salesforce.com`).

## Investigation procedure
1. Extract the login URL from the incident text or intake parameters using `_extract_login_url`.
2. Compare the URL hostname against the approved enterprise login catalogue:
   - **NA (Primary / Main Org)**: `https://bdx.my.salesforce.com` (Domain: `bdx.my.salesforce.com`)
   - **EMEA**: `https://bd2my.salesforce.com` (Domain: `bd2my.salesforce.com`, alias `bd2.my.salesforce.com`)
   - **ACE/GA**: `https://bdxga.my.salesforce.com` (Domain: `bdxga.my.salesforce.com`)
   - **SMAX**: `https://bdsmx.my.salesforce.com` (Domain: `bdsmx.my.salesforce.com`)
3. **User Existence Check**:
   - Before concluding that the URL is the sole cause of failure, check whether the affected user's account exists in the **Main Salesforce Organization (`bdx.my.salesforce.com`)** using Salesforce MCP (`salesforce_user_search`).
   - **Scenario 1: User Exists in the Main Organization**:
     - Confirm the user's account exists in the Main Organization.
     - Conclude that the unapproved or misdirected URL is the primary root cause.
     - Confirm root cause **LOGIN-2**.
   - **Scenario 2: User Does Not Exist in the Main Organization**:
     - Confirm that the user's account could not be located in the Main Organization.
     - The wrong URL is not the only issue—the user lacks a provisioned account.
     - Route to **LOGIN-1**: Ticket is rerouted directly to HCL Service Desk for further handling (no RITM required from caller).

## Permitted diagnostic tools
- Salesforce URL validation (`salesforce_validate_url`).
- Salesforce user search (`salesforce_user_search`, `salesforce_get_user_details`).
- Neo4j Knowledge Graph enterprise org lookup (`get_approved_orgs`, `get_main_org`).
- ServiceNow incident details (read-only).

## Confirmation criteria
Confirmed only when:
- A concrete URL from the incident is recorded as evidence, AND
- The URL is unapproved OR belongs to a cross-org while the user account is in Main Org, AND
- The user account exists in the Main Salesforce Organization (`bdx.my.salesforce.com`).

# Resolution
## Required confirmed diagnosis
`status: confirmed`, `issue_code: LOGIN-2`, with evidence references for the URL comparison and Main Org user account existence.

## Remediation procedure
No Salesforce metadata mutation is required. Provide authoritative URL guidance and verify:
1. Update ServiceNow ticket work notes explaining that the user attempted to access Salesforce using an incorrect or misdirected URL.
2. Provide the official primary enterprise login URL: **`https://bdx.my.salesforce.com`**.
3. Instruct the user to delete any obsolete bookmarks, cached shortcuts, or regional links, and authenticate using the provided URL.
4. Ask the user to retry accessing Salesforce using the provided URL and confirm whether the issue is resolved.

# HITL
- Approval required: No Salesforce metadata write is required. Routing guidance to user only.
- Present to operator: Incident ID, invalid/misdirected URL used, user account details in Main Org, recommended canonical URL (`https://bdx.my.salesforce.com`).
- Valid approval: Explicit confirmation to communicate canonical login URL to requester.

# Verification
- Expected state: Correct Main Org login URL documented in incident work note and communicated to caller.
- Verification procedure:
  1. The **Verification Agent** queries user access after communicating the canonical URL.
  2. If the user successfully accesses Salesforce via `https://bdx.my.salesforce.com`, close incident as resolved.
  3. If the user still encounters authentication failure after using the canonical URL, the Verification Agent re-evaluates user gateway attributes (e.g., account deactivation under LOGIN-3 or Federation ID mismatch under LOGIN-4/LOGIN-6).

# Safety Rules
- Never assume a URL is wrong without extracting a concrete URL from the ticket narrative.
- Always verify user account existence before concluding the wrong URL is the sole blocker.
- If the user does not exist in the Main Organization, do not simply provide a login URL—redirect to the RITM provisioning process.
