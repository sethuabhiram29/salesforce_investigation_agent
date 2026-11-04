---
issue_code: LOGIN-5
title: FederationIdentifier Has Been Replaced With a Suspended/Frozen/Invalid Value
domains:
  - LOGIN
version: 2
user_type: Internal
condition: "User exists in NA Org AND IsActive = True AND Internal User AND FederationIdentifier contains suspended/frozen"
---

# Purpose
An active internal user cannot authenticate via Single Sign-On because their Salesforce `FederationIdentifier` has been replaced with a suspended, frozen, or invalid value (e.g., automated inactivity deactivation marker or identity freeze in Okta/IdP). Direct modification by the automated agent is prohibited; the user must be directed to submit a Manage User RITM in ServiceNow for authorized correction.

# Diagnosis

## Required Evidence
- User exists in the primary NA Salesforce organization.
- `User.IsActive == True`.
- User confirmed as an Internal User.
- `User.FederationIdentifier` contains a value indicating suspension (e.g. substring `"suspended"`, `"frozen"`, or invalid suspension token).
- `User.EmployeeNumber` is recorded.

## Investigation Procedure
1. Retrieve incident and caller details.
2. Search user in NA Org using Salesforce SOSL Search (`salesforce_user_search` / `salesforce_execute_sosl`).
3. If user not found in NA, follow Login-1A/Login-1B process.
4. Verify user account is active (`User.IsActive == True`).
5. Retrieve `EmployeeNumber` and `FederationIdentifier` from User record.
6. Verify user is an Internal User.
7. Validate whether `FederationIdentifier` contains a suspended or frozen value.
8. If suspended value is identified, classify as Federation ID Suspended issue.
9. Update incident work notes with findings.
10. Inform user to raise Manage User RITM for `FederationIdentifier` correction.
11. Resolve or close incident as per support process.

## Permitted Diagnostic Tools
- `salesforce_user_search`: Search user by username, email, or employee number.
- `salesforce_get_user_details`: Retrieve full user record.
- ServiceNow: Retrieve incident and user details (read-only).

## Confirmation Criteria
Confirmed only when:
- User is uniquely resolved in NA Org.
- `User.IsActive == True`.
- User confirmed as an Internal User.
- `User.FederationIdentifier` is confirmed to contain `"suspended"` or `"frozen"`.

## Alternative Explanations
- If `FederationIdentifier` is null or empty: Route to LOGIN-4.
- If `FederationIdentifier` is populated but does not match `EmployeeNumber` without suspension markers: Route to LOGIN-6.
- If `User.IsActive == False`: Route to LOGIN-3 / LOGIN-3A.

# Resolution

## Required Confirmed Diagnosis
- `issue_code: LOGIN-5`
- `status: confirmed`

## Remediation Procedure
Direct Salesforce mutation of suspended Federation IDs is restricted:
1. Update ServiceNow incident work notes detailing:
   - Observed suspended/frozen value in `User.FederationIdentifier`.
   - Verified `EmployeeNumber`.
   - Requirement for authorized identity remediation.
2. Formulate user guidance informing the user to raise a **Manage User RITM** in ServiceNow to correct their `FederationIdentifier` back to their corporate Employee Number.
3. Transmit notification to the user and resolve/close the incident as per standard support process.

## Preconditions and Permitted Operations
- Permitted: ServiceNow work notes update, user communication with Manage User RITM guidance, incident closure.
- Prohibited: Directly modifying `User.FederationIdentifier` in Salesforce without an approved Manage User RITM.

# HITL
- Present to operator: Incident ID, user details, observed suspended `FederationIdentifier`, `EmployeeNumber`, Manage User RITM guidance.
- Valid approval: Explicit confirmation to deliver Manage User RITM instructions and resolve ticket.

# Verification
- Expected state: ServiceNow work notes and user communication contain complete Manage User RITM guidance for FederationIdentifier correction.
- Checks: Re-query incident to confirm delivery of RITM instructions.
