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

# 3. Ambiguity & Clarification Handling
- If a ticket says "Can't access Salesforce" or "System down" without specifying whether login failed or an object/record is missing:
  - Classify tentatively as `LOGIN` (the standard entry barrier).
  - Mark `is_ambiguous = True`.
  - Trigger clarification / escalation flow rather than guessing specific diagnostic causes.
- If multiple candidate users are mentioned without clear role attribution:
  - Flag `ambiguous_identity` and escalate for confirmation.
