---
issue_code: LOGIN-3A
title: Account Intentionally Deactivated by Delegated Administrator
domains:
  - LOGIN
version: 2
user_type: Any
condition: "User exists in NA org AND IsActive = False AND Deactivated user identified in SetupAuditTrail AND SetupAuditTrail.CreatedById matches DelegateGroupMember.UserOrGroupId"
---

# Purpose
An account has been intentionally deactivated by a Delegated Administrator, preventing the user from authenticating into Salesforce. This applies when the user's `IsActive` field is `False` in the NA Org and audit trail evidence confirms deactivation by a member of a Delegated Administration Group (`DelegateGroupMember`).

# Diagnosis

## Required Evidence
- User exists in the primary NA Salesforce organization.
- `User.IsActive == False`.
- Deactivation event identified in `SetupAuditTrail`.
- `SetupAuditTrail.CreatedById` matches a Delegated Administrator member (`DelegateGroupMember.UserOrGroupId`).

## Investigation Procedure
1. Retrieve incident and caller details.
2. Search user in NA Org using Salesforce SOSL Search (`salesforce_user_search` / `salesforce_execute_sosl`).
3. If user not found, follow Login-1A/Login-1B process.
4. Verify `User.IsActive` field.
5. If `IsActive=False`, retrieve latest user deactivation entries from `SetupAuditTrail`.
6. Retrieve Delegated Administrator members using `DelegateGroupMember` object.
7. Compare `SetupAuditTrail.CreatedById` (or corresponding user identifier) with `DelegateGroupMember.UserOrGroupId`.
8. If match found, confirm user was deactivated by Delegated Administrator.
9. Update incident work notes with deactivation details.
10. Inform user to raise Manage User RITM for reactivation.

## Permitted Diagnostic Tools
- `salesforce_user_search`: Search users by email, username, or employee number.
- `salesforce_get_user_details`: Retrieve full user record (`IsActive`, `EmployeeNumber`, `Profile`).
- `salesforce_execute_soql`: Query `SetupAuditTrail` and `DelegateGroupMember`.

## Confirmation Criteria
Confirmed only when:
- User is uniquely resolved in NA Org.
- `User.IsActive == False`.
- `SetupAuditTrail` record confirms deactivation action.
- Actor is verified as a Delegated Administrator via `DelegateGroupMember.UserOrGroupId`.

## Alternative Explanations
- If `IsActive == True`: Not deactivated; evaluate Federation ID issues (LOGIN-4, LOGIN-5, LOGIN-6).
- If `SetupAuditTrail.CreatedById` matches MuleSoft Integration User: Classify as MuleSoft-driven deactivation (LOGIN-3).
- If user not found in NA Org: Follow LOGIN-1 / LOGIN-1B.

# Resolution

## Required Confirmed Diagnosis
- `issue_code: LOGIN-3A`
- `status: confirmed`

## Remediation Procedure
Direct reactivation by the automated agent in Salesforce is strictly prohibited per security compliance policy.
1. Formulate resolution guidance notifying the user that their account was intentionally deactivated by a Delegated Administrator.
2. Instruct the user to submit a **Manage User RITM** in ServiceNow for authorized account reactivation approval.
3. Update ServiceNow incident work notes with complete deactivation audit details (actor, timestamp, Delegated Administrator verification).
4. Inform user and resolve/close the incident per support process.

## Preconditions and Permitted Operations
- Permitted: ServiceNow work notes update, requester communication, incident closure.
- Prohibited: Directly updating `User.IsActive = True` in Salesforce without an approved Manage User RITM.

# HITL
- Present to operator: Incident ID, user details, deactivation actor, confirmed Delegated Admin status, RITM instructions.
- Valid approval: Explicit confirmation to notify user and close ticket with Manage User RITM instructions.

# Verification
- Expected state: ServiceNow incident contains audit work notes and Manage User RITM communication delivered to caller.
- Checks: Confirm `User.IsActive == False` remains unchanged in Salesforce (no unauthorized mutation) and RITM guidance is logged.
