---
issue_code: LOGIN-6
title: FederationIdentifier Does Not Match Identity Mapping Maintained for Internal User
domains:
  - LOGIN
version: 2
user_type: Internal
condition: "User exists in NA Org AND IsActive = True AND Internal User AND FederationIdentifier IS NOT NULL AND FederationIdentifier != EmployeeNumber"
---

# Purpose
An active internal employee cannot sign in via Single Sign-On because their Salesforce `FederationIdentifier` is populated but does not match the authoritative corporate identity mapping maintained in Azure AD / Workday (e.g., following a re-hire process, employee number change, or Azure user principal synchronization mismatch). The Azure Team must be engaged for validation, and the Salesforce record updated upon confirmation.

# Diagnosis

## Required Evidence
- User exists in the primary NA Salesforce organization.
- `User.IsActive == True`.
- User confirmed as an Internal User.
- `User.FederationIdentifier` is NOT null and NOT empty.
- `User.FederationIdentifier != User.EmployeeNumber`.

## Investigation Procedure
1. Retrieve incident and caller details.
2. Search user in NA Org using Salesforce SOSL Search (`salesforce_user_search` / `salesforce_execute_sosl`).
3. If user not found in NA, follow Login-1A/Login-1B process.
4. Verify user account is active (`User.IsActive == True`).
5. Retrieve `EmployeeNumber` and `FederationIdentifier` from User record.
6. Verify user is an Internal User.
7. Compare `EmployeeNumber` and `FederationIdentifier`.
8. If `FederationIdentifier` is populated but does not match `EmployeeNumber`, classify as Federation ID synchronization issue.
9. Contact Azure Team to validate the `FederationIdentifier` currently mapped to the employee.
10. Compare Azure validation result with Salesforce value.
11. Update Salesforce `FederationIdentifier` if required (aligning to authoritative `EmployeeNumber` upon Azure confirmation).
12. Verify update completed successfully.
13. Update work notes and inform the user.

## Permitted Diagnostic Tools
- `salesforce_user_search`: Search user by username, email, or employee number.
- `salesforce_get_user_details`: Retrieve full user record.
- ServiceNow: Retrieve incident and user details (read-only).

## Confirmation Criteria
Confirmed only when:
- User is uniquely resolved in NA Org.
- `User.IsActive == True`.
- User confirmed as an Internal User.
- `User.FederationIdentifier` is populated.
- `User.FederationIdentifier != User.EmployeeNumber`.

## Alternative Explanations
- If `FederationIdentifier` is blank or null: Route to LOGIN-4.
- If `FederationIdentifier` contains suspended or frozen tokens: Route to LOGIN-5.
- If user is external and identifier is a CIAM UUID: Route to LOGIN-7.
- If `User.IsActive == False`: Route to LOGIN-3 / LOGIN-3A.

# Resolution

## Required Confirmed Diagnosis
- `issue_code: LOGIN-6`
- `status: confirmed`

## Remediation Procedure
1. Contact the Azure Team to validate the authoritative `FederationIdentifier` mapped to the employee in Azure AD / Workday.
2. Compare the Azure validation result with the Salesforce value.
3. Upon Azure team confirmation, formulate a change proposal to update Salesforce `User.FederationIdentifier` with the verified `EmployeeNumber`.
4. Submit for Human-in-the-Loop (HITL) approval.
5. Execute `salesforce_update_user(user_id, "FederationIdentifier", verified_employee_number)`.
6. Verify update completed successfully by re-querying Salesforce.
7. Update incident work notes with Azure alignment findings and inform the user.

## Preconditions and Permitted Operations
- Permitted: Engaging Azure team, updating `User.FederationIdentifier` to match confirmed `EmployeeNumber` post-approval, updating work notes.
- Prohibited: Writing an arbitrary or unconfirmed Federation ID; using email or username as Federation ID.

# HITL
- Present to operator: Incident ID, user details, current Salesforce `FederationIdentifier`, authoritative `EmployeeNumber`, Azure team confirmation status.
- Valid approval: Explicit confirmation to update Salesforce `FederationIdentifier` to match `EmployeeNumber`.

# Verification
- Expected state: `User.FederationIdentifier == EmployeeNumber` AND `User.IsActive == True`.
- Checks: Re-query Salesforce user record to confirm `FederationIdentifier` equals `EmployeeNumber`.
