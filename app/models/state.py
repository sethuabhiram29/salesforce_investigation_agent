"""Shared LangGraph investigation state.

Defines the TypedDict used by the outer graph to maintain investigation state.
Individual agents update their portion of this state.

Fields:
- incident: Original incident details and identifiers
- affected_user: Resolved affected user identity
- triage_result: Classification, extracted search values and ambiguity
- skill_refs: Selected skill code, version and stage
- evidence: Structured observations and provenance
- historical_cases: Relevant historical references from pgvector
- knowledge_refs: Relevant Neo4j nodes or relationships
- diagnosis_result: Findings, issue code, status and evidence references
- resolution_plan: Proposed changes, prerequisites and expected result
- approval: Approval status, approver and approved action reference
- verification_result: Post-change evidence and verification status
- communication_draft: Draft communication for requester
- servicenow_update: Summary of updates applied to ServiceNow
- attempted_checks: Previously executed checks to avoid repeated work
- trace_events: Timeline of actual execution events
- error: Structured execution or integration failure
"""

from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


class InvestigationState(TypedDict, total=False):
    """Outer LangGraph shared investigation state across all 10 stages."""

    # 1. Ticket details
    incident: Dict[str, Any]

    # 2. Affected user and mirror user resolution
    affected_user: Optional[Dict[str, Any]]
    mirror_user: Optional[Dict[str, Any]]

    # 3. Triage output
    triage_result: Optional[Dict[str, Any]]

    # 4. Canonical skill tracking
    skill_refs: Dict[str, Any]

    # 5. Evidence & Knowledge
    evidence: List[Dict[str, Any]]
    historical_cases: List[Dict[str, Any]]
    knowledge_refs: List[Dict[str, Any]]

    # 6. Diagnosis outcome
    diagnosis_result: Optional[Dict[str, Any]]

    # 7. Resolution proposal
    resolution_plan: Optional[Dict[str, Any]]

    # 8. HITL approval state
    approval: Optional[Dict[str, Any]]

    # 9. Post-remediation verification
    verification_result: Optional[Dict[str, Any]]

    # 10. Communication & ServiceNow close
    communication_draft: Optional[str]
    servicenow_update: Optional[Dict[str, Any]]

    # Safety, loop control & auditing
    attempted_checks: List[str]
    iteration_count: int
    trace_events: List[Dict[str, Any]]
    step_audit_trail: List[Dict[str, Any]]
    evidence_cache: Dict[str, Any]
    error: Optional[Dict[str, Any]]
