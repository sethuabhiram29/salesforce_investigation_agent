---
issue_code: RECORD-2
title: Missing Opportunity or Case Record Sharing
domains:
  - RECORD
version: 1
---

# Purpose
The user has object-level permissions to Opportunity or Case, but cannot access a specific Opportunity or Case record because record-level sharing is missing (Organization-Wide Defaults (OWD) is Private, user is outside Role Hierarchy, and no Sharing Rule, Opportunity/Case Team, Queue, Territory, or Manual Share grants access).

# Diagnosis

## Required Evidence
- Caller identity resolved to a Salesforce User in target Org (NA Org).
- User `IsActive` is `True`.
- Specific Opportunity or Case Record ID identified.
- User has Object-level Read permission on Opportunity / Case.
- `UserRecordAccess.HasReadAccess` is `False` for the affected record ID.
- Review of Owner, OWD, Role Hierarchy, Sharing Rules, Account/Opportunity Teams, Queues, and Territories confirms no active sharing path.

## Investigation Procedure
1. Identify affected Opportunity or Case record ID from incident narrative.
2. Verify user has Object CRUD permissions on Opportunity or Case.
3. Query `UserRecordAccess`:
   `SELECT RecordId, HasReadAccess, HasEditAccess FROM UserRecordAccess WHERE UserId = :userId AND RecordId = :recordId`.
4. Confirm `HasReadAccess` is `False`.
5. Audit Record Sharing:
   - Check Record Owner (User is not owner).
   - Check OWD for Opportunity/Case (Private/Public Read Only).
   - Check Role Hierarchy (Record owner does not report below user).
   - Query `OpportunityShare` or `CaseShare` for user, roles, or public groups.
6. Confirm missing sharing path as `RECORD-2`.

## Permitted Diagnostic Tools
- Salesforce MCP SOQL Tool - UserRecordAccess Lookup.
- Salesforce MCP SOQL Tool - OpportunityShare / CaseShare Lookup.
- ServiceNow REST Table API - `update_incident`.

## Confirmation Criteria
- User is active in NA Org.
- Object-level permissions present.
- `UserRecordAccess.HasReadAccess == False`.
- No sharing rule or team membership grants access.

# Resolution

## Remediation Procedure
1. Determine appropriate sharing mechanism:
   - Add user to Opportunity Team / Case Team with Read or Read/Write access.
   - Or create manual record share via `OpportunityShare` / `CaseShare`.
   - Or update Criteria-Based Sharing Rule / Public Group membership if systematic.
2. Submit HITL approval for adding user to Opportunity Team or Case Team.
3. Update ServiceNow incident work notes with diagnosed sharing gap and recommended team addition.

## HITL Requirements
- Human operator approval required before adding record sharing or team memberships.

