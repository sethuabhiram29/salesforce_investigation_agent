---
issue_code: APP-BU-MISSING
title: User Not Added to Required Business Unit Public Group
domains:
  - APPLICATION
version: 2
user_type: Internal / Standard
condition: "User exists in NA Org AND IsActive = True AND Required BU Public Group Membership Missing"
---

# Purpose
A user cannot access or view Conga contract documents and Content Versions in Salesforce because they have not been added to their required Business Unit Public Group (`GroupMember`).

# Preconditions
- User must exist in the NA Main Salesforce Org.
- `User.IsActive` must be `True`. (If user is not in NA org, follow Login-1/Login-1B; if inactive, follow Login-3/Login-3A).
- User has active Conga CLM package license and CRM Content User permissions.
- The user is missing membership in the required Business Unit Public Group in `GroupMember`.

# Business Unit Public Group Mapping Standard
Public Group membership directly governs visibility to contract documents and Content Versions:

| Business Unit | Read-Only Public Group Name | Read-Write Public Group Name |
|---|---|---|
| **MMS** | `MMS READ ONLY GROUP` | `MMS READ WRITE GROUP` |
| **PI** | `PI READ ONLY GROUP` | `PI READ WRITE GROUP` |
| **IDN** | `IDN READ ONLY GROUP` | `IDN READ WRITE GROUP` |
| **GPO** | `GPO READ ONLY GROUP` | `GPO READ WRITE GROUP` |
| **BDB** | `BDB READ ONLY GROUP` | `BDB READ WRITE GROUP` |
| **Government** | `Government READ ONLY GROUP` | `Government READ WRITE GROUP` |
| **Surgery** | `Surgery READ ONLY GROUP` | `Surgery READ WRITE GROUP` |
| **MDS** | `MDS READ ONLY GROUP` | `MDS READ WRITE GROUP` |
| **UCC** | `UCC READ ONLY GROUP` | `UCC READ WRITE GROUP` |

# Diagnosis Procedure
1. **Retrieve Incident & Caller Details**: Extract ticket details and obtain user's Business Unit and required access level (Read-Only or Read-Write).
2. **Execute Salesforce Search in NA Org**: Lookup user in NA Org.
3. **Validate Account State**:
   - If not found in NA Org $\rightarrow$ route per `LOGIN-1` / `LOGIN-1B`.
   - If `User.IsActive == False` $\rightarrow$ route per `LOGIN-3` / `LOGIN-3A`.
4. **Determine Business Unit & Access Level**:
   - Identify the user's Business Unit based on business input/confirmation and determine whether Read-Write or Read-Only access is needed.
5. **Verify Public Group Membership**:
   - Query `GroupMember` joined with `Group` for the user record.
6. **Evaluate Root Cause**:
   - If user is not present in the matching Public Group (e.g. `MMS READ WRITE GROUP` or `MMS READ ONLY GROUP`), confirm root cause as `APP-BU-MISSING`.

# Guardrails & Operational Authorization
> [!IMPORTANT]
> - **Direct Update Authorization**: Yes, the support team is authorized to directly update Public Group memberships in Salesforce (`Setup > Public Groups` or via `GroupMember` API).
> - Adding a user to a Public Group does not modify core User record fields, but HITL confirmation is logged for traceability.

# Remediation & Resolution
1. **Add User to Business Unit Public Group**:
   - Add user to the target Public Group (`<BU> READ WRITE GROUP` or `<BU> READ ONLY GROUP`) using `salesforce_add_user_to_public_group`.
2. **Validate Contract Document Visibility**:
   - Verify that the user now has visibility to contract documents and Content Versions.
3. **Update Work Notes**:
   - Log findings: Business Unit, Public Group assigned, date/time of assignment, and verification result.
4. **Resolve Incident**: Inform caller that they have been added to the BU Public Group and can now view contract documents.
