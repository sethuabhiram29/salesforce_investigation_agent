---
issue_code: OBJECT-1
title: User Not Able to Access Wizard App - Wizard Country Field Not Populated on Contact
domains:
  - OBJECT
version: 2
aliases:
  - OBJECT-001
  - OBJECT-WIZARD-COUNTRY-BLANK
---

# Purpose
User is unable to access or search products in the Wizard Application because the `Wizard_Country__c` custom field on their associated Contact record is null, blank, or unpopulated.

# Diagnosis

## Required Evidence
- User exists in NA Org and `User.IsActive == True`.
- Associated Contact record retrieved for affected user.
- `Contact.Wizard_Country__c` is confirmed `NULL`, empty, or unpopulated.
- Mirror user identified from the same region/business unit for baseline country configuration.

## Investigation Procedure / Analysis Logic
1. Retrieve incident and caller details from ServiceNow (`get_incident`, `get_caller`).
2. Execute Salesforce SOSL search in NA Org using available identifiers (`salesforce_user_search`).
3. If user is not found in NA Org, follow Login-1A/Login-1B process.
4. Verify `User.IsActive` status.
5. If inactive, follow Login-3 investigation process.
6. Retrieve Contact record associated with the affected user (`salesforce_get_contact`).
7. Validate `Contact.Wizard_Country__c`.
8. If `Wizard_Country__c` is blank, compare with a working user from the same region/business unit (mirror user).
9. Update `Contact.Wizard_Country__c` with the appropriate value.
10. Reproduce the issue and retest Wizard application access.
11. Confirm successful Product Search and Wizard login.
12. Update ServiceNow incident work notes with findings and actions performed.

## Permitted Diagnostic Tools
- ServiceNow REST Table API - `get_incident`.
- ServiceNow REST Table API - `get_caller`.
- Salesforce MCP SOSL Search Tool.
- Salesforce MCP SOQL Tool - User Detail Lookup (`salesforce_get_user_details`).
- Salesforce MCP SOQL Tool - Contact Lookup (`salesforce_get_contact`).
- Salesforce MCP Update Record Tool - Contact (`salesforce_update_contact`).
- ServiceNow REST Table API - `update_incident`.

## Confirmation Criteria
- `User.IsActive == True` in NA Org.
- Incident mentions Wizard App or Product Search issue.
- `Contact.Wizard_Country__c` is confirmed blank/null.

# Resolution

## Remediation Procedure
1. Identify working mirror user in the same region/department/business unit.
2. Determine authoritative `Wizard_Country__c` value (e.g. `US`, `GB`, `DE`).
3. Populate `Contact.Wizard_Country__c` on the affected user's Contact record with the mirror user's country code.
4. Verify Product Search functionality is restored.
5. Update ServiceNow incident work notes with remediation details.

## Permitted Operations
- Only the `Contact.Wizard_Country__c` field may be updated.
- Direct User profile or permission set modification is prohibited for this issue code.

## Safety Preconditions
- User exists in NA Org.
- User `IsActive == True`.
- `Contact.Wizard_Country__c` is confirmed `NULL` or Blank prior to remediation.

## HITL Requirements
- Human operator authorization required before executing `salesforce_update_contact`.
