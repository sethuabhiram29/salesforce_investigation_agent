---
issue_code: APP-XAUTHOR-PS-MISSING
title: Conga / Apttus X-Author Permission Set Missing
domains:
  - APPLICATION
version: 1
user_type: Any
condition: "User exists AND IsActive = True AND Description contains X-Author Symptom AND Apttus X-Author Permission Set NOT Assigned"
---

# Purpose
A user cannot connect to Salesforce through Conga X-Author for Excel or view contract templates because the required `Apttus_X_Author` (or Agreement - Apttus X-Author) Permission Set is not assigned.

# Diagnosis

## Required Evidence
- User exists and `User.IsActive == True`.
- Incident description contains "X-Author related issue" symptoms.
- Querying `PermissionSetAssignment` reveals that Apttus X-Author Permission Set is missing.

## Investigation Procedure
1. Retrieve incident narrative and detect X-Author error symptoms.
2. Verify user active status in Salesforce.
3. Query assigned permission sets for user (`salesforce_get_user_permission_sets`).
4. Check if `Apttus_X_Author` permission set is present.
5. If absent, confirm root cause as `APP-XAUTHOR-PS-MISSING`.
6. Formulate resolution plan to assign X-Author permission set.

## Confirmation Criteria
Confirmed only when:
- User is active in Salesforce.
- Ticket mentions X-Author errors.
- Apttus X-Author Permission Set is not assigned.

# Resolution

## Remediation Procedure
1. Formulate remediation proposal to assign `Apttus_X_Author` permission set to the user.
2. Submit proposal to human operator approval gate (HITL).
3. Upon approval, execute assignment.
4. Verify assignment in Salesforce.
5. Update ServiceNow work notes and resolve ticket.
