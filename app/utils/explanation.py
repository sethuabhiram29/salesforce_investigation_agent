"""Human-friendly narrative explanation generator for Salesforce investigations.

Converts technical diagnostics, evidence payloads, and graph traversal steps
into clear, persuasive, plain-English explanations suitable for both technical
and non-technical stakeholders (no raw JSON blobs).
"""

from typing import Any, Dict, List, Optional, Tuple
from app.knowledge.sop_repository import sop_repository, normalize_issue_code


def format_evidence_to_human_english(ev: Dict[str, Any]) -> str:
    """Translate raw Salesforce tool output into a concise, human-readable English summary."""
    tool = ev.get("tool_name", "")
    obs = ev.get("observed_value")
    raw = ev.get("raw_output")
    data = obs if obs is not None else raw

    if tool == "salesforce_get_user_details":
        if isinstance(data, dict):
            name = data.get("Name") or f"{data.get('FirstName', '')} {data.get('LastName', '')}".strip() or "User"
            email = data.get("Email") or data.get("Username") or "Unknown"
            uid = data.get("Id", "N/A")
            is_active = "Active" if data.get("IsActive") else "Deactivated"
            profile = data.get("ProfileName") or (data.get("Profile", {}).get("Name") if isinstance(data.get("Profile"), dict) else data.get("ProfileId")) or "Standard Profile"
            fed_id = data.get("FederationIdentifier")
            fed_id_str = f"'{fed_id}'" if fed_id else "None (Blank / Unassigned)"
            role = data.get("RoleName") or data.get("UserRoleId") or "None Assigned"
            delegated = "Yes" if data.get("DelegatedAdmin") else "No"
            return (
                f"Retrieved live Salesforce User record for **{name}** (`{email}`, ID: `{uid}`). "
                f"Account status is **{is_active}** (IsActive = {data.get('IsActive')}), Profile is **'{profile}'**, "
                f"Role is **'{role}'**, SSO Federation ID is **{fed_id_str}**, and Delegated Admin is **{delegated}**."
            )
        return "Retrieved user details from Salesforce org."

    elif tool == "salesforce_user_search":
        query = ev.get("query", "target user")
        if isinstance(data, list) and len(data) > 0:
            u = data[0]
            name = u.get("Name") or u.get("Username") or "User"
            email = u.get("Email") or u.get("Username") or ""
            uid = u.get("Id", "")
            return f"Searched Salesforce for '{query}' and located user **{name}** (`{email}`, ID: `{uid}`)."
        elif isinstance(data, list) and len(data) == 0:
            return f"Searched Salesforce for '{query}' and found **zero** matching user accounts in the organization."
        return f"Searched Salesforce for '{query}'."

    elif tool == "salesforce_get_object_permissions":
        obj = ev.get("field_name") or "Object"
        if isinstance(data, dict):
            r = "Yes" if data.get("PermissionsRead") else "No"
            c = "Yes" if data.get("PermissionsCreate") else "No"
            e = "Yes" if data.get("PermissionsEdit") else "No"
            d = "Yes" if data.get("PermissionsDelete") else "No"
            return (
                f"Checked object-level security permissions for **{obj}** in Salesforce. "
                f"Permissions: Read = **{r}**, Create = **{c}**, Edit = **{e}**, Delete = **{d}**."
            )
        return f"Checked object permissions on {obj}."

    elif tool == "salesforce_get_record_access":
        rec_id = ev.get("field_name") or "Record"
        if isinstance(data, dict):
            r = "Yes" if data.get("HasReadAccess") else "No"
            e = "Yes" if data.get("HasEditAccess") else "No"
            t = "Yes" if data.get("HasTransferAccess") else "No"
            return (
                f"Checked row-level sharing access on record `{rec_id}`. "
                f"Access rights: Read = **{r}**, Edit = **{e}**, Transfer = **{t}**."
            )
        return f"Checked record-level access on {rec_id}."

    elif tool == "salesforce_compare_user_access":
        return "Compared affected user permissions against the comparative peer (mirror user) baseline."

    elif tool == "salesforce_get_user_permission_sets":
        ps_count = len(data) if isinstance(data, list) else 0
        return f"Retrieved assigned Permission Sets from Salesforce ({ps_count} permission sets assigned)."

    elif tool == "salesforce_get_contact_wizard_details":
        return "Retrieved Contact Wizard and country configuration details from Salesforce."

    return f"Executed tool `{tool}` and recorded evidence in the investigation audit trail."


def format_observed_values_to_human_english(issue_code: str, obs_vals: Dict[str, Any]) -> str:
    """Format observed values dictionary into a clean, human-readable English statement."""
    if not obs_vals:
        return "No specific attributes observed."

    parts = []
    if "user_found" in obs_vals:
        if obs_vals["user_found"]:
            uid = obs_vals.get("Id", "")
            parts.append(f"User account exists in Salesforce (ID: {uid})")
        else:
            parts.append("User account does not exist in Salesforce (0 records returned)")

    if "IsActive" in obs_vals:
        act_str = "Active" if obs_vals["IsActive"] else "Deactivated"
        parts.append(f"Account Status is {act_str} (IsActive = {obs_vals['IsActive']})")

    if "FederationIdentifier" in obs_vals:
        fid = obs_vals["FederationIdentifier"]
        if fid is None or str(fid).strip() == "":
            parts.append("Federation Identifier (SSO ID) is blank / null")
        else:
            parts.append(f"Federation Identifier is assigned as '{fid}'")

    if "DelegatedAdmin" in obs_vals:
        del_str = "is a Delegated Admin" if obs_vals["DelegatedAdmin"] else "is not a Delegated Admin"
        parts.append(f"User {del_str}")

    if "PermissionsEdit" in obs_vals:
        target_obj = obs_vals.get("TargetObject", "Object")
        p_edit = "Granted" if obs_vals["PermissionsEdit"] else "Missing / Denied"
        parts.append(f"Edit permission on {target_obj} is {p_edit} (PermissionsEdit = {obs_vals['PermissionsEdit']})")

    if "HasReadAccess" in obs_vals or "HasEditAccess" in obs_vals:
        rec_id = obs_vals.get("RecordId", "Record")
        hr = "Granted" if obs_vals.get("HasReadAccess") else "Denied"
        he = "Granted" if obs_vals.get("HasEditAccess") else "Denied"
        parts.append(f"Sharing on {rec_id}: Read is {hr}, Edit is {he}")

    if "Username" in obs_vals and "Email" in obs_vals:
        parts.append(f"Username: {obs_vals.get('Username')}")

    if not parts:
        # Fallback to key-value pairs formatted cleanly
        clean_items = [f"{k}: {v}" for k, v in obs_vals.items() if not str(k).startswith("_")]
        return ", ".join(clean_items)

    return "; ".join(parts) + "."


def generate_step_narrative_explanation(
    issue_code: str,
    domain: str,
    status: str,
    observed_values: Dict[str, Any],
    expected_criteria: str,
    target_identifier: str,
    user_details: Optional[Dict[str, Any]] = None,
    hist_match: Optional[Tuple[str, str, float]] = None,
    rank_idx: int = 1,
    next_cand_str: str = "",
    decision_basis: Optional[str] = None,
    comparison_summary: Optional[str] = None,
) -> Dict[str, str]:
    """Generate a cohesive, human-friendly English narrative explaining the diagnostic step.
    
    Written conversationally as if explaining and reasoning to a human colleague.
    """
    user_det = user_details or {}
    user_name = user_det.get("Name") or user_det.get("Username") or target_identifier
    is_active = user_det.get("IsActive", False)
    fed_id = user_det.get("FederationIdentifier")
    fed_id_str = f"'{fed_id}'" if fed_id else "None (Blank)"
    delegated = user_det.get("DelegatedAdmin", False)

    sop_data = sop_repository.get_sop(issue_code) or sop_repository.get_sop(normalize_issue_code(issue_code))

    # 1. Why was this step taken?
    if hist_match:
        hist_code, hist_desc, hist_sim = hist_match
        sim_pct = int(hist_sim * 100)
        why_step_taken = (
            f"Candidate #{rank_idx} ({issue_code}) was selected directly from historical incident precedents "
            f"filtered in the '{domain}' domain ('{hist_desc}', similarity: {sim_pct}%). We are evaluating historical "
            f"precedents top-to-bottom based on similarity to check if our ticket shares the same confirmed root cause."
        )
    else:
        why_step_taken = (
            f"Candidate #{rank_idx} ({issue_code}) was selected to systematically evaluate the remaining known root causes "
            f"in the '{domain}' domain catalog after earlier hypotheses were examined."
        )

    # 2. What did we do in this step?
    titles = {
        "LOGIN-1": "User Account Availability in Salesforce",
        "LOGIN-2": "Salesforce Login URL Endpoint Verification",
        "LOGIN-3": "User Account Deactivation Status",
        "LOGIN-3A": "Delegated Administrator Account Deactivation",
        "LOGIN-4": "Single Sign-On (SAML) Federation Identifier Configuration",
        "LOGIN-5": "Federation Identifier Suspension in Identity Provider",
        "LOGIN-6": "Identity Provider Sync (Azure Re-hire)",
        "LOGIN-7": "External User CIAM Federation Sync",
        "LOGIN-8": "Salesforce Mobile App Client Authentication Handshake",
        "LOGIN-9": "Field Service Work Order Email Notification Delivery",
        "OBJECT-1": "Object-Level Edit Permissions on Target Object",
        "OBJECT-2": "Object Permission Discrepancy Compared to Mirror User Baseline",
        "RECORD-3": "Row-Level Record Access and Sharing Rules",
        "APPLICATION-1": "CC360 Connected App Portal Permission Set License",
    }
    scenario_title = (sop_data.get("description") if sop_data else None) or titles.get(issue_code, f"Candidate Scenario {issue_code}")
    what_we_did = f"Investigated '{scenario_title}' ({issue_code}) against the live Salesforce User record for {user_name}."

    # 3. Live Salesforce Evidence Checked (Plain English)
    evidence_english = format_observed_values_to_human_english(issue_code, observed_values)

    # 4. Expected vs Observed Comparison
    if comparison_summary:
        comparison_english = comparison_summary
    elif status == "confirmed":
        comparison_english = (
            f"All confirmation criteria for {issue_code} matched the live Salesforce evidence. "
            f"Expected: {expected_criteria}. Observed: {evidence_english}"
        )
    elif status == "contradicted":
        comparison_english = (
            f"Evidence contradicted hypothesis {issue_code}. "
            f"Expected: {expected_criteria}, but observed: {evidence_english}"
        )
    else:
        comparison_english = (
            f"Current Salesforce evidence is inconclusive for {issue_code}. "
            f"Requires external diagnostic logs to prove or disprove."
        )

    # 5. Convincing Analytical Reasoning (Prioritize Grounded Decision Basis)
    if decision_basis:
        reasoning = decision_basis
    elif issue_code == "LOGIN-1":
        if status == "contradicted":
            reasoning = (
                f"We searched Salesforce for '{target_identifier}' and located a provisioned user account "
                f"(ID: {user_det.get('Id', 'found')}). Because the user account is clearly present in Salesforce, "
                f"the problem cannot be an uncreated or missing account. This conclusively disproves LOGIN-1."
            )
        else:
            reasoning = (
                f"We searched Salesforce for '{target_identifier}' and found zero matching user records in the org. "
                f"Because the user account does not exist, the user cannot sign in. This confirms LOGIN-1."
            )
    elif issue_code in ["LOGIN-3", "LOGIN-3A"]:
        actor = observed_values.get("deactivation_actor") or ("Delegated Administrator" if delegated else "Standard Admin")
        if not is_active:
            if actor == "Delegated Administrator":
                reasoning = (
                    f"The live Salesforce User record shows that the user's account is deactivated (IsActive = False). "
                    f"Audit analysis confirms the deactivation was performed by a Delegated Administrator. "
                    f"Per security policy SOP LOGIN-003, automated direct reactivation is prohibited; the caller must be notified "
                    f"to raise a Manage User RITM in ServiceNow to obtain authorized approvals. This confirms LOGIN-3 (User Account Deactivated)."
                )
            elif actor == "Mulesoft":
                reasoning = (
                    f"The live Salesforce User record shows that the user's account is deactivated (IsActive = False). "
                    f"Audit records indicate deactivation originated through automated Mulesoft integration sync. "
                    f"This confirms LOGIN-3 (User Account Deactivated via Mulesoft)."
                )
            else:
                reasoning = (
                    f"The live Salesforce User record shows that the user's account is deactivated (IsActive = False). "
                    f"In Salesforce, an inactive account immediately terminates login processing at the server gateway before any "
                    f"SSO or credential check is performed. This confirms LOGIN-3 (User Account Deactivated) as the exact root cause."
                )
        else:
            reasoning = (
                f"The user's account is currently active in Salesforce (IsActive = True). Because active accounts are permitted "
                f"at the gateway, account deactivation cannot explain the issue. This disproves LOGIN-3."
            )
    elif issue_code == "LOGIN-4":
        if status == "confirmed":
            reasoning = (
                f"The user account is active in Salesforce (IsActive = True), meaning authentication reaches the SSO stage. "
                f"However, the FederationIdentifier field is completely blank. When Okta sends the SAML assertion, "
                f"Salesforce requires a matching FederationIdentifier to associate the assertion with this user. Because it is "
                f"missing, Salesforce rejects the login. This confirms LOGIN-4 as the exact root cause."
            )
        elif not is_active:
            reasoning = (
                f"The user account is deactivated in Salesforce (IsActive = False). Inactive accounts are blocked at the central "
                f"gateway before any SSO token or Federation ID is evaluated. Therefore, missing Federation ID is disproven as "
                f"the root cause in favor of account deactivation."
            )
        else:
            reasoning = (
                f"The FederationIdentifier field is already populated with '{fed_id}'. Because the SSO identifier is present, "
                f"a missing Federation ID cannot be the cause. This disproves LOGIN-4."
            )
    elif issue_code in ["OBJECT-1", "OBJECT-2"]:
        if status == "confirmed":
            reasoning = (
                f"Queried object permissions on the requested object and confirmed that PermissionsEdit is False. "
                f"Lacking Edit permission directly causes the 'Insufficient Privileges' error when modifying records of this type. "
                f"This confirms {issue_code} as the root cause."
            )
        else:
            reasoning = (
                f"User already holds PermissionsEdit on the target object. Object-level permission is not the blocker. "
                f"This disproves {issue_code}."
            )
    elif issue_code in ["RECORD-3", "RECORD-2"]:
        if status == "confirmed":
            reasoning = (
                f"Queried row-level sharing access and found the user lacks Read or Edit permissions on the target record. "
                f"This explains why Salesforce threw an Insufficient Privileges error on this specific record."
            )
        else:
            reasoning = (
                f"User already has row-level access to the target record, or no specific record ID was identified in the incident. "
                f"This disproves record-level sharing as the root cause."
            )
    elif sop_data:
        sop_desc = sop_data.get("description", issue_code)
        sop_res = sop_data.get("resolution_steps", "")
        if status == "confirmed":
            reasoning = f"Analysis of canonical SOP ('{sop_desc}') confirms root cause as {issue_code}. Live Salesforce evidence satisfies all criteria. Resolution: {sop_res[:120]}."
        else:
            reasoning = f"Evaluated candidate SOP ('{sop_desc}') against live Salesforce evidence. Observed evidence ({evidence_english}) contradicts {issue_code} criteria."
    else:
        reasoning = (
            f"Evaluated candidate {issue_code} against live Salesforce evidence. Resulting status: {status.upper()}."
        )

    # 6. Next Step Action & Reason
    if status == "confirmed":
        next_step_action = (
            f"Root cause locked as {issue_code}. Advancing along directed edge to the formal Root Cause Confirmation gate, "
            f"before entering the Resolution Planning stage to load the canonical skill file and formulate remediation fields."
        )
    elif status == "contradicted":
        next_step_action = (
            f"Candidate {issue_code} contradicted by live Salesforce evidence. Advancing along directed edge to evaluate the "
            f"next candidate ({next_cand_str}) without loading skill files."
        )
    else:
        next_step_action = (
            f"Insufficient evidence for {issue_code}. Advancing along directed edge to evaluate the next candidate ({next_cand_str})."
        )

    return {
        "what_we_did": what_we_did,
        "why_step_taken": why_step_taken,
        "evidence_english": evidence_english,
        "comparison_english": comparison_english,
        "reasoning": reasoning,
        "next_step_action": next_step_action,
    }
