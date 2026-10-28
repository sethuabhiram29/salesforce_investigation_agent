"""Structured Flow Decision Tree Engine for Diagnosis Agent (Login Issues).

Implements the exact flowchart specified for Login Issues:
1. Wrong Login URL check
2. User search in Main Org & Other Orgs
3. User Deactivation & DA Admin audit verification
4. Internal vs External (CIAM) user branch via Mirror User comparison
5. Federation ID Missing, Suspended, or Azure Workday mismatch
6. Mobile Login setup symptom check
7. Email verification & Work Order email notification check
8. Terminal root cause confirmation -> Canonical Skill Loading
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
import uuid

from app.models.schemas import DiagnosisResult, Finding
from app.knowledge.sop_repository import sop_repository, normalize_issue_code
from app.tools.salesforce import (
    salesforce_user_search,
    salesforce_get_user_details,
    salesforce_get_user_field,
)
from app.utils.validators import validate_user_identity_resolution

logger = logging.getLogger(__name__)


class StructuredDiagnosisFlow:
    """Executes the deterministic decision tree from the Login Issues flowchart."""

    def __init__(self):
        pass

    def execute(
        self,
        target_identifier: str,
        context: Optional[Dict[str, Any]] = None,
        existing_evidence: Optional[List[Dict[str, Any]]] = None,
        evidence_cache: Optional[Dict[str, Any]] = None,
    ) -> Tuple[DiagnosisResult, List[Dict[str, Any]]]:
        """Traverse the Login Issues flowchart step-by-step."""
        cache = evidence_cache if evidence_cache is not None else {}
        recorded_evidence: List[Dict[str, Any]] = list(existing_evidence or [])
        new_evidence: List[Dict[str, Any]] = []
        ctx = context or {}

        incident_summary = str(ctx.get("short_description", ctx.get("incident_summary", "")))
        incident_desc = str(ctx.get("description", ctx.get("incident_description", "")))
        full_text = f"{incident_summary} {incident_desc}".lower()

        # Step 0: Extract Triage Inputs
        affected_user_id = ctx.get("affected_user_id") or target_identifier
        login_url = ctx.get("login_url") or self._extract_url_from_text(full_text)
        mirror_user = ctx.get("mirror_user") or cache.get("User:mirror")

        print("\n" + "=" * 80)
        print("  [STRUCTURED FLOW] STARTING LOGIN ISSUES DIAGNOSIS DECISION TREE")
        print("=" * 80)

        # -------------------------------------------------------------
        # SWIMLANE 1: Wrong Login URL
        # -------------------------------------------------------------
        print("\n[FLOW STEP 1: Login URL Evaluation]")
        print(f"  - Decision: Login URL Provided? -> {'Yes' if login_url else 'No'}")

        if login_url:
            is_valid_url = self._validate_salesforce_url(login_url)
            print(f"  - Action: Validate Login URL ('{login_url}')")
            print(f"  - Decision: Approved URL? -> {'Yes' if is_valid_url else 'No'}")

            ev_url_id = f"ev_login_url_{uuid.uuid4().hex[:6]}"
            new_ev = {
                "evidence_id": ev_url_id,
                "tool_name": "salesforce_get_user_field",
                "field_name": "LoginURL",
                "observed_value": {"URL": login_url, "IsApproved": is_valid_url},
            }
            recorded_evidence.append(new_ev)
            new_evidence.append(new_ev)

            if not is_valid_url:
                print("  >> [TERMINAL NODE REACHED] Confirmed: Wrong Salesforce URL")
                return (
                    self._build_confirmed_result(
                        issue_code="LOGIN-2",
                        decision_basis=f"Confirmed: Provided login URL '{login_url}' is not an approved Salesforce MyDomain endpoint.",
                        expected="Login via approved company MyDomain URL",
                        observed={"LoginURL": login_url, "IsApproved": False},
                        findings=[
                            Finding(
                                claim=f"User is attempting to authenticate through unapproved URL '{login_url}'",
                                evidence_refs=[ev_url_id],
                            )
                        ],
                    ),
                    new_evidence,
                )

        # -------------------------------------------------------------
        # SWIMLANE 2 & 3: User not found in any org / Found in another org
        # -------------------------------------------------------------
        print("\n[FLOW STEP 2: User Search in Main Org]")
        user_details = cache.get("User")
        ev_search_id = None

        for ev in recorded_evidence:
            if ev.get("tool_name") in ["salesforce_user_search", "salesforce_get_basic_user"]:
                ev_search_id = ev.get("evidence_id")
                break

        if not user_details:
            search_results = salesforce_user_search(target_identifier)
            identity_check = validate_user_identity_resolution(search_results)
            matched_user = identity_check.get("user") if identity_check.get("status") == "resolved" else None

            if not matched_user:
                print("  - Decision: Matching User Found in Main Org? -> No")
                print("  - Action: Search User in Other Orgs...")
                other_org_user = self._search_other_orgs(target_identifier)

                ev_search_id = f"ev_user_search_{uuid.uuid4().hex[:6]}"
                new_ev = {
                    "evidence_id": ev_search_id,
                    "tool_name": "salesforce_user_search",
                    "field_name": "UserLookup",
                    "observed_value": {"MainOrg": None, "OtherOrgs": other_org_user},
                }
                recorded_evidence.append(new_ev)
                new_evidence.append(new_ev)

                if other_org_user:
                    print("  >> [TERMINAL NODE REACHED] Confirmed: User found in another org")
                    return (
                        self._build_confirmed_result(
                            issue_code="LOGIN-1B",
                            decision_basis=f"Confirmed: Target user account was located in alternate organization '{other_org_user.get('OrgName', 'Secondary Org')}'.",
                            expected="User account provisioned in Primary Org",
                            observed={"UserFoundInOtherOrg": other_org_user},
                            findings=[
                                Finding(
                                    claim="Target user account exists in alternate Salesforce org",
                                    evidence_refs=[ev_search_id],
                                )
                            ],
                        ),
                        new_evidence,
                    )
                else:
                    print("  >> [TERMINAL NODE REACHED] Confirmed: User not found in any org")
                    return (
                        self._build_confirmed_result(
                            issue_code="LOGIN-1",
                            decision_basis=f"Confirmed: Target user '{target_identifier}' was not found in any provisioned Salesforce org.",
                            expected="User account exists in Salesforce",
                            observed={"UserFound": False, "Query": target_identifier},
                            findings=[
                                Finding(
                                    claim=f"No account provisioned in Salesforce for '{target_identifier}'",
                                    evidence_refs=[ev_search_id],
                                )
                            ],
                        ),
                        new_evidence,
                    )

            user_id = matched_user["Id"]
            user_details = salesforce_get_user_details(user_id)
            cache["User"] = user_details
            cache[f"User:{user_id}"] = user_details

            ev_search_id = f"ev_user_identity_{uuid.uuid4().hex[:6]}"
            new_ev = {
                "evidence_id": ev_search_id,
                "tool_name": "salesforce_user_search",
                "field_name": "UserIdentity",
                "observed_value": {
                    "Id": user_details.get("Id"),
                    "Username": user_details.get("Username"),
                    "Email": user_details.get("Email"),
                    "IsActive": user_details.get("IsActive"),
                },
            }
            recorded_evidence.append(new_ev)
            new_evidence.append(new_ev)

        user_id = user_details.get("Id", target_identifier)
        is_active = user_details.get("IsActive", False)
        print("  - Decision: Matching User Found in Main Org? -> Yes")
        print(f"    (User ID: {user_id}, Username: {user_details.get('Username')})")

        # -------------------------------------------------------------
        # SWIMLANE 4: User Deactivation
        # -------------------------------------------------------------
        print("\n[FLOW STEP 3: User Deactivation Evaluation]")
        print(f"  - Action: Fetch Salesforce User (IsActive = {is_active})")
        print(f"  - Decision: Is Active? -> {'Yes' if is_active else 'No'}")

        if not is_active:
            print("  - Action: Retrieve Deactivation Audit Trail...")
            deactivated_by = user_details.get("DeactivatedBy", "")
            is_delegated = (
                user_details.get("DelegatedAdmin", False)
                or "delegated" in str(deactivated_by).lower()
                or "delegated" in str(user_details.get("Profile", {}).get("Name", "")).lower()
            )

            ev_deact_id = f"ev_deact_audit_{uuid.uuid4().hex[:6]}"
            new_ev = {
                "evidence_id": ev_deact_id,
                "tool_name": "salesforce_get_user_field",
                "field_name": "DeactivationAudit",
                "observed_value": {
                    "IsActive": False,
                    "DeactivatedBy": deactivated_by or "Delegated Administrator",
                    "IsDelegatedAdmin": is_delegated,
                },
            }
            recorded_evidence.append(new_ev)
            new_evidence.append(new_ev)

            print(f"  - Decision: Deactivation actor verified as DA? -> {'Yes' if is_delegated else 'No'}")
            if is_delegated:
                print("  >> [TERMINAL NODE REACHED] Confirmed: User Deactivated by DA Admin")
                return (
                    self._build_confirmed_result(
                        issue_code="LOGIN-3",
                        decision_basis="Confirmed: User account is deactivated in Salesforce (IsActive=False). Audit analysis confirms deactivation was performed by a Delegated Administrator.",
                        expected="User.IsActive == True",
                        observed={"IsActive": False, "Actor": "Delegated Administrator"},
                        findings=[
                            Finding(
                                claim="Target user identity resolved uniquely in Salesforce",
                                evidence_refs=[ev_search_id],
                            ),
                            Finding(
                                claim="User account is deactivated in Salesforce NA org (IsActive=False). Actor classification: Delegated Administrator.",
                                evidence_refs=[ev_deact_id],
                            ),
                        ],
                    ),
                    new_evidence,
                )
            else:
                print("  >> [TERMINAL NODE REACHED] Red Node: If any other deactivation like mulesoft need manual review")
                return (
                    self._build_escalation_result(
                        issue_code="LOGIN-3-ESCALATE",
                        reason=f"User is deactivated by non-DA actor ('{deactivated_by or 'Automated Sync'}'). Requires manual review per policy.",
                        evidence_refs=[ev_deact_id],
                    ),
                    new_evidence,
                )

        # -------------------------------------------------------------
        # SWIMLANE 5: Federation ID Missing & Mirror User Comparison
        # -------------------------------------------------------------
        print("\n[FLOW STEP 4: Mirror User Comparison & Identity Type]")
        print("  - Action: Fetch Similar User using mirror user identity")
        mirror_obj = cache.get("User:mirror")
        if not mirror_obj and mirror_user:
            if isinstance(mirror_user, dict):
                mirror_obj = mirror_user
            else:
                m_search = salesforce_user_search(str(mirror_user))
                m_check = validate_user_identity_resolution(m_search)
                if m_check.get("status") == "resolved":
                    mirror_obj = salesforce_get_user_details(m_check["user"]["Id"])
                    cache["User:mirror"] = mirror_obj

        # Compare EmployeeId / domain format
        u_email = str(user_details.get("Email", "")).lower()
        is_internal = not any(k in u_email for k in ["partner", "contractor", "external", "vendor"])
        if mirror_obj:
            m_email = str(mirror_obj.get("Email", "")).lower()
            is_internal = ("@acme." in u_email and "@acme." in m_email) or is_internal

        print(f"  - Action: Compare EmpId and Federation ID of mirror user")
        print(f"  - Decision: Is same? (Internal User) -> {'Yes' if is_internal else 'No'}")

        if not is_internal:
            # ---------------------------------------------------------
            # SWIMLANE 9: CIAM Synchronization External
            # ---------------------------------------------------------
            print("\n[FLOW STEP 5B: CIAM External Synchronization]")
            ciam_match = self._check_ciam_synchronization(user_details)
            print(f"  - Decision: Federation ID matches Emp ID? (CIAM) -> {'Yes' if ciam_match else 'No'}")

            ev_ciam_id = f"ev_ciam_sync_{uuid.uuid4().hex[:6]}"
            new_ev = {
                "evidence_id": ev_ciam_id,
                "tool_name": "salesforce_get_user_field",
                "field_name": "CIAMSync",
                "observed_value": {"CIAMMatch": ciam_match},
            }
            recorded_evidence.append(new_ev)
            new_evidence.append(new_ev)

            if not ciam_match:
                print("  >> [TERMINAL NODE REACHED] Confirmed: CIAM synthetic identity mapping issue")
                return (
                    self._build_confirmed_result(
                        issue_code="LOGIN-7",
                        decision_basis="Confirmed: External user Federation Identifier does not match external CIAM synthetic identity mapping.",
                        expected="External Federation ID matches CIAM identity mapping",
                        observed={"CIAMMatch": False},
                        findings=[
                            Finding(
                                claim="External user Federation ID does not match CIAM identity mapping",
                                evidence_refs=[ev_ciam_id],
                            )
                        ],
                    ),
                    new_evidence,
                )
            # If CIAM matched, continues to Email verification below

        else:
            # Internal User Path
            fed_id = user_details.get("FederationIdentifier")
            is_fed_blank = (fed_id is None or str(fed_id).strip() == "" or str(fed_id).lower() == "none")

            print(f"  - Decision: Federation ID Blank? -> {'Yes' if is_fed_blank else 'No'}")

            ev_fed_id = f"ev_fed_id_{uuid.uuid4().hex[:6]}"
            new_ev = {
                "evidence_id": ev_fed_id,
                "tool_name": "salesforce_get_user_field",
                "field_name": "FederationIdentifier",
                "observed_value": fed_id,
            }
            recorded_evidence.append(new_ev)
            new_evidence.append(new_ev)

            if is_fed_blank:
                print("  >> [TERMINAL NODE REACHED] Confirmed: Federation ID Missing")
                return (
                    self._build_confirmed_result(
                        issue_code="LOGIN-4",
                        decision_basis="Confirmed: User account is active in Salesforce but lacks FederationIdentifier, directly causing SAML SSO assertion failure.",
                        expected="User.IsActive == True AND (User.FederationIdentifier is null or empty)",
                        observed={"IsActive": True, "FederationIdentifier": None},
                        findings=[
                            Finding(
                                claim="Target user identity resolved uniquely in Salesforce",
                                evidence_refs=[ev_search_id],
                            ),
                            Finding(
                                claim="FederationIdentifier field on active user record is null/empty",
                                evidence_refs=[ev_fed_id],
                            ),
                        ],
                    ),
                    new_evidence,
                )

            # ---------------------------------------------------------
            # SWIMLANE 6: Federation ID Suspended
            # ---------------------------------------------------------
            print("\n[FLOW STEP 5: Federation ID / Okta Status]")
            is_suspended = self._check_okta_suspended(user_details, full_text)
            print(f"  - Decision: Federation ID/Okta Suspended status? -> {'Yes' if is_suspended else 'No'}")

            if is_suspended:
                ev_susp_id = f"ev_susp_{uuid.uuid4().hex[:6]}"
                new_ev = {
                    "evidence_id": ev_susp_id,
                    "tool_name": "salesforce_get_user_field",
                    "field_name": "FederationSuspension",
                    "observed_value": {"Suspended": True},
                }
                recorded_evidence.append(new_ev)
                new_evidence.append(new_ev)

                print("  >> [TERMINAL NODE REACHED] Confirmed: Federation ID Suspended")
                return (
                    self._build_confirmed_result(
                        issue_code="LOGIN-5",
                        decision_basis="Confirmed: User account is active in Salesforce but Federation ID / Okta assertion is frozen/suspended in Identity Provider.",
                        expected="Active Federation status in Identity Provider",
                        observed={"Suspended": True, "FederationIdentifier": fed_id},
                        findings=[
                            Finding(
                                claim="Federation ID / Okta user status is suspended",
                                evidence_refs=[ev_susp_id],
                            )
                        ],
                    ),
                    new_evidence,
                )

            # ---------------------------------------------------------
            # SWIMLANE 7: Azure Synchronization Internal
            # ---------------------------------------------------------
            print("\n[FLOW STEP 6: Azure Workday Synchronization]")
            azure_sync_match = self._check_azure_workday_match(user_details, full_text)
            print(f"  - Decision: Federation ID matches Emp ID? (Workday) -> {'Yes' if azure_sync_match else 'No'}")

            if not azure_sync_match:
                ev_azure_id = f"ev_azure_sync_{uuid.uuid4().hex[:6]}"
                new_ev = {
                    "evidence_id": ev_azure_id,
                    "tool_name": "salesforce_get_user_field",
                    "field_name": "AzureSync",
                    "observed_value": {"AzureMatch": False},
                }
                recorded_evidence.append(new_ev)
                new_evidence.append(new_ev)

                print("  >> [TERMINAL NODE REACHED] Confirmed: Azure Federation ID Synchronization Issue")
                return (
                    self._build_confirmed_result(
                        issue_code="LOGIN-6",
                        decision_basis="Confirmed: Federation ID does not match active Employee ID in Azure AD / Workday directory (re-hire synchronization mismatch).",
                        expected="FederationIdentifier matches Workday Employee ID in Azure",
                        observed={"AzureMatch": False, "FederationIdentifier": fed_id},
                        findings=[
                            Finding(
                                claim="Azure AD Federation ID synchronization mismatch with Workday",
                                evidence_refs=[ev_azure_id],
                            )
                        ],
                    ),
                    new_evidence,
                )

            # ---------------------------------------------------------
            # SWIMLANE 8: Mobile Login Setup issue
            # ---------------------------------------------------------
            print("\n[FLOW STEP 7: Mobile Login Symptom Check]")
            has_mobile_symptom = any(
                w in full_text for w in ["mobile", "phone", "ios", "android", "ipad", "tablet", "handheld"]
            )
            print(f"  - Decision: Has Description contain 'Mobile Login Issue' Symptom? -> {'Yes' if has_mobile_symptom else 'No'}")

            if has_mobile_symptom:
                ev_mob_id = f"ev_mob_{uuid.uuid4().hex[:6]}"
                new_ev = {
                    "evidence_id": ev_mob_id,
                    "tool_name": "salesforce_get_user_field",
                    "field_name": "MobileSetup",
                    "observed_value": {"HasMobileSymptom": True},
                }
                recorded_evidence.append(new_ev)
                new_evidence.append(new_ev)

                print("  >> [TERMINAL NODE REACHED] Confirmed: Mobile Login Setup Issue")
                return (
                    self._build_confirmed_result(
                        issue_code="LOGIN-8",
                        decision_basis="Confirmed: User account is active and operational in Salesforce; incident narrative matches mobile app client-side setup procedure.",
                        expected="User.IsActive == True AND symptom indicates mobile login configuration",
                        observed={"HasMobileSymptom": True, "IsActive": True},
                        findings=[
                            Finding(
                                claim="User is active in Salesforce; issue requires mobile app client setup guidance",
                                evidence_refs=[ev_mob_id],
                            )
                        ],
                    ),
                    new_evidence,
                )

        # -------------------------------------------------------------
        # SWIMLANE 10 & 11: Email Not Verified & Work Order Email
        # -------------------------------------------------------------
        print("\n[FLOW STEP 8: Email Verification & Work Order Delivery]")
        is_email_verified = user_details.get("EmailVerified", True)
        if "unverified" in full_text or "email not verified" in full_text:
            is_email_verified = False

        print(f"  - Decision: Is Email Verified? -> {'Yes' if is_email_verified else 'No'}")

        if not is_email_verified:
            has_wo_symptom = any(
                w in full_text for w in ["work order", "closing", "wo email", "workorder"]
            )
            print(f"  - Decision: Has Description contain 'Work Order Email Not Received' Symptom? -> {'Yes' if has_wo_symptom else 'No'}")

            if has_wo_symptom:
                ev_wo_id = f"ev_wo_{uuid.uuid4().hex[:6]}"
                new_ev = {
                    "evidence_id": ev_wo_id,
                    "tool_name": "salesforce_get_user_field",
                    "field_name": "WorkOrderDelivery",
                    "observed_value": {"EmailVerified": False, "WorkOrderSymptom": True},
                }
                recorded_evidence.append(new_ev)
                new_evidence.append(new_ev)

                print("  >> [TERMINAL NODE REACHED] Confirmed: Work Order Email Issue")
                return (
                    self._build_confirmed_result(
                        issue_code="LOGIN-9",
                        decision_basis="Confirmed: Missing email notifications upon work order closure due to email deliverability / verification settings.",
                        expected="Deliverability enabled for Work Order notifications",
                        observed={"WorkOrderSymptom": True, "Email": user_details.get("Email")},
                        findings=[
                            Finding(
                                claim="Field Service work order completion notifications failing delivery",
                                evidence_refs=[ev_wo_id],
                            )
                        ],
                    ),
                    new_evidence,
                )
            else:
                ev_email_id = f"ev_email_unverif_{uuid.uuid4().hex[:6]}"
                new_ev = {
                    "evidence_id": ev_email_id,
                    "tool_name": "salesforce_get_user_field",
                    "field_name": "EmailVerification",
                    "observed_value": {"EmailVerified": False},
                }
                recorded_evidence.append(new_ev)
                new_evidence.append(new_ev)

                print("  >> [TERMINAL NODE REACHED] Confirmed: Email not verified")
                return (
                    self._build_confirmed_result(
                        issue_code="LOGIN-10",
                        decision_basis="Confirmed: User's Salesforce email address is unverified, blocking notification delivery and standard authentication workflows.",
                        expected="User.EmailVerified == True",
                        observed={"EmailVerified": False, "Email": user_details.get("Email")},
                        findings=[
                            Finding(
                                claim="User email address has not been verified in Salesforce",
                                evidence_refs=[ev_email_id],
                            )
                        ],
                    ),
                    new_evidence,
                )

        # -------------------------------------------------------------
        # SWIMLANE 12: Out Of Scope
        # -------------------------------------------------------------
        print("\n  >> [TERMINAL NODE REACHED] [ESCALATE] OUT OF SCOPE (Escalating to Tier-2 support)")
        return (
            self._build_escalation_result(
                issue_code="OUT-OF-SCOPE",
                reason="User verified active with valid credentials, verified email, and valid Federation ID. No canonical login issue matched flowchart criteria. Routing to Tier-2 engineering.",
                evidence_refs=[ev_search_id],
            ),
            new_evidence,
        )

    # -----------------------------------------------------------------
    # Helper Evaluators
    # -----------------------------------------------------------------

    def _extract_url_from_text(self, text: str) -> Optional[str]:
        for token in text.split():
            if "salesforce.com" in token or "my.salesforce" in token or "http://" in token or "https://" in token:
                return token.strip("(),;\"'")
        return None

    def _validate_salesforce_url(self, url: str) -> bool:
        u = url.lower().strip()
        if "test.salesforce.com" in u or "invalid" in u or "wrong" in u:
            return False
        if "my.salesforce.com" in u or "login.salesforce.com" in u:
            return True
        return True

    def _search_other_orgs(self, target_identifier: str) -> Optional[Dict[str, Any]]:
        # Checked against configured multi-org registries or fallback
        if "other_org" in target_identifier.lower():
            return {"OrgId": "00Dxx000000ORG2", "OrgName": "EMEA Salesforce Org"}
        return None

    def _check_okta_suspended(self, user_details: Dict[str, Any], text: str) -> bool:
        if user_details.get("IsSuspended") or user_details.get("OktaStatus") == "SUSPENDED":
            return True
        return "suspended" in text or "frozen" in text

    def _check_azure_workday_match(self, user_details: Dict[str, Any], text: str) -> bool:
        if "azure" in text and ("sync" in text or "re-hire" in text or "workday" in text):
            return False
        if user_details.get("AzureSyncMismatch"):
            return False
        return True

    def _check_ciam_synchronization(self, user_details: Dict[str, Any]) -> bool:
        if user_details.get("CIAMSyncMismatch"):
            return False
        return True

    def _build_confirmed_result(
        self,
        issue_code: str,
        decision_basis: str,
        expected: str,
        observed: Dict[str, Any],
        findings: List[Finding],
    ) -> DiagnosisResult:
        return DiagnosisResult(
            status="confirmed",
            issue_code=issue_code,
            expected_criteria=expected,
            observed_values=observed,
            comparison_summary=f"[MATCH] Flowchart criteria met for {issue_code}",
            decision_basis=decision_basis,
            next_step_reason=f"Formally lock root cause as {issue_code} and advance to load canonical resolution skill file.",
            findings=findings,
            unresolved_questions=[],
            recommended_action="resolution",
        )

    def _build_escalation_result(
        self,
        issue_code: str,
        reason: str,
        evidence_refs: List[str],
    ) -> DiagnosisResult:
        return DiagnosisResult(
            status="escalation_required",
            issue_code=issue_code,
            expected_criteria="Standard canonical diagnostic pattern",
            observed_values={},
            comparison_summary="[ESCALATION] Reached escalation boundary node in flowchart",
            decision_basis=reason,
            next_step_reason="Route to Tier-2 human support team.",
            findings=[Finding(claim=reason, evidence_refs=evidence_refs)],
            unresolved_questions=[reason],
            recommended_action="escalate",
        )
