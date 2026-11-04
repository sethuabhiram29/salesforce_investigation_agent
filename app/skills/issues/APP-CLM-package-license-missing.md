---
issue_code: APP-CLM-LICENSE-MISSING
title: CLM Package License Missing in Salesforce User Record
domains:
  - APPLICATION
version: 1
user_type: Any
condition: "User exists AND IsActive = True AND Description contains CLM Onboarding Symptom AND CLM Package License NOT Assigned"
---

# Purpose
A user onboarding to Conga CLM (Contract Lifecycle Management) cannot access CLM objects, agreements, or contract templates because the managed package license (`UserPackageLicense` for Conga CLM / Apttus) has not been allocated to their user record.

# Diagnosis

## Required Evidence
- User exists and `User.IsActive == True`.
- Incident description contains "CLM New User Onboarding Issue" or CLM setup symptoms.
- User does not have an active `UserPackageLicense` for the Conga CLM managed package.

## Investigation Procedure
1. Retrieve incident description and identify CLM new user onboarding symptom.
2. Verify user active status in Salesforce.
3. Query `UserPackageLicense` via SOQL/MCP for the affected user.
4. Verify whether Conga CLM managed package license is allocated.
5. If license is missing, confirm root cause as `APP-CLM-LICENSE-MISSING`.
6. Formulate resolution plan to assign CLM package license.

## Confirmation Criteria
Confirmed only when:
- User is active in Salesforce.
- Ticket mentions CLM onboarding or setup.
- CLM Package License is not assigned to the user.

# Resolution

## Remediation Procedure
1. Formulate remediation proposal to assign `UserPackageLicense` for Conga CLM.
2. Submit proposal to human operator approval gate (HITL).
3. Upon approval, assign managed package license.
4. Verify license in Salesforce.
5. Update ServiceNow work notes and resolve ticket.
