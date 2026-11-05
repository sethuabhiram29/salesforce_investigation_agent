---
issue_code: OBJECT-1
title: Blank Wizard_Country__c Field on Contact
domains:
  - OBJECT
version: 1
---

# Purpose
The user is unable to use the Wizard App or performs Product Search resulting in errors or empty results because the `Wizard_Country__c` custom field on their associated Contact record is blank.

# Diagnosis

## Required Evidence
- Caller identity resolved to a Salesforce User in the target Org (NA Org).
- User `IsActive` is `True`.
- Associated Contact record ID identified via `User.ContactId` or SOSL matching caller details.
- `Contact.Wizard_Country__c` is confirmed `null`, empty string, or unpopulated.

## Investigation Procedure
1. Retrieve incident and caller details from ServiceNow.
2. Confirm user exists and is active in NA Org.
3. Query `Contact` record linked to the user via SOQL: `SELECT Id, Name, Wizard_Country__c, Account.Name FROM Contact WHERE Id = :contactId`.
4. Inspect `Wizard_Country__c` field value.
5. If `Wizard_Country__c` is null or empty, confirm diagnosis as `OBJECT-1`.

## Permitted Diagnostic Tools
- ServiceNow REST Table API - `get_incident`, `get_caller`.
- Salesforce MCP SOQL Tool - Contact record lookup.
- ServiceNow REST Table API - `update_incident` (work notes).

## Confirmation Criteria
- User is active in NA Org.
- Incident mentions Wizard App or Product Search issue.
- `Contact.Wizard_Country__c` is confirmed blank/null.

# Resolution

## Remediation Procedure
1. Identify the user's correct country / jurisdiction from the ServiceNow caller profile or User record (`User.Country`, `User.CountryCode`).
2. If confirmed, prepare update payload for `Contact.Wizard_Country__c` with valid country code.
3. Submit HITL approval for updating Contact record.
4. If automated write is restricted, direct user/admin to update the Contact record via Manage User Access RITM.
5. Log findings and resolution instructions in ServiceNow incident work notes.

## HITL Requirements
- Explicit human approval required before updating `Contact.Wizard_Country__c`.

## Verification
- Re-query `Contact.Wizard_Country__c` to ensure it is populated with a valid country value.
- Have user relaunch Wizard App and perform Product Search.

