---
issue_code: OUT-OF-SCOPE-RESOLVER
title: Application Issue Out of Automation Scope - Escalate to Resolver
domains:
  - APPLICATION
version: 1
user_type: Any
condition: "Issue is outside standard automation rules or all permissions already assigned"
---

# Purpose
An application issue is determined to be outside the scope of self-service automation, either because all standard permission sets and licenses are already assigned (requiring deeper L3 application debugging), or because the reported symptom falls into an unhandled custom scope. The incident must be escalated to the designated L3 Group Resolver or L3 Queue Resolver.

# Diagnosis

## Required Evidence
- User is active in Salesforce.
- All candidate permission sets or managed package licenses for the application are already assigned, OR
- The reported application/symptom is outside supported automation paths.

## Investigation Procedure
1. Verify that standard permission sets and licenses have been evaluated.
2. If all required permissions are already assigned, classify as L3 Group Resolver escalation (`OUT-OF-SCOPE-L3-GROUP`).
3. If application type is unhandled or symptom does not match known automation paths, classify as L3 Queue Resolver escalation (`OUT-OF-SCOPE-L3-QUEUE`).
4. Document all evaluated permissions and findings into ServiceNow work notes.
5. Re-route incident ticket to appropriate resolver team.

# Resolution

## Remediation Procedure
1. Record complete investigation audit trail into ServiceNow ticket work notes.
2. Re-route incident to L3 Resolver Group or Queue via `servicenow_reroute_incident`.
3. Inform requester that the issue has been escalated to specialized application tier-3 engineering.

