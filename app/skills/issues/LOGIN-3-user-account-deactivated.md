---
issue_code: LOGIN-3
title: Automated Deactivation from MuleSoft Integration Process
domains:
  - LOGIN
version: 2
user_type: Any
condition: "User exists in NA Org AND IsActive = False AND SetupAuditTrail.CreatedById = MuleSoft Integration User"
---

# Purpose
An account has been automatically deactivated by the automated MuleSoft integration process (e.g. Workday HR synchronization, inactivity threshold, or synchronization error). The automated agent must investigate the deactivation event, inspect integration logs, and engage the MuleSoft/Workday teams.

# Diagnosis

## Required Evidence
- User exists in the primary NA Salesforce organization.
- `User.IsActive == False`.
- Deactivation event identified in `SetupAuditTrail`.
- `SetupAuditTrail.CreatedById` matches the MuleSoft Integration User.

## Investigation Procedure
1. Retrieve incident and caller details.
2. Search user in NA Org using Salesforce SOSL Search (`salesforce_user_search` / `salesforce_execute_sosl`).
3. If user not found, follow Login-1A/Login-1B process.
4. Verify `User.IsActive` field.
5. If `IsActive=False`, retrieve latest deactivation entries from `SetupAuditTrail`.
6. Identify deactivation event corresponding to the affected user.
7. Validate that `SetupAuditTrail.CreatedById` matches MuleSoft Integration User.
8. If match found, classify as MuleSoft-driven deactivation.
9. Retrieve deactivation payload/log details from MuleSoft/Kibana (API/MCP if available).
10. Determine whether deactivation occurred due to inactivity, Workday status change, synchronization issue, or other integration event.
11. Update incident work notes with findings.
12. Route or engage MuleSoft/Workday support teams if additional action is required.

## Permitted Diagnostic Tools
- `salesforce_user_search`: Search users by email, username, or employee number.
- `salesforce_get_user_details`: Retrieve full user record.
- `salesforce_execute_soql`: Query `SetupAuditTrail`.
- Kibana / MuleSoft API lookup (read-only integration log inspection).

## Confirmation Criteria
Confirmed only when:
- User is uniquely resolved in NA Org.
- `User.IsActive == False`.
- `SetupAuditTrail.CreatedById` matches the MuleSoft Integration User.

## Alternative Explanations
- If `SetupAuditTrail.CreatedById` matches `DelegateGroupMember`: Classify as Delegated Admin deactivation (LOGIN-3A).
- If `IsActive == True`: Account is active; evaluate Federation ID issues (LOGIN-4, LOGIN-5, LOGIN-6).
- If user not found in NA Org: Follow LOGIN-1 / LOGIN-1B.

# Resolution

## Required Confirmed Diagnosis
- `issue_code: LOGIN-3`
- `status: confirmed` / `escalation_required`

## Remediation Procedure
1. Investigate the deactivation reason with the MuleSoft team and inspect integration payload/Kibana logs.
2. Cross-reference upstream HR status with the Workday team to check for termination, leave of absence, or rehire events.
3. Update ServiceNow incident work notes with comprehensive integration findings.
4. Route or engage the MuleSoft/Workday support teams for automated synchronization correction or account remediation.

## Preconditions and Permitted Operations
- Permitted: ServiceNow work notes update, integration log inspection, ticket routing to MuleSoft/Workday queue.
- Prohibited: Directly modifying `User.IsActive = True` in Salesforce without resolving upstream Workday synchronization state.

# HITL
- Present to operator: Incident ID, user details, MuleSoft deactivation timestamp, Kibana payload findings, target escalation group.
- Valid approval: Explicit confirmation to document findings and engage MuleSoft/Workday support teams.

# Verification
- Expected state: Incident work notes updated with MuleSoft deactivation payload details and routed to integration support.
- Checks: Confirm `User.IsActive == False` remains intact pending integration remediation.
