---
issue_code: APP-APTTUS-PS-MISSING
title: Agreement - Apttus Permission Set Missing
domains:
  - APPLICATION
version: 1
user_type: Any
condition: "User exists AND IsActive = True AND Description contains Permission/Access Symptom AND Apttus Permission Set NOT Assigned"
---

# Purpose
A user cannot access Apttus/Conga agreement records or contract management functions because the general Agreement Apttus Permission Set (`Apttus_Agreement_PermissionSet` / `Conga_Agreement_User`) is missing from their assigned permission sets.

# Diagnosis

## Required Evidence
- User exists and `User.IsActive == True`.
- Incident description contains "Permission or Access issue" symptoms relating to agreements.
- Querying `PermissionSetAssignment` reveals that the Agreement Apttus Permission Set is missing.

## Investigation Procedure
1. Retrieve incident narrative and detect agreement permission/access symptoms.
2. Verify user active status in Salesforce.
3. Query assigned permission sets for user (`salesforce_get_user_permission_sets`).
4. Check if Agreement Apttus Permission Set is assigned.
5. If absent, confirm root cause as `APP-APTTUS-PS-MISSING`.
6. Formulate resolution plan to assign Apttus Agreement permission set.

## Confirmation Criteria
Confirmed only when:
- User is active in Salesforce.
- Ticket mentions agreement permission/access symptoms.
- Agreement Apttus Permission Set is not assigned.

# Resolution

## Remediation Procedure
1. Formulate remediation proposal to assign `Apttus_Agreement_PermissionSet` to the user.
2. Submit proposal to human operator approval gate (HITL).
3. Upon approval, execute assignment.
4. Verify assignment in Salesforce.
5. Update ServiceNow work notes and resolve ticket.
