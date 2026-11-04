---
issue_code: APP-XAUTHOR-PS-MISSING
title: Conga / Apttus X-Author Access & URL Configuration Issue
domains:
  - APPLICATION
version: 2
user_type: Internal / Standard
condition: "User exists in NA Org AND IsActive = True AND Description contains X-Author Symptom AND (Agreement - Apttus X-Author Master Permission Set Missing OR Incorrect Custom Domain URL Used)"
---

# Purpose
A user is unable to log in to or connect via Conga X-Author for Excel, either due to missing the `Agreement - Apttus X-Author Master Permission Set` or attempting to connect using an incorrect Salesforce environment URL.

# Preconditions
- User must exist in the NA Main Salesforce Org.
- `User.IsActive` must be `True`. (If user is not in NA org, follow Login-1/Login-1B; if inactive, follow Login-3/Login-3A).
- User requires X-Author access and ticket description or error logs mention X-Author connectivity/login issues.

# Environment & URL Architecture Standard
> [!NOTE]
> - **No Org-Specific X-Author URL**: There is no dedicated or org-specific URL for X-Author. Users must log in to X-Author using the standard Salesforce **custom domain URL**.
> - **Production URL**: `https://bdx.my.salesforce.com`
> - **Sandbox URL**: Relevant custom domain sandbox URL (e.g. `https://bdx--<sandbox>.sandbox.my.salesforce.com`).
> - No separate X-Author software license provisioning is performed; access is governed solely by the `Agreement - Apttus X-Author Master Permission Set` and using the custom domain login URL.

# Diagnosis Procedure
1. **Retrieve Incident & Caller Details**: Extract ticket description, symptoms, and caller username/email.
2. **Execute Salesforce Search in NA Org**: Look up user in NA Org.
3. **Validate Account State**:
   - If not found in NA Org $\rightarrow$ route per `LOGIN-1` / `LOGIN-1B`.
   - If `User.IsActive == False` $\rightarrow$ route per `LOGIN-3` / `LOGIN-3A`.
4. **Determine X-Author Access Requirement**:
   - Verify caller's need for Conga X-Author for Excel.
5. **Retrieve Assigned Permission Sets**:
   - Query `PermissionSetAssignment` for user.
6. **Verify Assignment**:
   - Check if `Agreement - Apttus X-Author Master Permission Set` is assigned.
7. **Verify Custom Domain Login URL**:
   - Check if caller is attempting to access via a generic URL (e.g. `login.salesforce.com`) rather than the approved custom domain URL (`https://bdx.my.salesforce.com`).
8. **Confirm Root Cause**:
   - Classify as `APP-XAUTHOR-PS-MISSING` if permission set is missing or if guidance on the custom domain URL is required.

# Guardrails & Operational Boundaries
- Do not attempt to provision external licenses outside Salesforce. Access to X-Author is entirely managed through the `Agreement - Apttus X-Author Master Permission Set` and authenticating through the BD custom domain.

# Remediation & Resolution
1. **Assign Permission Set (If Missing)**:
   - Propose assignment of `Agreement - Apttus X-Author Master Permission Set`.
   - Submit proposal through HITL approval gate and assign in Salesforce NA Org upon approval.
2. **Guide User on Custom Domain URL**:
   - Instruct the user to open X-Author for Excel, select **Custom Domain** on the login prompt, and enter `https://bdx.my.salesforce.com` (or sandbox URL if testing).
3. **Update Work Notes**:
   - Document permission set status, custom domain URL guidance provided, and actions taken.
4. **Resolve Incident**: Close ticket after confirming user can connect to X-Author successfully.
