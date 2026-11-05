---
issue_code: OBJECT-3
title: Users Cannot Access Product Search Object - Wizard Country Blank on Contact Record
domains:
  - OBJECT
version: 2
aliases:
  - OBJECT-003
---

# Purpose
Users are unable to perform Product Search or access the Product Search object in Salesforce because the custom field `Wizard_Country__c` on their associated Contact record is blank or unpopulated.

# Diagnosis

## Required Evidence
- User exists in NA Org and `User.IsActive == True`.
- Associated Contact record retrieved for affected user.
- `Contact.Wizard_Country__c` is confirmed `NULL`, empty, or invalid.
- Mirror user identified from the same region/business unit for baseline country code.

## Investigation Procedure / Analysis Logic
1. Retrieve incident and caller details from ServiceNow (`get_incident`, `get_caller`).
2. Execute Salesforce SOSL search in NA Org using available identifiers (`salesforce_user_search`).
3. If user is not found in NA Org, follow Login-1A/Login-1B process.
4. Verify `User.IsActive` status.
5. If inactive, follow Login-3 investigation process.
6. Retrieve Contact record associated with the affected user (`salesforce_get_contact`).
7. Validate `Contact.Wizard_Country__c`.
8. Compare with a working user record from the same region/business unit (mirror user).
9. Update `Contact.Wizard_Country__c` if blank or incorrect with the appropriate value.
10. Retest Product Search access.
11. Confirm successful Product Search functionality and object visibility.
12. Update ServiceNow work notes with findings and actions performed.

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
- Product search error reported by user.
- `Contact.Wizard_Country__c` is confirmed blank/null.

# Resolution

## Remediation Procedure
1. Identify working mirror user in the same region/department/business unit.
2. Determine authoritative `Wizard_Country__c` value (e.g. `US`, `GB`, `DE`).
3. Update `Contact.Wizard_Country__c` on the affected user's Contact record with the valid country code.
4. Retest Product Search access and object visibility.
5. Update ServiceNow incident work notes with remediation details.

## Permitted Operations
- Only the `Contact.Wizard_Country__c` field may be modified.

## Safety Preconditions
- User exists in NA Org.
- User `IsActive == True`.
- `Contact.Wizard_Country__c` is confirmed `NULL` or Blank prior to remediation.

## HITL Requirements
- Human operator authorization required before executing `salesforce_update_contact`.
