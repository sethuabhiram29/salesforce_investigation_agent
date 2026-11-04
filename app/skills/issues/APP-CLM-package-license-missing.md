---
issue_code: APP-CLM-LICENSE-MISSING
title: Conga Contract Lifecycle Management Package License Not Assigned
domains:
  - APPLICATION
version: 1
user_type: Internal
package_license_name: "Conga Contract Lifecycle Management"
condition: "User exists in NA Org AND IsActive = True AND Conga CLM User Configuration Missing"
---

# Purpose
An active internal user cannot access Conga Contract Lifecycle Management (CLM) features or agreement records because the **"Conga Contract Lifecycle Management"** package license has not been allocated to their Salesforce user record.

# Key Architecture & Domain Guidelines
- **Configuration Requirement**: Conga CLM user configuration requires assigning the **"Conga Contract Lifecycle Management"** package license.
- **Underlying Salesforce Object**: `UserPackageLicense`
- **Request Mechanism**: User must submit a **Manage User Access request for Conga CLM onboarding/licensing**.

# Safety Rules & Preconditions
> [!IMPORTANT]
> - User must exist in NA Org and be active (`IsActive == True`) before Conga access validation is performed.
> - Login-related issues must be resolved first.
> - Conga CLM user configuration must exist before application access can be granted.

# Diagnosis

## Required Evidence
1. User exists in NA Org and `User.IsActive == True`.
2. Ticket narrative indicates Conga CLM access or onboarding failure.
3. SOQL inspection of `UserPackageLicense` confirms the user has NOT been assigned the `Conga Contract Lifecycle Management` package license.

## Investigation Procedure
1. Retrieve incident and caller details from ServiceNow.
2. Extract Email ID, Federation ID, Username, Employee ID, or Full Name.
3. Execute Salesforce SOSL search in NA Org using available identifiers.
4. If user not found in NA, follow Login-1A/Login-1B process.
5. Retrieve Salesforce User details and verify account is active (`User.IsActive == True`).
6. If user is inactive, follow Login-3 investigation process.
7. Verify whether the user has been assigned the **"Conga Contract Lifecycle Management"** package license using `UserPackageLicense`.
8. If the package license is not assigned, classify as Conga User Configuration Issue (`APP-CLM-LICENSE-MISSING`) and initiate the Conga onboarding/access provisioning process.
9. Validate Conga application access.
10. Update incident work notes with findings and actions performed.

## Permitted Diagnostic Tools
- `servicenow_get_incident`
- `servicenow_get_caller`
- `salesforce_user_search`
- `salesforce_get_user_details`
- `salesforce_execute_soql` (Query `UserPackageLicense`)
- `servicenow_add_work_notes`

## Confirmation Criteria
Confirmed only when:
- User is active in NA Org.
- Incident involves Conga CLM access or onboarding.
- `UserPackageLicense` confirms `Conga Contract Lifecycle Management` package license is missing.

# Resolution

## Remediation Procedure
1. Verify whether the user has the **"Conga Contract Lifecycle Management"** package license assigned.
2. If the package license is not assigned:
   - Instruct requester to submit a **Manage User Access request for Conga CLM onboarding/licensing**.
   - Route request per established Conga access provisioning process.
3. Update ServiceNow incident work notes with findings, licensing status, and onboarding guidance.
