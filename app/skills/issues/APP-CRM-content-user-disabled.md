---
issue_code: APP-CRM-CONTENT-DISABLED
title: CRM Content User Feature Not Enabled in Salesforce User Record
domains:
  - APPLICATION
version: 1
user_type: Any
condition: "User exists AND IsActive = True AND Description contains CRM Content Symptom AND UserPermissionsSFContentUser = False"
---

# Purpose
A user cannot access Salesforce CRM Content, workspace libraries, or document attachments because the `UserPermissionsSFContentUser` (CRM Content User) feature license checkbox is disabled on their User record.

# Diagnosis

## Required Evidence
- User exists and `User.IsActive == True`.
- Incident description contains "CRM Content / Content Library Issue" symptoms.
- `User.UserPermissionsSFContentUser == False` (or `UserPermissionsContentUser == False`).

## Investigation Procedure
1. Retrieve incident description and detect CRM Content / Content Library symptoms.
2. Verify user active status in Salesforce.
3. Query `UserPermissionsSFContentUser` field from User record.
4. If field is False/disabled, confirm root cause as `APP-CRM-CONTENT-DISABLED`.
5. Formulate remediation plan to enable CRM Content User.

## Confirmation Criteria
Confirmed only when:
- User is active in Salesforce.
- Ticket mentions CRM Content / Content Library access issues.
- `User.UserPermissionsSFContentUser` is False.

# Resolution

## Remediation Procedure
1. Formulate remediation proposal: `UPDATE User SET UserPermissionsSFContentUser = True WHERE Id = :user_id`.
2. Submit proposal to human operator approval gate (HITL).
3. Upon approval, execute user update.
4. Verify user record shows `UserPermissionsSFContentUser == True`.
5. Update ServiceNow work notes and inform user.
