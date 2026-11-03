---
issue_code: LOGIN-2
title: Wrong URL Used to Access Salesforce
domains:
  - LOGIN
version: 2
---

# Purpose
The caller cannot reach or sign in to Salesforce because they are using an unauthorized, invalid, or obsolete login URL that does not point to the primary North America production org (`bdx.my.salesforce.com`) or any approved enterprise regional instance. Applies when the incident mentions a custom URL, outdated bookmark, sandbox endpoint, or "page not found / wrong login page" symptom.

# Diagnosis
## Required evidence
- Caller identity (email / username / Federation ID).
- The login URL or endpoint the user reports using (from incident description, work notes, or URL parameter).

## Investigation procedure
1. Retrieve the incident and caller details.
2. Extract the login URL from the incident text or intake parameters using `_extract_login_url`.
3. Compare the URL hostname against the approved enterprise login catalogue:
   - **NA (Primary / Main Org)**: `https://bdx.my.salesforce.com` (Domain: `bdx.my.salesforce.com`)
   - **EMEA**: `https://bd2my.salesforce.com` (Domain: `bd2my.salesforce.com`, alias `bd2.my.salesforce.com`)
   - **ACE/GA**: `https://bdxga.my.salesforce.com` (Domain: `bdxga.my.salesforce.com`)
   - **SMAX**: `https://bdsmx.my.salesforce.com` (Domain: `bdsmx.my.salesforce.com`)
4. Record the URL, the comparison result, and the approved enterprise catalogue as evidence.

## Permitted diagnostic tools
- Salesforce URL validation (`salesforce_validate_url`).
- Neo4j Knowledge Graph enterprise org lookup (`get_approved_orgs`).
- ServiceNow incident details (read-only).

## Confirmation criteria
Confirmed only when:
- A concrete URL from the incident is recorded as evidence, AND
- The URL hostname does NOT match `bdx.my.salesforce.com`, `bd2my.salesforce.com`, `bdxga.my.salesforce.com`, or `bdsmx.my.salesforce.com`.

## Alternative explanations
- URL is approved: This skill does NOT apply. The decision graph automatically traverses `ON_YES` to Swimlane 2 (`Search User in main org`).
- User exists in another approved enterprise org (e.g. EMEA or ACE/GA): Evaluated in Swimlane 3 (**LOGIN-1B**).

# Resolution
## Required confirmed diagnosis
`status: confirmed`, `issue_code: LOGIN-2`, with the evidence reference for the URL comparison.

## Remediation procedure
No Salesforce metadata change required. Route guidance to the user and Help Desk:
1. Provide the user with the correct primary enterprise login URL: `https://bdx.my.salesforce.com` (or regional URL if assigned to EMEA/ACE/SMAX).
2. Instruct the user to delete any obsolete bookmarks or cached browser shortcuts.
3. Add a work note documenting the invalid URL used and the recommended canonical URL.
4. Reassign or resolve the incident per Help Desk standard operating procedure.

# HITL
- Approval required: No Salesforce metadata write is required. Routing guidance to user only.
- Present to operator: Incident ID, invalid URL used, matched approved enterprise catalogue, recommended URL.
- Valid approval: Explicit confirmation to notify user with canonical login URL.

# Verification
- Expected state: Guidance documented in incident work note and communicated to caller.
- Checks: Confirm caller is provided official enterprise URL `https://bdx.my.salesforce.com`.
- Failure handling: If user reports ongoing issues after using canonical URL, re-open for credential/SSO investigation.

# Safety Rules
- Never invent evidence or URLs.
- Never assume a URL is wrong without extracting a concrete URL from the ticket.
- Verify whether the user actually belongs to an alternate regional org (EMEA, ACE/GA, SMAX) before redirecting to NA.
