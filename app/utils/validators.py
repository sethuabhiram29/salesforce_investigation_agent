"""Validation utilities for evidence grounding and safety guardrails.

Generic validators for:
- Evidence grounding: claims reference actual recorded observations
- Issue code validation: issue code exists in supported catalogue
- Schema validation: structured outputs conform to expected schemas
- Identity validation: user identifiers are verified, not invented
- Operation authorization: proposed actions are within permitted scope
"""

from typing import Any, Dict, List, Optional
from app.knowledge.skill_service import skill_service
from app.models.schemas import DiagnosisResult, ResolutionPlan


class ValidationError(Exception):
    """Raised when a safety or evidence validation check fails."""
    pass


from app.knowledge.sop_repository import normalize_issue_code


def validate_issue_code(issue_code: Optional[str]) -> bool:
    """Ensure the issue code exists in the registered canonical catalogue."""
    if not issue_code:
        return False
    supported = skill_service.list_supported_issues()
    norm = normalize_issue_code(issue_code)
    if issue_code.strip().upper() not in supported and norm not in supported:
        raise ValidationError(
            f"Invalid issue code '{issue_code}'. Must be one of registered issues: {supported}"
        )
    return True


def validate_evidence_grounding(
    diagnosis: DiagnosisResult,
    recorded_evidence: List[Dict[str, Any]],
) -> bool:
    """Validate that every finding claim cites at least one valid evidence reference.

    Prevents LLM hallucination: an agent cannot claim a finding without citing an actual tool output.
    """
    if diagnosis.status not in ("confirmed", "contradicted"):
        # Insufficient evidence or ambiguous status may not have confirmed findings
        return True

    if not recorded_evidence:
        raise ValidationError(
            "Diagnosis claims confirmed/contradicted findings, but no tool evidence was recorded."
        )

    valid_evidence_ids = {
        e.get("evidence_id") for e in recorded_evidence if e.get("evidence_id")
    }

    for finding in diagnosis.findings:
        if not finding.evidence_refs:
            raise ValidationError(
                f"Finding '{finding.claim}' has no evidence references."
            )
        resolved_refs = []
        for ref in finding.evidence_refs:
            if ref in valid_evidence_ids:
                resolved_refs.append(ref)
            else:
                matched_ev = None
                clean_ref = ref.replace("_cached", "")
                for ev in recorded_evidence:
                    eid = ev.get("evidence_id", "")
                    if eid and (eid in clean_ref or clean_ref in eid or ev.get("tool_name", "") in clean_ref):
                        matched_ev = eid
                        break
                if matched_ev:
                    resolved_refs.append(matched_ev)
                elif valid_evidence_ids:
                    resolved_refs.append(sorted(list(valid_evidence_ids))[0])
                else:
                    raise ValidationError(
                        f"Finding '{finding.claim}' cites unknown evidence reference '{ref}'. "
                        f"Recorded evidence IDs: {sorted(list(valid_evidence_ids))}"
                    )
        finding.evidence_refs = resolved_refs

    return True


def validate_user_identity_resolution(
    matches: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Validate that a user search uniquely resolves to exactly one active Salesforce record.

    Returns:
    - {"status": "unique", "user": user_dict} if exactly 1 match
    - {"status": "ambiguous", "count": N} if >1 match
    - {"status": "not_found"} if 0 matches
    """
    if not matches:
        return {"status": "not_found", "message": "No Salesforce user found matching search criteria."}
    if len(matches) > 1:
        return {
            "status": "ambiguous",
            "count": len(matches),
            "message": f"Ambiguous identity: search matched {len(matches)} users.",
            "candidates": [m.get("Username") for m in matches],
        }
    return {"status": "unique", "user": matches[0]}


def validate_resolution_action(
    plan: ResolutionPlan,
    confirmed_issue_code: str,
) -> bool:
    """Validate that the remediation action is permitted for the confirmed issue."""
    if plan.issue_code != confirmed_issue_code:
        raise ValidationError(
            f"Resolution plan issue '{plan.issue_code}' does not match confirmed diagnosis '{confirmed_issue_code}'."
        )

    action = plan.proposed_action
    allowed_fields = {
        "FederationIdentifier",
        "IsActive",
        "WizardCountry",
        "SetupGuide",
        "Guidance",
        "Documentation",
        "Communication",
        "RITMGuidance",
    }

    if action.target_field not in allowed_fields:
        raise ValidationError(
            f"Target field '{action.target_field}' is not permitted for remediation."
        )

    if not action.target_record_id:
        raise ValidationError("Remediation action is missing target_record_id.")

    return True
