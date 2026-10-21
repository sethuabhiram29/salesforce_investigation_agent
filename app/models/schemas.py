"""Pydantic schemas for structured agent outputs.

Includes:
- TriageResult: classification output
- DiagnosisResult: structured findings with evidence refs
- ResolutionPlan: proposed remediation with preconditions
- ApprovalRequest: HITL approval details
- VerificationResult: post-change verification status
- EvidenceRecord: individual observation with provenance
- HistoricalCase: past incident context from PostgreSQL
- TraceEvent: audit trail entry
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class IncidentData(BaseModel):
    """Raw incident information from ServiceNow intake."""
    incident_id: str
    short_description: str
    description: str
    caller_id: Optional[str] = None
    caller_email: Optional[str] = None
    on_behalf_of: Optional[str] = None
    on_behalf: Optional[str] = None
    requested_for: Optional[str] = None
    affected_user_id: Optional[str] = None
    affected_user_email: Optional[str] = None
    mirror_user_email: Optional[str] = None
    created_at: Optional[str] = None


class TriageResult(BaseModel):
    """Classification output from Triage Agent."""
    domain: Literal["LOGIN", "APPLICATION", "RECORD", "OBJECT"]
    is_ambiguous: bool = False
    extracted_entities: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0
    reasoning: str = ""


class EvidenceRecord(BaseModel):
    """Structured observation and provenance from a tool inspection."""
    evidence_id: str
    tool_name: str
    field_name: Optional[str] = None
    observed_value: Any = None
    raw_output: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class Finding(BaseModel):
    """An individual claim supported by evidence."""
    claim: str
    evidence_refs: List[str] = Field(default_factory=list)


class DiagnosisResult(BaseModel):
    """Structured diagnosis outcome from Diagnosis Agent."""
    status: Literal[
        "confirmed",
        "insufficient_evidence",
        "contradicted",
        "ambiguous_identity",
        "escalation_required",
    ]
    issue_code: Optional[str] = None
    findings: List[Finding] = Field(default_factory=list)
    unresolved_questions: List[str] = Field(default_factory=list)
    recommended_action: Literal["resolution", "switch_hypothesis", "escalate"] = "resolution"
    expected_criteria: Optional[str] = None
    observed_values: Optional[Dict[str, Any]] = None
    comparison_summary: Optional[str] = None
    decision_basis: Optional[str] = None
    next_step_reason: Optional[str] = None


class RemediationAction(BaseModel):
    """Specific remediation operation proposal."""
    action_type: str
    target_record_id: str
    target_object: str
    target_field: str
    current_value: Any = None
    proposed_value: Any = None
    justification: str


class ResolutionPlan(BaseModel):
    """Remediation proposal constructed by Resolution Agent."""
    issue_code: str
    proposed_action: RemediationAction
    preconditions: List[str] = Field(default_factory=list)
    requires_approval: bool = True
    rollback_plan: str = ""
    status: Literal["draft", "approved", "rejected", "executed"] = "draft"


class ApprovalRequest(BaseModel):
    """HITL Approval interrupt payload bound to the exact proposed action."""
    approval_id: str
    incident_id: str
    issue_code: str
    action_proposal: RemediationAction
    evidence_summary: List[str]
    approver: Optional[str] = None
    approval_status: Literal["pending", "approved", "rejected"] = "pending"
    decision_timestamp: Optional[str] = None
    rejection_reason: Optional[str] = None


class VerificationResult(BaseModel):
    """Post-change verification output from Verification Agent."""
    verified: bool
    expected_state: Dict[str, Any]
    actual_state: Dict[str, Any]
    checks_performed: List[str] = Field(default_factory=list)
    details: str = ""


class HistoricalCase(BaseModel):
    """Relevant historical incident retrieved from PostgreSQL pgvector."""
    incident_id: str
    summary: str
    description: str
    domain: str
    root_cause: str
    resolution: str
    similarity: float


class TraceEvent(BaseModel):
    """Audit trail record for full investigation transparency."""
    event_id: str
    stage: str
    agent_name: str
    action: str
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
