---
issue_code: LOGIN-7
title: FederationIdentifier in Salesforce Does Not Match FederationIdentifier Maintained in CIAM
domains:
  - LOGIN
version: 2
user_type: External
condition: "User exists in NA Org AND IsActive = True AND External User AND FederationIdentifier requires CIAM validation"
---

# Purpose
An external user (e.g. customer portal, partner, or community user) cannot authenticate into Salesforce because their `FederationIdentifier` does not match the identity record maintained in the Customer Identity and Access Management (CIAM) system. The CIAM Team must be engaged to validate the authoritative UUID, and the Salesforce user record updated upon confirmation.

# Diagnosis

## Required Evidence
- User exists in the primary NA Salesforce organization.
- `User.IsActive == True`.
- User confirmed as an **External User** (e.g. `UserType` is community/portal or `FederationIdentifier` follows CIAM UUID format).
- `User.FederationIdentifier` requires CIAM synchronization.

## Investigation Procedure
1. Retrieve incident and caller details.
2. Search user in NA Org using Salesforce SOSL Search (`salesforce_user_search` / `salesforce_execute_sosl`).
3. If user not found in NA, follow Login-1A/Login-1B process.
4. Verify user account is active (`User.IsActive == True`).
5. Retrieve `EmployeeNumber` and `FederationIdentifier` from Salesforce User record.
6. Determine user type.
7. If `FederationIdentifier` does not match `EmployeeNumber` and `FederationIdentifier` follows CIAM UUID format, classify user as External User.
8. Contact CIAM Team to validate the `FederationIdentifier` associated with the user.
9. Compare CIAM `FederationIdentifier` with Salesforce `FederationIdentifier`.
10. Update Salesforce `FederationIdentifier` if required.
11. Update work notes with findings and actions performed.
12. Inform user and resolve incident.

## Permitted Diagnostic Tools
- `salesforce_user_search`: Search user by username or email.
- `salesforce_get_user_details`: Retrieve full user record (`UserType`, `FederationIdentifier`, `ContactId`).
- ServiceNow: Retrieve incident and user details (read-only).

## Confirmation Criteria
Confirmed only when:
- User is uniquely resolved in NA Org.
- `User.IsActive == True`.
- User confirmed as an External User.
- Salesforce `FederationIdentifier` is confirmed to require CIAM synchronization.

## Alternative Explanations
- If user is an Internal Employee: Route to LOGIN-4 (missing) or LOGIN-6 (Azure mismatch).
- If `User.IsActive == False`: Route to LOGIN-3 / LOGIN-3A.

# Resolution

## Required Confirmed Diagnosis
- `issue_code: LOGIN-7`
- `status: confirmed`

## Remediation Procedure
1. Engage the CIAM Team point of contact to retrieve the authoritative external UUID mapping.
2. Compare CIAM `FederationIdentifier` with Salesforce `FederationIdentifier`.
3. Upon confirmation from the CIAM Team, formulate proposal to update Salesforce `User.FederationIdentifier` to the validated CIAM UUID.
4. Submit for Human-in-the-Loop (HITL) approval.
5. Execute `salesforce_update_user(user_id, "FederationIdentifier", ciam_uuid)`.
6. Verify update completed successfully by re-querying Salesforce.
7. Update incident work notes with findings and actions performed, inform the user, and resolve incident.

## Preconditions and Permitted Operations
- Permitted: Engaging CIAM team, updating `User.FederationIdentifier` with CIAM-confirmed UUID post-approval, updating work notes.
- Prohibited: Updating `FederationIdentifier` with employee numbers for external users; direct writes without CIAM team validation.

# HITL
- Present to operator: Incident ID, external user details, current Salesforce `FederationIdentifier`, CIAM-validated UUID.
- Valid approval: Explicit confirmation to update Salesforce `FederationIdentifier` to the CIAM UUID.

# Verification
- Expected state: `User.FederationIdentifier == ciam_uuid` AND `User.IsActive == True`.
- Checks: Re-query Salesforce user record to confirm `FederationIdentifier` matches CIAM value.
