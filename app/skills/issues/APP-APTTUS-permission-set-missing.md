---
issue_code: APP-APTTUS-PS-MISSING
title: Required Conga / Apttus Permission Set Not Assigned
domains:
  - APPLICATION
version: 2
user_type: Internal / Standard
condition: "User exists in NA Org AND IsActive = True AND Description contains Conga/Agreement Permission or Access Issue AND Required Apttus BU Permission Set Missing"
---

# Purpose
A user is unable to access Conga/Apttus Agreement records or perform contract management operations because their user account has not been assigned the required Business Unit-specific Apttus Permission Set.

# Preconditions
- User must exist in the NA Main Salesforce Org.
- `User.IsActive` must be `True`. (If user is not in NA org, follow Login-1/Login-1B; if inactive, follow Login-3/Login-3A).
- User has active Conga CLM package license and CRM Content User permissions.
- Ticket description references agreement/contract permission or access symptoms.
- The required Business Unit Permission Set corresponding to the user's BU and access level is not assigned in `PermissionSetAssignment`.

# Business Unit Permission Set Mapping Standard
Apttus Permission Set assignment is strictly mapped based on the requested **Business Unit** (`MMS`, `PI`, `IDN`, `GPO`, `BDB`, `Government`, `Surgery`, `MDS`, or `UCC`) and requested **Access Level** (`Read-Only` vs `Read-Write`):

| Business Unit | Read-Only Permission Set Label | Read-Write Permission Set Label |
|---|---|---|
| **MMS** | `Agreement Read Access MMS` | `Agreement Read Write MMS Contract Consultant` |
| **PI** | `Agreement Read Access PI` | `Agreement Read Write PI Contract Consultant` |
| **IDN** | `Agreement Read Access IDN` | `Agreement Read Write IDN Contract Consultant` |
| **GPO** | `Agreement Read Access GPO` | `Agreement Read Write GPO Contract Consultant` |
| **BDB** | `Agreement Read Access BDB` | `Agreement Read Write BDB Contract Consultant` |
| **Government** | `Agreement Read Access Government` | `Agreement Read Write Government Contract Consultant` |
| **Surgery** | `Agreement Read Access Surgery` | `Agreement Read Write Surgery Contract Consultant` |
| **MDS** | `Agreement Read Access MDS` | `Agreement Read Write MDS Contract Consultant` |
| **UCC** | `Agreement Read Access UCC` | `Agreement Read Write UCC Contract Consultant` |

# Diagnosis Procedure
1. **Retrieve Incident & Caller Details**: Extract ticket description, caller email/username, and requested business unit and role.
2. **Execute Salesforce Search in NA Org**: SOSL lookup user by EmployeeNumber/Email/Username.
3. **Validate Account State**:
   - If not found in NA Org $\rightarrow$ route per `LOGIN-1` / `LOGIN-1B`.
   - If `User.IsActive == False` $\rightarrow$ route per `LOGIN-3` / `LOGIN-3A`.
4. **Retrieve Assigned Permission Sets**:
   - Query `PermissionSetAssignment` for the user record.
5. **Determine Requested BU & Access Level**:
   - Parse incident narrative or prompt user/ticket for target BU (`MMS`, `PI`, `IDN`, etc.) and Access Level (`Read-Only` or `Read-Write`).
6. **Verify BU Permission Set**:
   - Check if the matching BU Permission Set (e.g. `Agreement Read Write MMS Contract Consultant` or `Agreement Read Access MMS`) is assigned.
7. **Confirm Root Cause**:
   - If missing, classify root cause as `APP-APTTUS-PS-MISSING`.

# Guardrails & Safety Boundaries
> [!IMPORTANT]
> - Do not assign permission sets without validating the requested Business Unit and whether the user requires Read-Only or Read-Write (Contract Consultant) rights.
> - Ensure hitl approval is obtained before provisioning any write-level contract consultant permission set.

# Remediation & Resolution
1. **Propose Permission Set Assignment**:
   - Target Permission Set: `Agreement Read Access <BU>` or `Agreement Read Write <BU> Contract Consultant`.
   - Submit proposal through HITL approval gate.
2. **Execute Assignment**:
   - Assign the verified Apttus BU Permission Set in Salesforce NA Org.
3. **Verify Access**:
   - Confirm record created in `PermissionSetAssignment`.
4. **Update Work Notes**:
   - Document:
     - Business Unit
     - Requested Access Level (Read-Only vs Read-Write)
     - Expected Permission Set
     - Current Assigned Permission Sets
     - Missing Permission Set Added
5. **Resolve Incident**: Notify caller that the required Apttus BU permission set has been assigned and prompt them to verify agreement access.
