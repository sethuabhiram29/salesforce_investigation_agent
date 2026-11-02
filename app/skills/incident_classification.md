---
title: Incident Classification and Semantic Identity Resolution Skill
version: 3
purpose: Contextual triage, domain classification, affected user resolution, and mirror user extraction
---

# Purpose
This skill guides the Triage Agent in:
1. Contextually understanding the natural language narrative of ServiceNow support incidents.
2. Classifying incidents into one of four investigation domains: **LOGIN**, **OBJECT**, **RECORD**, or **APPLICATION** based on symptom semantics (without premature remediation).
3. Dynamically identifying the **Affected User** based on sentence context and narrative roles, rather than assuming the ticket caller is the affected party.
4. Dynamically extracting any **Mirror User** (benchmark/comparison peer) referenced in the ticket to enable differential access analysis.

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

# 3. Dynamic Login URL & Endpoint Extraction

In enterprise Salesforce architectures, login entry points differ depending on whether the user is authenticating against production, a custom MyDomain URL, a developer/UAT sandbox, or a partner community. 

The Knowledge Graph decision tree anchors on the **Login URL** in Swimlane 1 ("Wrong Login Url") as part of the initial Prompt Result:

```
[Prompt Result]
  - Affected User
  - Problem / Details
  - Mirror User
  - Login URL
       │
       ▼
[Login URL Provided?] ───(Yes)───► [Validate Login URL] ───(Approved URL?)
       │                                                         │
      (No)                                                     (No) ──► Confirmed: Wrong Salesforce URL (LOGIN-2)
       │                                                         │
       └────────────────────────► (Go to Swimlane 2) ◄──────────(Yes)
```

### Extraction Guidelines for Triage Agent:
1. **Detection Patterns**:
   - Explicit web URLs: `http://...`, `https://...`
   - Custom MyDomain URLs: `*.my.salesforce.com`, `*.lightning.force.com`
   - Sandbox environments: `test.salesforce.com`, `*.sandbox.my.salesforce.com`
   - Standard portals: `login.salesforce.com`
2. **Contextual Narrative Extraction**:
   - Identify when a user cites the exact URL they are browsing to:
     - *"User cannot sign in at https://acme--test.sandbox.my.salesforce.com"* ➔ Extracted Login URL: `https://acme--test.sandbox.my.salesforce.com`
     - *"Navigating to test.salesforce.com gives invalid credentials"* ➔ Extracted Login URL: `https://test.salesforce.com`
     - *"User is using bookmarked URL https://oldportal.my.salesforce.com"* ➔ Extracted Login URL: `https://oldportal.my.salesforce.com`
### Approved Regional Login URLs & Catalogue:
The enterprise validates login URLs against approved regional pod instances and corporate production MyDomains:
- `https://indXX.salesforce.com` (India regional pods, e.g. `ind01.salesforce.com`, `indXX.salesforce.com`)
- `https://jpnXX.salesforce.com` (Japan regional pods, e.g. `jpn01.salesforce.com`, `jpnXX.salesforce.com`)
- `https://gbrXX.salesforce.com` (Great Britain regional pods, e.g. `gbr01.salesforce.com`, `gbrXX.salesforce.com`)
- `https://ausXX.salesforce.com` (Australia regional pods, e.g. `aus01.salesforce.com`, `ausXX.salesforce.com`)
- `https://deuXX.salesforce.com` (Germany regional pods, e.g. `deu01.salesforce.com`, `deuXX.salesforce.com`)
- `https://fraXX.salesforce.com` (France regional pods, e.g. `fra01.salesforce.com`, `fraXX.salesforce.com`)
- Corporate MyDomain production instances: `*.my.salesforce.com`
- Standard corporate entry: `https://login.salesforce.com`

If the incident narrative cites an approved regional URL or corporate MyDomain, `Approved URL?` evaluates to **`YES`** and diagnosis proceeds to Swimlane 2 (User presence in main org).
If an unapproved URL is cited (such as `test.salesforce.com` or an invalid pod), `Approved URL?` evaluates to **`NO`** and locks root cause **`LOGIN-2 (Wrong Salesforce URL)`**.

### Absence of Custom URL:
- If the ticket does not mention any explicit login URL, hostname, or website link, assign `login_url = None`.
- The diagnosis engine evaluates `Login URLs Provided?` as **`NO`** and traverses directly to Swimlane 2 (`Search user in main org`).

---

# 4. Canonical Login Knowledge Graph Swimlanes (12 Swimlanes)

The Knowledge Graph decomposes all login investigations into 12 structured swimlanes:
1. **Wrong Login Url**: Ingests Triage Result (`Affected User`, `Division / LOB`, `Mirror User`, `Login URL`). Evaluates `Login URLs Provided?` and validates against approved regional catalogue (`indXX`, `jpnXX`, `gbrXX`, `ausXX`, `deuXX`, `fraXX`). Confirms **LOGIN-2** on failure.
2. **User not found in any org**: Searches primary org. If missing, queries secondary orgs (EMEA, GA, ServiceMax, RIM). Confirms **LOGIN-1** (User not found).
3. **User found in another org**: Confirms **LOGIN-1B** if user account is located in an alternate corporate org.
4. **User Deactivation**: Checks `IsActive`. If `False`, inspects Setup Audit Trail. Confirms **LOGIN-3** if deactivated by Delegated Administrator (DA); escalates to **LOGIN-3-ESCALATE** (`If any other deactivation like maxwell need manual review`) if deactivated by Maxwell/automated integration.
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
