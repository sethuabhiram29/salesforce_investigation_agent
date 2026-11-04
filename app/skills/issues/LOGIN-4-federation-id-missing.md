---
issue_code: LOGIN-4
title: FederationIdentifier is Blank or Null in Salesforce User Record
domains:
  - LOGIN
version: 1
user_type: Internal
condition: "User exists in NA Org AND IsActive = True AND Internal User AND FederationIdentifier IS NULL or Blank"
---

# Purpose
An active internal employee cannot sign in via Single Sign-On (Okta / Azure AD / Ping) because their Salesforce user record is missing a Federation ID (`FederationIdentifier` is blank or null). In a SAML SSO environment, the identity provider sends the assertion with the user's corporate Employee Number, which fails to match any Salesforce user record when `FederationIdentifier` is unpopulated.

# Diagnosis

## Required Evidence
- User exists in the primary NA Salesforce organization.
- `User.IsActive == True`.
- User is verified as an **Internal User** (determined through peer mirror user benchmark where `EmployeeNumber == FederationIdentifier` or `UserType == 'Standard'`).
- `User.FederationIdentifier` is `NULL` or blank string (`""`).
- `User.EmployeeNumber` is populated with the authoritative corporate Employee Number.

## Investigation Procedure
1. Retrieve incident and caller details.
2. Search user in NA Org using Salesforce SOSL Search (`salesforce_user_search` / `salesforce_execute_sosl`).
3. If user not found in NA, follow Login-1A/Login-1B process.
4. Retrieve User details including `EmployeeNumber` and `FederationIdentifier`.
5. Verify user is an Internal User. (If the user is Internal or not, verify through mirror user comparison: peer internal user has `EmployeeNumber` matching `FederationIdentifier` and `UserType == 'Standard'`).
6. Validate whether `FederationIdentifier` is blank or null.
7. If blank, update `FederationIdentifier` with `EmployeeNumber`.
8. Verify update completed successfully.
9. Update work notes with findings and actions performed.
10. Inform user and resolve incident.

## Permitted Diagnostic Tools
- `salesforce_user_search`: Search user by username, email, or employee number.
- `salesforce_get_user_details`: Retrieve full user record (`EmployeeNumber`, `FederationIdentifier`, `IsActive`, `UserType`).
- `salesforce_find_peer_mirror_user`: Retrieve peer mirror user to confirm internal employee identity archetype.

## Confirmation Criteria
Confirmed only when:
- User is uniquely resolved in NA Org.
- `User.IsActive == True`.
- User confirmed as an Internal User via mirror user benchmark.
- `User.FederationIdentifier` is observed as null or empty string.
- `User.EmployeeNumber` is available.

## Alternative Explanations
- If `FederationIdentifier` contains "suspended" or "frozen": Route to LOGIN-5.
- If `FederationIdentifier` is populated but does not match `EmployeeNumber`: Route to LOGIN-6 (Azure sync) or LOGIN-7 (CIAM external).
- If `User.IsActive == False`: Route to LOGIN-3 / LOGIN-3A.

# Resolution

## Required Confirmed Diagnosis
- `issue_code: LOGIN-4`
- `status: confirmed`

## Remediation Procedure
1. Propose updating `User.FederationIdentifier` strictly with the user's authoritative `EmployeeNumber` (never email address or username).
2. Submit the proposed update for Human-in-the-Loop (HITL) authorization.
3. Upon approval, execute `salesforce_update_user(user_id, "FederationIdentifier", employee_number)`.
4. Verify update completed successfully by re-querying Salesforce.
5. Update ServiceNow incident work notes detailing:
   - Prior state (`FederationIdentifier` was blank).
   - Authoritative `EmployeeNumber` applied.
   - Live verification outcome.
6. Inform user that `FederationIdentifier` has been synchronized with their Employee Number and resolve incident.

## Preconditions and Permitted Operations
- Permitted: Updating `User.FederationIdentifier` to match `User.EmployeeNumber`.
- Prohibited: Using email address or username as Federation ID; modifying any field other than `FederationIdentifier`.

# HITL
- Present to operator: Incident ID, User (`Username`, `Id`), authoritative `EmployeeNumber`, current `FederationIdentifier` (blank), proposed value (`EmployeeNumber`).
- Valid approval: Explicit confirmation to update `User.FederationIdentifier` with `EmployeeNumber`.

# Verification
- Expected state: `User.FederationIdentifier == EmployeeNumber` AND `User.IsActive == True`.
- Checks: Re-query live Salesforce user record and assert that `FederationIdentifier` exactly equals `EmployeeNumber`.

# Safety Rules
- Never invent evidence or user identifiers.
- Never populate FederationIdentifier with email address or username; strictly use authoritative EmployeeNumber.
- Always require HITL approval before mutating Salesforce user records.
