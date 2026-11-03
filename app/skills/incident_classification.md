---
title: Incident Classification and Semantic Identity Resolution Skill
version: 5
purpose: Contextual triage, domain classification, affected user resolution, mirror user extraction, and enterprise multi-org URL/identity verification
---

# Purpose
This skill guides the Triage Agent in:
1. Contextually understanding the natural language narrative of ServiceNow support incidents.
2. Classifying incidents into one of four investigation domains: **LOGIN**, **OBJECT**, **RECORD**, or **APPLICATION** based on symptom semantics (without premature remediation).
3. Dynamically identifying the **Affected User** based on sentence context and narrative roles, rather than assuming the ticket caller is the affected party.
4. Dynamically extracting any **Mirror User** (benchmark/comparison peer) referenced in the ticket to enable differential access analysis.
5. Dynamically extracting any **Login URL / Endpoint** cited in the narrative to anchor Swimlane 1 ("Wrong Login Url") and cross-organization user verification.

---

# 1. Semantic Domain Classification

Analyze the symptom reported by the user, the stage of their interaction with Salesforce, and the scope of the restriction.

### A. LOGIN Domain
- **Core Semantic Question**: Is the user unable to authenticate or establish an active Salesforce session?
- **Symptom Scope**: System-wide access block. The user cannot get past the login screen, SSO portal, or authentication barrier.
- **Key Indicators**:
  - SAML / Okta / Azure AD / CIAM identity provider errors.
  - Federation ID mismatches or missing federation values.
  - Deactivated or locked out user accounts.
  - Accessing via wrong or outdated custom URLs / non-production domains.
  - Cross-organization misdirection (Main Org employee using regional URL or vice-versa).
  - Salesforce Mobile App authentication failures.

### B. OBJECT Domain
- **Core Semantic Question**: Is the user logged in, but blocked from CRUD operations on an entire object type or specific fields?
- **Symptom Scope**: Schema/Object-wide restriction. The user can view Salesforce, but cannot create, read, edit, or delete records of a given object (e.g. Account, Contact, Opportunity) or cannot see specific fields.
- **Key Indicators**:
  - "Insufficient Privileges" when clicking Edit, Delete, or New on an object tab.
  - Field-Level Security (FLS) hiding fields or rendering them read-only.
  - Country-specific Wizard app blocks or Product Search object limitations.
  - Typically accompanied by requests to check Profiles or Permission Sets.

### C. RECORD Domain
- **Core Semantic Question**: Can the user generally access the object, but is blocked from a **specific individual record**, report, or dashboard?
- **Symptom Scope**: Row-level / instance-level restriction. The user has object permissions, but this specific record instance (by Record ID or specific name) is inaccessible.
- **Key Indicators**:
  - Access denied to a specific Opportunity, Case, or custom record ID.
  - Report or Dashboard visibility errors where folder sharing or report owner access is restricted.
  - Driven by Organization-Wide Defaults (OWD), Role Hierarchy, Sharing Rules, Public Groups, Queues, or manual shares.

### D. APPLICATION Domain
- **Core Semantic Question**: Is the issue isolated to a third-party package, connected app, or dedicated portal?
- **Symptom Scope**: Application-specific subsystem.
- **Key Indicators**:
  - Customer Care 360 (CC360) community portal.
  - Pharmacy System (Pharm) portal access.
  - Conga CLM / Apttus contract lifecycle management or X-Author Excel add-in.
  - Showpad collateral management.

---

# 2. Dynamic Semantic Identity Resolution

Support tickets are written by humans using diverse narrative styles. The agent must parse the semantic roles of all mentioned entities rather than relying on brittle pattern matching.

### Narrative Roles to Distinguish:
1. **Reporter / Caller**:
   - The individual who logged the ticket in ServiceNow (manager, IT helpdesk analyst, admin, or the user themself).
   - *Example cues*: "Logged by...", "Manager reaching out for...", "Help desk ticket for...", or default caller metadata.

2. **Affected User (The Subject)**:
   - The actual human being whose Salesforce access is broken or who is experiencing the reported symptom.
   - *Resolution Hierarchy*:
     - **Priority 1 (Contextual Narrative)**: When the description or summary clearly indicates that someone other than the caller is having the problem (e.g. "My team member Jane Doe cannot sign in", "Please check permissions for bob@company.com", "Ticket raised for Sarah Connor who is locked out").
     - **Priority 2 (`on_behalf_of` Field)**: When the ticket includes a structured `on_behalf_of` or `requested_for` field identifying the intended recipient.
     - **Priority 3 (Caller)**: When the narrative indicates self-reporting ("I cannot log in", "My account is blocked") or no alternative subject is identified.

3. **Mirror User (The Benchmark)**:
   - A peer or colleague whose access is working correctly, cited by the requester as an example of expected permissions.
   - *Contextual Understanding*:
     - "Working fine for Alice (alice@company.com)"
     - "Please match access with Bob Smith"
     - "Charlie has the same job role and can edit these accounts"
     - "Compare with colleague David"
   - *Crucial Rule*: A mirror user is **NEVER** the affected user. They represent the healthy baseline state.

---

# 3. Dynamic Multi-Org Login URL & User Existence Architecture

In enterprise Salesforce architectures, users access different production organizations depending on region and function. 

### Approved Enterprise Organizations and Canonical URLs:
1. **North America (NA) - Primary / Main Org**: `https://bdx.my.salesforce.com` (Domain: `bdx.my.salesforce.com`)
2. **Europe, Middle East & Africa (EMEA)**: `https://bd2my.salesforce.com` (Domain: `bd2my.salesforce.com`, alias: `bd2.my.salesforce.com`)
3. **Asia Central East / Greater Asia (ACE/GA)**: `https://bdxga.my.salesforce.com` (Domain: `bdxga.my.salesforce.com`)
4. **ServiceMax (SMAX)**: `https://bdsmx.my.salesforce.com` (Domain: `bdsmx.my.salesforce.com`)

### Cross-Organization Decision Tree:
```
                                 [Login URL Evaluated]
                                           │
         ┌─────────────────────────────────┼──────────────────────────────────┐
         ▼                                 ▼                                  ▼
[1. Unapproved URL]             [2. Main Org URL (bdx)]            [3. Cross-Org URL (bd2/bdxga/bdsmx)]
         │                                 │                                  │
Check User in Main Org            Check User in Main Org             Check User in THAT Cross-Org
         │                                 │                                  │
 ┌───────┴───────┐                 ┌───────┴───────┐                  ┌───────┴───────┐
 │               │                 │               │                  │               │
 ▼               ▼                 ▼               ▼                  ▼               ▼
User Exists:    User Missing:     User Exists:    User Missing:      User Exists:    User Missing:
Main cause is   No account        Right URL.      Check other orgs.  Belongs here.   CHECK MAIN ORG!
wrong URL.      anyway.           Proceed with    If in EMEA/ACE ➔   Reroute to      If in Main Org ➔
Provide bdx     Advise RITM       deep login      give that URL &    regional        "You are Main Org,
URL & verify    via HCL           investigation   reroute.           team.           use bdx URL!"
via Verifier.   Service Desk.     (Active/FedID). If in none ➔ RITM.                 If in other ➔ give URL
                                                                                     If in none ➔ RITM.
```

### Universal Rule for "User Not Found / None" Cases:
Across all paths, if an affected user cannot be located in the required organization or in any registered corporate organization:
1. Document the list of organizations searched in the ServiceNow work notes.
2. Inform the user that an active account does not exist and a formal **Salesforce User Provisioning Request (RITM)** must be raised.
3. Reroute the ticket to the **HCL Service Desk** for fulfillment.

---

# 4. Canonical Login Knowledge Graph Swimlanes (12 Swimlanes)

1. **Wrong Login Url**: Ingests Triage Result (`Affected User`, `Division / LOB`, `Mirror User`, `Login URL`). Evaluates `Login URLs Provided?` and validates against approved enterprise orgs (`bdx`, `bd2my`, `bdxga`, `bdsmx`).
   - If unapproved: checks user in Main Org. If user exists ➔ confirms **LOGIN-2**; if missing ➔ routes to **LOGIN-1** (RITM via HCL Service Desk).
   - If cross-org: checks user in secondary org and Main Org. If Main Org user used cross-org link ➔ confirms **LOGIN-2**; if user exists in regional org ➔ confirms **LOGIN-1B** (regional scope).
2. **User not found in any org**: Searches primary org (`bdx.my.salesforce.com`). If missing, queries secondary orgs (EMEA, ACE/GA, SMAX). Confirms **LOGIN-1** (User not found) if absent from all orgs; advises RITM and reroutes to HCL Service Desk.
3. **User found in another org**: Confirms **LOGIN-1B** if user account is located in an alternate corporate org (EMEA `bd2my`, ACE/GA `bdxga`, or SMAX `bdsmx`). Documents approved regional URL and reroutes to regional team.
4. **User Deactivation**: Checks `IsActive`. If `False`, inspects Setup Audit Trail. Confirms **LOGIN-3** if deactivated by Delegated Administrator (DA); escalates to **LOGIN-3-ESCALATE** if deactivated by automated integration (Mulesoft/Workday).
5. **Federation ID Missing**: Fetches Mirror User and performs `Compare EmpId and Federation Id of Mirror user`. Evaluates `Is same? (Internal)`:
   - If `YES` (Internal archetype where EmpId == FedId): Checks `Federation ID Blank?` -> Confirms **LOGIN-4** if missing.
   - If `NO` (External / CIAM archetype): Jumps directly across Swimlanes 6-8 into Swimlane 9 (`CIAM Synchronization External`).
6. **Federation ID Suspended**: Evaluates `Federation ID has Suspended value?`. Confirms **LOGIN-5** if user is suspended or frozen in Okta/IdP.
7. **Azure Synchronization Internal**: Evaluates `Federation ID matches Emp ID? (Workday)`. Strictly compares Salesforce `FederationIdentifier` against authoritative Workday `EmployeeNumber`. Confirms **LOGIN-6** on mismatch.
8. **Mobile Login Setup Issue**: Evaluates `Has Description contain "Mobile Login Issue" Symptom?`. Confirms **LOGIN-8** if mobile client configuration is reported; otherwise branches `NO` to Swimlane 12 (`Out Of Scope`).
9. **CIAM Synchronization External**: Evaluates `Federation ID matches Emp ID? (CIAM)`. Confirms **LOGIN-7** (`CIAM Synthetic Identity mapping issue`) on mismatch; advances `YES` to Swimlane 10.
10. **Email Not Verified**: Evaluates `Is Email Verified?`. If `YES`, routes directly to **Out Of Scope**. If `NO`, evaluates `Has Description contain "Work Order Email Not Received" Symptom?`:
    - If `NO` -> Confirms **LOGIN-10** (`Confirmed: Email not verified`).
    - If `YES` -> Advances to Swimlane 11.
11. **Work Order Email Issue**: Confirms **LOGIN-9** (`Confirmed: Work Order Email Issue`).
12. **Out Of scope**: Red terminal boundary node for tickets that do not match canonical login issue patterns.

---

# 5. Ambiguity & Clarification Handling
- If a ticket says "Can't access Salesforce" or "System down" without specifying whether login failed or an object/record is missing:
  - Classify tentatively as `LOGIN` (the standard entry barrier).
  - Mark `is_ambiguous = True`.
  - Trigger clarification / escalation flow rather than guessing specific diagnostic causes.
- If multiple candidate users are mentioned without clear role attribution:
  - Flag `ambiguous_identity` and escalate for confirmation.
