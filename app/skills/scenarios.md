---
title: Investigation Scenarios — Symptom & Classification Catalog
version: 3
purpose: Domain classification and symptom matching (Excludes resolution/remediation steps)
---

# Purpose
This catalog defines the symptom manifestations, error patterns, and environmental context for all supported incident scenarios across the four Salesforce support domains: **LOGIN**, **OBJECT**, **RECORD**, and **APPLICATION**.

> [!NOTE]
> This skill catalog is used during **Triage & Classification**. Remediation and resolution procedures are strictly separated and reside in the downstream issue-specific resolution skills.

---

# 1. LOGIN Domain Scenarios
Symptom profile: The user is unable to establish an authenticated session in Salesforce, encounters single sign-on (SSO) failures, is blocked by account status, uses incorrect entry points, or fails mobile app authentication.

| Issue Code | Scenario | Symptom Manifestation & Error Patterns | Prerequisites & Contextual Indicators |
| :--- | :--- | :--- | :--- |
| **LOGIN-1** | User Account not available | User reports inability to log in; user does not exist in the primary Salesforce org (SFDC NA); may belong to regional/subsidiary orgs. | New user onboarding, contractor, or user in EMEA / GA / ServiceMax / RIM orgs. |
| **LOGIN-2** | Using wrong URL address to access salesforce system | User redirected to generic login page, commercial portal, or sandbox rather than the company's branded custom domain (e.g. `company.my.salesforce.com`). | User accessing via outdated bookmark, external link, or non-NA org URL. |
| **LOGIN-3** | User account got deactivated | User receives "Your account has been deactivated" or inactive user error upon login; user is active in HR systems but marked inactive in Salesforce. | Recent leave of absence, automated deactivation by Mulesoft/Workday integration, or manual Delegated Admin deactivation. |
| **LOGIN-4** | User Federation ID not available | SAML / SSO login fails with identity provider errors (Okta, Azure AD, Ping); IdP sends assertion but Salesforce cannot match FederationIdentifier. | Single Sign-On users; Employee ID not mapped or blank in Salesforce User record. |
| **LOGIN-5** | User Federation ID suspended | SSO login blocked; error indicates federated identity is suspended due to security lockout or extended inactivity. | Inactive for 60-90+ days; security suspension flag active in identity system. |
| **LOGIN-6** | User Federation ID not synced with Azure system (Re-hire process) | Re-hired employee receives authentication failure; Azure AD creates a new object/employee ID while Salesforce retains old credentials. | Re-hired staff; mismatch between Azure AD user principal and Salesforce FederationIdentifier. |
| **LOGIN-7** | External user Federation ID is not synced with CIAM system | External partner, vendor, or customer portal user fails authentication via Customer Identity & Access Management (CIAM). | CIAM portal login; external user record in SFDC NA out of sync with CIAM ID. |
| **LOGIN-8** | User not able to login using Salesforce Mobile app | Authentication fails specifically on iOS/Android Salesforce mobile client while desktop login may or may not work. | Mobile app configuration, custom domain setup in mobile client, MDM/MAM device policies. |
| **LOGIN-9** | User not able to get email while closing work order | User encounters notification/email delivery failure upon closing field service work orders; email verification incomplete. | Unverified email address on User record; CIAM Federation sync failure. |

---

# 2. OBJECT Domain Scenarios
Symptom profile: The user can log into Salesforce normally, but cannot perform Create, Read, Edit, or Delete (CRUD) actions on a specific object type, cannot view specific fields (FLS), or is blocked by country/object wizards.

| Issue Code | Scenario | Symptom Manifestation & Error Patterns | Prerequisites & Contextual Indicators |
| :--- | :--- | :--- | :--- |
| **OBJECT-1** | User not able to access Wizard app | User cannot launch or complete the custom country/product Wizard application; wizard fails to load target data. | User contact record lacks `Wizard Country` or localized configuration. |
| **OBJECT-2** | User cannot edit/delete records of specific object or access field | "Insufficient Privileges" error when attempting to edit/delete records of an object (e.g., Account, Contact, Opportunity); or specific fields are hidden/read-only. | Profile or Permission Set missing ObjectPermissions (Read/Create/Edit/Delete) or FieldPermissions (FLS); often accompanied by a comparison with a working peer (Mirror User). |
| **OBJECT-3** | Users cannot access Product Search Object | Product Search tab or object is inaccessible or throws access denied when searching product catalog. | User contact record missing `Wizard Country` population required for catalog filtering. |

---

# 3. RECORD Domain Scenarios
Symptom profile: The user has general access to the object, but is blocked from viewing or editing a **specific individual record**, report, or dashboard due to ownership, sharing rules, public groups, or folder permissions.

| Issue Code | Scenario | Symptom Manifestation & Error Patterns | Prerequisites & Contextual Indicators |
| :--- | :--- | :--- | :--- |
| **RECORD-1** | Report / Dashboard access issue | User cannot open, view, or refresh a specific report or dashboard ("Report not found" or "Insufficient privileges on report"). | Underlying object access missing, or the Report/Dashboard Folder has not been shared with user's role or public group. |
| **RECORD-2** | User unable to access to Opportunity / Case | User cannot view or edit a specific Opportunity or Case record that other team members can access. | Organization-Wide Defaults (OWD) are Private; record not owned by user; missing public group membership, sharing rule, or manual share. |
| **RECORD-3** | User unable to access a record in salesforce | User receives insufficient privileges error on a specific Record ID; `UserRecordAccess` returns `HasReadAccess = False`. | Record ownership mismatch, queue/group membership missing, territory or team assignment missing. |

---

# 4. APPLICATION Domain Scenarios
Symptom profile: User is authenticated and has Salesforce access, but is blocked from integrated connected apps, AppExchange packages, contract lifecycle management, or external partner communities.

| Issue Code | Scenario | Symptom Manifestation & Error Patterns | Prerequisites & Contextual Indicators |
| :--- | :--- | :--- | :--- |
| **APPLICATION-1**| User unable to access CC360 App | Access denied or missing navigation tabs for Customer Care 360 (CC360) community portal. | Missing community portal permission set: `CC360 Community User`. |
| **APPLICATION-2**| User unable to access Pharm system App | Access denied when opening Pharmacy System (Pharm) application or portal. | Missing community portal permission set: `Cmty-PS Community User`. |
| **APPLICATION-3**| User not able to access Conga App | Inability to access Conga CLM (Contract Lifecycle Management), create contracts, access Apttus, or connect via X-Author Excel plugin. | User missing from Conga package, `Salesforce CRM Content User` disabled, Apttus permission sets unassigned, or missing BU Public Group. |
| **APPLICATION-4**| Showpad access issue | Showpad collateral app fails to load inside Salesforce; authentication or license mapping error between Salesforce and Showpad. | Missing Showpad package license or connected app permissions. |
