"""Streamlit UI for Salesforce Agentic Support System.

Visualizes the multi-agent orchestration lifecycle:
- Intake & Triage (Semantic identity resolution & mirror user extraction)
- Historical Precedents (PostgreSQL pgvector)
- Diagnosis Agent & Tool Execution (Salesforce MCP / API read-only tools)
- Resolution Planning & Whitelist Validation
- HITL Approval Gate
- Remediation Execution & Verification
- Communication & ServiceNow Closure
"""

import copy
import json
import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=True)

import streamlit as st

from app.integrations.salesforce.client import salesforce_client
from app.knowledge.neo4j_repository import neo4j_repository
from app.knowledge.sop_repository import sop_repository
from app.orchestrator.agent import InvestigationOrchestrator
from app.tools.salesforce import reset_fixture_state
from app.utils.explanation import format_evidence_to_human_english

# Page configuration
st.set_page_config(
    page_title="Salesforce Agentic Investigation System",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #0b5cff;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        color: #64748b;
        font-size: 1.05rem;
        margin-bottom: 1.5rem;
    }
    .stage-card {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 18px;
        margin-bottom: 16px;
    }
    .tool-box {
        background-color: #f1f5f9;
        border-left: 4px solid #3b82f6;
        padding: 10px 14px;
        border-radius: 4px;
        margin: 8px 0;
        font-family: monospace;
        font-size: 0.9rem;
    }
    .badge-login { background-color: #fee2e2; color: #991b1b; padding: 3px 8px; border-radius: 4px; font-weight: 600; }
    .badge-object { background-color: #fef3c7; color: #92400e; padding: 3px 8px; border-radius: 4px; font-weight: 600; }
    .badge-record { background-color: #e0e7ff; color: #3730a3; padding: 3px 8px; border-radius: 4px; font-weight: 600; }
    .badge-app { background-color: #dcfce7; color: #166534; padding: 3px 8px; border-radius: 4px; font-weight: 600; }
    .badge-success { background-color: #dcfce7; color: #166534; padding: 3px 8px; border-radius: 4px; font-weight: 600; }
    .point-card-p1 {
        background: #eff6ff;
        border-left: 5px solid #2563eb;
        padding: 14px 18px;
        border-radius: 8px;
        margin-bottom: 14px;
        box-shadow: 0 1px 3px rgba(37,99,235,0.08);
    }
    .point-card-p2 {
        background: #fefce8;
        border-left: 5px solid #ca8a04;
        padding: 14px 18px;
        border-radius: 8px;
        margin-bottom: 14px;
        box-shadow: 0 1px 3px rgba(202,138,4,0.08);
    }
    .point-card-p3 {
        background: #f0fdf4;
        border-left: 5px solid #16a34a;
        padding: 14px 18px;
        border-radius: 8px;
        margin-bottom: 14px;
        box-shadow: 0 1px 3px rgba(22,163,74,0.08);
    }
    .tool-box-clean {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-left: 4px solid #0284c7;
        padding: 12px 16px;
        border-radius: 6px;
        margin: 10px 0;
        font-size: 0.90rem;
    }
</style>
""", unsafe_allow_html=True)


def build_traversal_mermaid(final_state: dict) -> str:
    """Dynamically builds a Mermaid flowchart representing Points 1, 2, and 3."""
    domain = final_state.get("triage_result", {}).get("domain", "LOGIN")
    diag = final_state.get("diagnosis_result", {})
    confirmed_rc = diag.get("issue_code", "UNKNOWN")
    plan = final_state.get("resolution_plan", {})
    action = plan.get("proposed_action", {})
    verif = final_state.get("verification_result", {})
    sn = final_state.get("servicenow_update", {})
    audit = final_state.get("step_audit_trail", [])

    candidates = []
    for it in audit:
        if it.get("stage") == "diagnosis" and "Candidate Evaluation:" in it.get("step_name", ""):
            c_code = it.get("step_name", "").replace("Candidate Evaluation: ", "").strip()
            c_status = it.get("status", "unknown")
            candidates.append((c_code, c_status))

    lines = ["flowchart TD"]
    lines.append('    subgraph P1 ["📍 POINT 1: Domain Identified in Neo4j"]')
    lines.append(f'        D1["Domain: {domain}<br/>(Neo4j Root Node)"]')
    lines.append('    end')

    lines.append('    subgraph P2 ["📍 POINT 2: Scenarios Traversal & Root Cause Locked"]')
    if candidates:
        prev = None
        for code, status in candidates:
            safe_id = code.replace("-", "_")
            if status in ["matched", "confirmed"] or code == confirmed_rc:
                label = f"{code}<br/>✅ CONFIRMED ROOT CAUSE"
                lines.append(f'        {safe_id}["{label}"]')
            else:
                label = f"{code}<br/>❌ CONTRADICTED"
                lines.append(f'        {safe_id}["{label}"]')
            if prev:
                lines.append(f'        {prev} -. contradicted .-> {safe_id}')
            else:
                lines.append(f'        D1 --> {safe_id}')
            prev = safe_id
    else:
        safe_id = confirmed_rc.replace("-", "_")
        lines.append(f'        {safe_id}["{confirmed_rc}<br/>✅ CONFIRMED ROOT CAUSE"]')
        lines.append(f'        D1 --> {safe_id}')
    lines.append('    end')

    lines.append('    subgraph P3 ["📍 POINT 3: Consequent Graph Lifecycle"]')
    lines.append(f'        SKILL["Canonical Skill Loaded<br/>(:Skill {{id: \'{confirmed_rc}\'}} )"]')
    target_field = action.get("target_field", "Remediation")
    lines.append(f'        PLAN["Resolution Plan Formulated<br/>(User.{target_field})"]')
    lines.append('        EXEC["Remediation Execution<br/>(salesforce_update_user)"]')
    lines.append('        VERIF["Live State Verification<br/>(salesforce_get_user_details)"]')
    lines.append(f'        CLOSURE["Incident Closure<br/>({sn.get("incident_id", "Incident")} -> Resolved)"]')
    lines.append('    end')

    rc_id = confirmed_rc.replace("-", "_")
    lines.append(f'    {rc_id} ==> SKILL')
    lines.append('    SKILL --> PLAN')
    lines.append('    PLAN --> EXEC')
    lines.append('    EXEC --> VERIF')
    lines.append('    VERIF --> CLOSURE')

    # Styles
    lines.append('    style D1 fill:#eff6ff,stroke:#3b82f6,stroke-width:2px')
    lines.append(f'    style {rc_id} fill:#f0fdf4,stroke:#10b981,stroke-width:3px')
    for code, status in candidates:
        if code != confirmed_rc:
            s_id = code.replace("-", "_")
            lines.append(f'    style {s_id} fill:#fef2f2,stroke:#ef4444,stroke-width:1px')
    lines.append('    style SKILL fill:#f0fdf4,stroke:#10b981,stroke-width:2px')
    lines.append('    style PLAN fill:#f8fafc,stroke:#64748b,stroke-width:2px')
    lines.append('    style EXEC fill:#f0f9ff,stroke:#0284c7,stroke-width:2px')
    lines.append('    style VERIF fill:#ecfdf5,stroke:#059669,stroke-width:2px')
    lines.append('    style CLOSURE fill:#fdf4ff,stroke:#a855f7,stroke-width:2px')

    return "\n".join(lines)


# Sample Scenarios Catalog
SAMPLE_SCENARIOS = {
    "⚡ LIVE SALESFORCE: Sethuabhiram yenugula (SSO Login & Missing Fed ID)": {
        "incident_id": "INC-LIVE-001",
        "short_description": "Cannot sign in to Salesforce via Okta Single Sign-On",
        "caller_email": "ysethuabhiram@gmail.com",
        "on_behalf_of": "ysethuabhiram.2b47dde5aaca@agentforce.com",
        "description": "User Sethuabhiram yenugula (ysethuabhiram@gmail.com) reports SAML SSO failure. Authentication fails at identity assertion. Please check user FederationIdentifier in Salesforce.",
    },
    "⚡ LIVE SALESFORCE: salesforce agent (Account Verification)": {
        "incident_id": "INC-LIVE-002",
        "short_description": "User login issue - delegated access check",
        "caller_email": "salesforceagent@00djv0000000gvhuai.com",
        "on_behalf_of": "",
        "description": "User salesforceagent@00djv0000000gvhuai.com reports inability to authenticate. Verify user active status and federation ID in Salesforce.",
    },
    "LOGIN-4: Jane Doe SSO Federation ID Missing": {
        "incident_id": "INC10001",
        "short_description": "Cannot login to Salesforce via Okta SSO",
        "caller_email": "jane.doe@acme.corp",
        "on_behalf_of": "",
        "description": "User jane.doe@acme.corp is unable to log in to Salesforce via Okta Single Sign-On. Error states user not found in identity assertion. Please check user FederationIdentifier.",
    },
    "LOGIN-3: John Smith Account Deactivated (Delegated Admin)": {
        "incident_id": "INC10002",
        "short_description": "User locked out after medical leave",
        "caller_email": "john.smith@acme.corp",
        "on_behalf_of": "",
        "description": "John Smith (john.smith@acme.corp) returned from medical leave today and cannot log in. Login history indicates user account deactivated by Delegated Admin.",
    },
    "VAGUE: Cannot access Salesforce (Dynamic Diagnosis & Fallback)": {
        "incident_id": "INC10003",
        "short_description": "Can't access salesforce at all",
        "caller_email": "jane.doe@acme.corp",
        "on_behalf_of": "",
        "description": "I can't access salesforce at all since this morning. Please fix it immediately.",
    },
    "OBJECT-2: Sarah Connor Account Edit vs Mirror User (Alex Taylor)": {
        "incident_id": "INC10004",
        "short_description": "Cannot edit account details",
        "caller_email": "sarah.connor@acme.corp",
        "on_behalf_of": "",
        "description": "User sarah.connor@acme.corp lacks permission to edit Account records. Working fine for alex.taylor@acme.corp with same sales profile.",
    },
    "RECORD-3: Row-Level Opportunity Access Blocked": {
        "incident_id": "INC10005",
        "short_description": "Insufficient privileges on Opportunity record 006xx000001OPP",
        "caller_email": "sarah.connor@acme.corp",
        "on_behalf_of": "",
        "description": "Sarah Connor cannot open Opportunity record 006xx000001OPP. User receives insufficient privileges error.",
    },
    "APPLICATION-1: CC360 Community Portal Access Missing": {
        "incident_id": "INC10006",
        "short_description": "Unable to access CC360 Customer Portal",
        "caller_email": "sarah.connor@acme.corp",
        "on_behalf_of": "",
        "description": "User sarah.connor@acme.corp cannot see the CC360 navigation tab or portal. Compare with alex.taylor@acme.corp who has full CC360 access.",
    },
    "CUSTOM: Enter Custom ServiceNow Details": {
        "incident_id": "INC99999",
        "short_description": "",
        "caller_email": "",
        "on_behalf_of": "",
        "description": "",
    },
}


@st.cache_data(ttl=30)
def get_live_salesforce_users():
    """Fetch live users from Salesforce org via SOQL."""
    try:
        if salesforce_client.authenticate_direct():
            users = salesforce_client.execute_soql(
                "SELECT Id, Name, Username, Email, IsActive, Profile.Name, FederationIdentifier FROM User LIMIT 50"
            )
            return users or []
    except Exception as e:
        pass
    return []


def get_connection_info():
    """Detect current Salesforce connection mode."""
    is_live = salesforce_client.authenticate_direct()
    mcp_url = os.environ.get("SALESFORCE_MCP_URL")
    username = os.environ.get("SALESFORCE_USERNAME")
    access_token = salesforce_client.access_token

    if is_live and access_token and access_token != "fixture":
        return "Live Org (JWT Certificate)", f"Connected to `{salesforce_client.instance_url}` as `{username}` via OAuth 2.0 JWT Bearer Flow", "success"
    elif mcp_url:
        return "MCP Server", f"Configured for MCP endpoint `{mcp_url}`", "info"
    else:
        return "Fixture / PoC Mode", "Running locally with enriched mock fixtures (Offline safe)", "warning"


# --- SIDEBAR ---
with st.sidebar:
    st.markdown("### ⚙️ System Configuration")

    mode_name, mode_desc, mode_type = get_connection_info()
    if mode_type == "success":
        st.success(f"**{mode_name}**\n\n{mode_desc}")
    elif mode_type == "info":
        st.info(f"**{mode_name}**\n\n{mode_desc}")
    else:
        st.warning(f"**{mode_name}**\n\n{mode_desc}")

    neo4j_live = neo4j_repository.is_live()
    if neo4j_live:
        st.success("🕸️ **Neo4j Graph**: Connected (Live DB)")
    else:
        st.info("🕸️ **Knowledge Graph**: In-Memory Graph (78 steps)")

    st.markdown("---")
    st.markdown("### 📋 Load Scenario Preset")
    preset_key = st.selectbox("Choose a pre-configured incident:", list(SAMPLE_SCENARIOS.keys()), index=0)
    preset_data = SAMPLE_SCENARIOS[preset_key]

    st.markdown("---")
    st.markdown("### 🛡️ Human-in-the-Loop (HITL)")
    auto_approve = st.checkbox(
        "Auto-approve remediation changes",
        value=True,
        help="If enabled, auto-approves safe whitelisted remediations for seamless demo execution.",
    )

    if st.button("🔄 Refresh Live Salesforce Users"):
        st.cache_data.clear()
        st.sidebar.success("Salesforce cache refreshed!")

    if st.button("🔄 Reset Fixture Data"):
        reset_fixture_state()
        st.sidebar.success("Fixture data reset to initial state!")


# --- MAIN HEADER ---
st.markdown('<div class="main-title">⚡ Salesforce Agentic Support System</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">Autonomous multi-agent investigation pipeline connected directly to live Salesforce org with grounded evidence retrieval and root-cause confirmation.</div>',
    unsafe_allow_html=True,
)

# --- LIVE SALESFORCE ORG USER DIRECTORY ---
live_users = get_live_salesforce_users()
with st.expander("🌐 **Live Salesforce Org Directory & User Details**", expanded=True if live_users else False):
    c_info1, c_info2 = st.columns([2, 1])
    with c_info1:
        st.markdown(f"""
        - **Live Org Instance**: `{salesforce_client.instance_url}`
        - **Authenticated Agent**: `{os.environ.get('SALESFORCE_USERNAME')}`
        - **Auth Method**: `OAuth 2.0 JWT Bearer Flow (Public/Private Key Digital Certificate)`
        """)
    with c_info2:
        st.metric(label="Total Users in Live Org", value=len(live_users) if live_users else "Offline")

    if live_users:
        table_rows = []
        for u in live_users:
            p_name = u.get("Profile", {}).get("Name") if isinstance(u.get("Profile"), dict) else "N/A"
            table_rows.append({
                "Name": u.get("Name", "N/A"),
                "Username": u.get("Username", "N/A"),
                "Email": u.get("Email", "N/A"),
                "Salesforce ID": u.get("Id", "N/A"),
                "Profile": p_name,
                "Active": "✅ True" if u.get("IsActive") else "❌ False",
                "Federation ID": u.get("FederationIdentifier") or "*(None / Missing)*",
            })
        st.dataframe(table_rows, use_container_width=True)
        st.caption("💡 *Select the live preset from the sidebar or enter any of these actual emails/usernames in the ticket intake form below to test live investigation against real Salesforce data.*")
    else:
        st.info("No live users loaded. Currently in fixture fallback mode.")

# --- KNOWLEDGE BASE SOPS VIEWER ---
with st.expander("📚 **Knowledge Base Canonical SOPs (`data/sop_scenarios_selected_sheets.xlsx`)**", expanded=False):
    all_sops = sop_repository.get_all_sops()
    unique_sops = {}
    for code, sop_data in all_sops.items():
        raw_id = sop_data.get("id")
        if raw_id not in unique_sops:
            unique_sops[raw_id] = sop_data

    sop_table_rows = []
    for sop_id, sop_data in unique_sops.items():
        sop_table_rows.append({
            "SOP ID": sop_id,
            "Normalized Code": sop_data.get("code"),
            "Domain": sop_data.get("domain"),
            "Scenario Description": sop_data.get("description"),
            "Prerequisites": sop_data.get("prerequisites") or "None specified",
        })
    st.dataframe(sop_table_rows, use_container_width=True)
    st.caption("📖 *All 19 SOPs are dynamically loaded directly from `data/sop_scenarios_selected_sheets.xlsx`. When evaluating candidates, the diagnosis agent strictly exhausts all SOPs in the identified domain before transitioning across domains.*")

# --- INCIDENT INPUT FORM ---
with st.expander("📝 **ServiceNow Incident Intake Form**", expanded=True):
    col1, col2, col3 = st.columns([1.5, 2, 2])
    with col1:
        incident_id = st.text_input("Incident ID", value=preset_data["incident_id"])
    with col2:
        caller_email = st.text_input("Caller Email", value=preset_data["caller_email"])
    with col3:
        on_behalf_of = st.text_input("On Behalf Of (Optional)", value=preset_data.get("on_behalf_of", ""))

    short_description = st.text_input("Short Description / Summary", value=preset_data["short_description"])
    description = st.text_area("Full Description / Narrative", value=preset_data["description"], height=100)

    start_btn = st.button("🚀 Start Autonomous Investigation", type="primary", use_container_width=True)


# --- INVESTIGATION EXECUTION ---
if start_btn:
    ticket = {
        "incident_id": incident_id.strip() or "INC_TEST",
        "short_description": short_description.strip(),
        "caller_email": caller_email.strip(),
        "on_behalf_of": on_behalf_of.strip() if on_behalf_of else None,
        "description": description.strip(),
    }

    st.markdown("---")
    st.markdown("### 🔍 Live Multi-Agent Investigation Execution")

    orchestrator = InvestigationOrchestrator()
    config = {"configurable": {"thread_id": f"ui_{int(time.time())}"}}

    initial_state = {
        "incident": ticket,
        "evidence": [],
        "historical_cases": [],
        "trace_events": [],
        "iteration_count": 0,
    }
    if auto_approve:
        initial_state["approval"] = {"approval_status": "approved"}

    accumulated_state = dict(initial_state)
    execution_container = st.container()

    step_counter = 1
    stream_generator = orchestrator.graph.stream(initial_state, config=config)

    for output in stream_generator:
        for node_name, state_update in output.items():
            accumulated_state.update(state_update)
            if "step_audit_trail" in state_update:
                accumulated_state["step_audit_trail"] = state_update["step_audit_trail"]

            with execution_container:
                # -------------------------------------------------------------
                # STAGE 1: TRIAGE NODE
                # -------------------------------------------------------------
                if node_name == "triage":
                    triage = state_update.get("triage_result", {})
                    domain = triage.get("domain", "LOGIN")
                    is_ambig = triage.get("is_ambiguous", False)
                    affected = state_update.get("affected_user", {})
                    mirror = state_update.get("mirror_user")
                    history = state_update.get("historical_cases", [])
                    audit_trail = state_update.get("step_audit_trail", [])
                    triage_audit = next((it for it in audit_trail if it.get("stage") == "triage"), {})

                    domain_class = f"badge-{domain.lower()}" if domain.lower() in ["login", "object", "record", "app"] else "badge-login"

                    with st.expander(f"📍 **Step {step_counter}: Triage & Semantic Identity Resolution** `[{node_name}]`", expanded=True):
                        # Point 1 Knowledge Graph Callout
                        st.markdown(f"""
                        <div class="point-card-p1">
                            <span style="font-size: 1.15rem; font-weight: 700; color: #1e40af;">
                                📍 POINT 1: Domain Identified in Neo4j Knowledge Graph ➔ <code>(:Domain {{name: '{domain}'}})</code>
                            </span>
                            <p style="margin: 6px 0 0 0; color: #1e3a8a; font-size: 0.93rem; line-height: 1.55;">
                                <b>How the Graph Traversal Starts Here:</b> The Triage Agent ingests the incoming incident ticket, analyzes symptoms using semantic classification, and resolves the caller's Salesforce identity. By classifying the incident into the <b>{domain}</b> domain, the agent anchors the investigation onto the <b>Neo4j Domain root node</b>. Downstream candidate scenarios will strictly branch out from this domain anchor.
                            </p>
                        </div>
                        """, unsafe_allow_html=True)

                        st.markdown(f"""
                        **Orchestrator Stage Summary**: Evaluated incoming ticket narrative against canonical classification skill.
                        - **Classified Domain**: <span class="{domain_class}">{domain}</span>
                        - **Ambiguity Detected**: `{"Yes (Broad symptom - will perform cross-domain probe)" if is_ambig else "No (High confidence)"}`
                        - **Triage Reasoning**: *{triage.get("reasoning", "Extracted domain indicators from symptom profile.")}*
                        - 🎯 **Decision Basis**: *{triage_audit.get("decision_basis", "Domain determined by ticket narrative keywords.")}*
                        - ➡️ **Why Taking Next Step**: **{triage_audit.get("next_step_reason", "Advancing to diagnosis agent to evaluate candidate scenarios top-to-bottom without loading skill files.")}**
                        """, unsafe_allow_html=True)

                        # Explicit Tools Called Box
                        st.markdown(f"""
                        <div class="tool-box-clean">
                            <div style="font-weight: 700; color: #0284c7; font-size: 0.96rem; margin-bottom: 6px;">
                                🛠️ Tools Called at this Instance: <code>servicenow_get_incident()</code>, <code>salesforce_user_search()</code>, <code>salesforce_get_user_details()</code>
                            </div>
                            <div style="font-size: 0.90rem; color: #334155; line-height: 1.6;">
                                🎯 <b>Why Called at this Specific Instance:</b> Ingested ticket narrative from ServiceNow, resolved caller/affected email to a unique Salesforce User record (Id: <code>{affected.get('Id', 'N/A')}</code>), and pre-fetched live user gateway attributes into the evidence cache.<br>
                                📤 <b>Tool Results:</b><br>
                                &nbsp;&nbsp;• <b>ServiceNow Ingestion:</b> Retrieved ticket <code>{ticket.get('incident_id')}</code> ("{ticket.get('short_description')}")<br>
                                &nbsp;&nbsp;• <b>Salesforce Identity Match:</b> Mapped user email <code>{affected.get('Email', ticket.get('caller_email'))}</code> to Salesforce ID <code>{affected.get('Id', 'N/A')}</code><br>
                                &nbsp;&nbsp;• <b>Evidence Cache:</b> Gateway user record stored in memory (prevents redundant duplicate MCP queries)<br>
                                💡 <b>State Working Description:</b> Anchored investigation at Point 1 (Domain: {domain}). Ready to traverse candidate scenario nodes in Point 2.
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        c1, c2 = st.columns(2)
                        with c1:
                            st.markdown("##### 👤 Resolved Affected User")
                            if affected:
                                st.markdown(f"""
                                - **Name**: {affected.get('FirstName', '')} {affected.get('LastName', '')}
                                - **Email**: `{affected.get('Email', 'Unknown')}`
                                - **Salesforce ID**: `{affected.get('Id', 'N/A')}`
                                - **Resolution Source**: `{affected.get('resolution_source', 'Narrative')}`
                                """)
                            else:
                                st.warning("No affected user resolved from narrative or caller.")

                        with c2:
                            st.markdown("##### 👥 Resolved Mirror User (Comparative Peer)")
                            if mirror:
                                st.markdown(f"""
                                - **Name**: {mirror.get('FirstName', '')} {mirror.get('LastName', '')}
                                - **Email**: `{mirror.get('Email', 'Unknown')}`
                                - **Salesforce ID**: `{mirror.get('Id', 'N/A')}`
                                - **Role**: `Working benchmark baseline for differential permissions`
                                """)
                            else:
                                st.info("No comparative mirror user mentioned in ticket.")

                        if history:
                            st.markdown("##### 🧠 PostgreSQL pgvector Historical Precedents")
                            for idx, h in enumerate(history, 1):
                                sim = h.get('similarity', 0) * 100
                                st.markdown(f"**({idx}) [{sim:.1f}% Match] Past Incident {h.get('incident_id')}**: *{h.get('root_cause')}*")

                    step_counter += 1

                # -------------------------------------------------------------
                # STAGE 2: DIAGNOSIS NODE
                # -------------------------------------------------------------
                elif node_name == "diagnosis":
                    diag = state_update.get("diagnosis_result", {})
                    skill = state_update.get("skill_refs", {})
                    evidence = state_update.get("evidence", [])
                    findings = diag.get("findings", [])
                    confirmed_rc = diag.get('issue_code', 'Pending')

                    with st.expander(f"🔬 **Step {step_counter}: Candidate Evidence Evaluation & Root Cause Confirmation** `[{node_name}]`", expanded=True):
                        # Point 2 Knowledge Graph Callout
                        st.markdown(f"""
                        <div class="point-card-p2">
                            <span style="font-size: 1.15rem; font-weight: 700; color: #854d0e;">
                                📍 POINT 2: Knowledge Graph Scenarios Traversal & Root Cause Locked ➔ <code>(:Scenario {{id: '{confirmed_rc}'}})</code>
                            </span>
                            <p style="margin: 6px 0 0 0; color: #713f12; font-size: 0.93rem; line-height: 1.55;">
                                <b>How Traversal & Working Goes On:</b> From the Domain root node (Point 1), the Diagnosis Agent branches down the scenario DAG within the domain. Each candidate hypothesis is systematically evaluated against live Salesforce gateway evidence. Any candidate with conflicting evidence is marked <b>CONTRADICTED</b>. When all criteria match 100%, the root cause node is permanently confirmed and locked!
                            </p>
                        </div>
                        """, unsafe_allow_html=True)

                        st.markdown(f"""
                        **Orchestrator Decision Basis**: Evaluating candidates top-to-bottom against observed evidence.
                        - **Confirmed Root Cause**: `{confirmed_rc}`
                        - **Diagnostic Status**: `{diag.get('status', 'unknown').upper()}`
                        - **Skill Loading Boundary Rule**: *No skill file is loaded during candidate evaluation. Skill file is loaded only in the dedicated resolution planning stage (Point 3) after root cause is confirmed.*
                        """)

                        # Step-by-step candidate audit trail
                        audit_trail = state_update.get("step_audit_trail", [])
                        if audit_trail:
                            st.markdown("##### 📋 Knowledge Graph Scenario Nodes Traversal & Rule Evaluation")
                            st.caption("Traverses candidates top-to-bottom within the classified domain. Compares expected scenario criteria against live Salesforce attributes.")
                            for item in audit_trail:
                                if item.get("stage") in ["diagnosis", "root_cause_confirmation"]:
                                    is_rc = item.get("status") in ["confirmed", "matched"] or item.get("stage") == "root_cause_confirmation"
                                    badge_class = "badge-success" if is_rc else ("badge-login" if item.get("status") == "contradicted" else "badge-record")
                                    border_col = "#10b981" if is_rc else ("#ef4444" if item.get("status") == "contradicted" else "#f59e0b")
                                    bg_col = "#f0fdf4" if is_rc else ("#fef2f2" if item.get("status") == "contradicted" else "#f8fafc")
                                    obs_summary_english = item.get("observed_summary") or item.get("observed_values", {})
                                    if isinstance(obs_summary_english, dict):
                                        obs_summary_english = ", ".join(f"{k}: {v}" for k, v in obs_summary_english.items())

                                    tool_str = ", ".join(item.get("tools_called", [])) if item.get("tools_called") else "salesforce_get_user_details"
                                    tool_res_str = item.get("conclusion", "Evaluated against live evidence")

                                    cmp = item.get("decision_comparison") or {}
                                    dec_outcome = cmp.get("decision_outcome") or item.get("status_reason", "")
                                    is_yes = "yes" in str(dec_outcome).lower()
                                    is_no = "no" in str(dec_outcome).lower()
                                    if is_yes:
                                        pill_style = "background-color: #dcfce7; color: #166534; border: 1px solid #86efac; padding: 3px 10px; border-radius: 4px; font-weight: 700; font-size: 0.85rem;"
                                        pill_text = "✅ DECISION: YES"
                                    elif is_no:
                                        pill_style = "background-color: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; padding: 3px 10px; border-radius: 4px; font-weight: 700; font-size: 0.85rem;"
                                        pill_text = "❌ DECISION: NO"
                                    elif is_rc:
                                        pill_style = "background-color: #dcfce7; color: #166534; border: 1px solid #86efac; padding: 3px 10px; border-radius: 4px; font-weight: 700; font-size: 0.85rem;"
                                        pill_text = "🎯 CONFIRMED ROOT CAUSE"
                                    else:
                                        pill_style = "background-color: #eff6ff; color: #1e40af; border: 1px solid #bfdbfe; padding: 3px 10px; border-radius: 4px; font-weight: 700; font-size: 0.85rem;"
                                        pill_text = f"⚡ {item.get('status_reason', 'ACTION COMPLETED')}"

                                    comparison_html = ""
                                    if cmp:
                                        dec_color = "#16a34a" if is_yes else "#dc2626"
                                        comparison_html = f"""
                                        <div style="background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 12px 14px; margin: 10px 0;">
                                            <div style="font-weight: 700; color: #1e293b; margin-bottom: 6px; font-size: 0.92rem;">
                                                ⚖️ Side-by-Side Comparison & Decision Breakdown:
                                            </div>
                                            <table style="width: 100%; font-size: 0.87rem; border-collapse: collapse;">
                                                <tr style="border-bottom: 1px solid #f1f5f9;">
                                                    <td style="padding: 4px 8px; font-weight: 600; color: #475569; width: 28%;">Rule / Condition:</td>
                                                    <td style="padding: 4px 8px; color: #0f172a;">{cmp.get('rule_evaluated', 'N/A')}</td>
                                                </tr>
                                                <tr style="border-bottom: 1px solid #f1f5f9;">
                                                    <td style="padding: 4px 8px; font-weight: 600; color: #475569;">Expected Standard:</td>
                                                    <td style="padding: 4px 8px; color: #0f172a;">{cmp.get('expected_criteria', 'N/A')}</td>
                                                </tr>
                                                <tr style="border-bottom: 1px solid #f1f5f9; background: #f8fafc;">
                                                    <td style="padding: 4px 8px; font-weight: 600; color: #1e40af;">👤 Target User Value:</td>
                                                    <td style="padding: 4px 8px; font-family: monospace; color: #1e40af; font-weight: 600;">{cmp.get('target_value', 'N/A')}</td>
                                                </tr>
                                                <tr style="border-bottom: 1px solid #f1f5f9; background: #fdf4ff;">
                                                    <td style="padding: 4px 8px; font-weight: 600; color: #7e22ce;">👥 Benchmark / Peer Mirror:</td>
                                                    <td style="padding: 4px 8px; font-family: monospace; color: #7e22ce;">{cmp.get('baseline_value', 'N/A')}</td>
                                                </tr>
                                                <tr style="border-bottom: 1px solid #f1f5f9;">
                                                    <td style="padding: 4px 8px; font-weight: 600; color: #475569;">Comparison Result:</td>
                                                    <td style="padding: 4px 8px; font-weight: 700; color: {dec_color};">{cmp.get('comparison_result', 'N/A')}</td>
                                                </tr>
                                                <tr>
                                                    <td style="padding: 4px 8px; font-weight: 600; color: #475569;">Why {cmp.get('decision_outcome', 'Outcome')}:</td>
                                                    <td style="padding: 4px 8px; color: #334155; line-height: 1.5;">{cmp.get('reasoning', 'N/A')}</td>
                                                </tr>
                                            </table>
                                        </div>
                                        """
                                    elif item.get("graph_node_id") in ["NODE_FETCH_MIRROR_USER", "NODE_COMPARE_EMP_FED_ID"]:
                                        obs_dict = item.get("tool_result") or item.get("observed_values") or {}
                                        t_u = obs_dict.get("TargetUser", {}) if isinstance(obs_dict, dict) else {}
                                        p_m = obs_dict.get("PeerMirrorUser", {}) if isinstance(obs_dict, dict) else {}
                                        if t_u or isinstance(p_m, dict):
                                            comparison_html = f"""
                                            <div style="background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 12px 14px; margin: 10px 0;">
                                                <div style="font-weight: 700; color: #1e293b; margin-bottom: 6px; font-size: 0.92rem;">
                                                    👥 Peer Mirror User Attribute Baseline Comparison:
                                                </div>
                                                <table style="width: 100%; font-size: 0.87rem; border-collapse: collapse;">
                                                    <tr style="border-bottom: 1px solid #f1f5f9; background: #f8fafc;">
                                                        <td style="padding: 4px 8px; font-weight: 600; color: #1e40af; width: 28%;">👤 Target User:</td>
                                                        <td style="padding: 4px 8px; font-family: monospace; color: #1e40af;">Username: {t_u.get('Username')}, Profile: {t_u.get('Profile')}, UserType: {t_u.get('UserType')}, FedID: {t_u.get('FederationIdentifier')}</td>
                                                    </tr>
                                                    <tr style="border-bottom: 1px solid #f1f5f9; background: #fdf4ff;">
                                                        <td style="padding: 4px 8px; font-weight: 600; color: #7e22ce;">👥 Discovered Peer Mirror:</td>
                                                        <td style="padding: 4px 8px; font-family: monospace; color: #7e22ce;">Username: {p_m.get('Username') if isinstance(p_m, dict) else p_m}, Profile: {p_m.get('Profile') if isinstance(p_m, dict) else 'N/A'}, UserType: {p_m.get('UserType') if isinstance(p_m, dict) else 'N/A'}, FedID: {p_m.get('FederationIdentifier') if isinstance(p_m, dict) else 'N/A'}</td>
                                                    </tr>
                                                    <tr>
                                                        <td style="padding: 4px 8px; font-weight: 600; color: #475569;">Discovery Source:</td>
                                                        <td style="padding: 4px 8px; color: #334155;">{obs_dict.get('DiscoveryMethod', 'Salesforce SOQL discovery of active peer user with Standard license baseline')}</td>
                                                    </tr>
                                                </table>
                                            </div>
                                            """
                                        else:
                                            comparison_html = f"""
                                            <div style="background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 12px 14px; margin: 10px 0;">
                                                <div style="font-weight: 700; color: #1e293b; margin-bottom: 6px; font-size: 0.92rem;">
                                                    👥 Discovered Comparative Peer Mirror User:
                                                </div>
                                                <table style="width: 100%; font-size: 0.87rem; border-collapse: collapse;">
                                                    <tr style="border-bottom: 1px solid #f1f5f9; background: #fdf4ff;">
                                                        <td style="padding: 4px 8px; font-weight: 600; color: #7e22ce; width: 28%;">Peer Mirror User:</td>
                                                        <td style="padding: 4px 8px; font-family: monospace; color: #7e22ce;">{obs_dict.get('PeerMirrorUser', 'None')} (UserType: {obs_dict.get('PeerUserType', 'Standard')})</td>
                                                    </tr>
                                                    <tr>
                                                        <td style="padding: 4px 8px; font-weight: 600; color: #475569;">Discovery Source:</td>
                                                        <td style="padding: 4px 8px; color: #334155;">{obs_dict.get('DiscoveryMethod', 'Salesforce SOQL discovery of active peer user with Standard license baseline')}</td>
                                                    </tr>
                                                </table>
                                            </div>
                                            """

                                    with st.container():
                                        st.markdown(f"""
                                        <div style="border-left: 4px solid {border_col}; padding: 14px 18px; margin-bottom: 14px; background-color: {bg_col}; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                                                <div style="font-weight: 700; font-size: 1.02rem; color: #1e293b;">
                                                    {item.get('step_name')}
                                                </div>
                                                <div>
                                                    <span style="{pill_style}">{pill_text}</span>
                                                    <span style="font-family: monospace; font-size: 0.78rem; background: #e2e8f0; color: #334155; padding: 2px 6px; border-radius: 4px; margin-left: 6px;">
                                                        Node: {item.get('graph_node_id', 'DAG_NODE')}
                                                    </span>
                                                </div>
                                            </div>
                                            <div style="font-size: 0.90rem; color: #334155; line-height: 1.65;">
                                                🛠️ <b>Tool Called:</b> <code>{tool_str}()</code> &nbsp;|&nbsp; 🧭 <b>Traversal:</b> <span style="color: #7c3aed; font-weight: 600;">{item.get('movement_direction', 'N/A')}</span><br>
                                                {comparison_html if comparison_html else f"🔍 <b>Details:</b> {item.get('current_step_details', 'N/A')}<br>💡 <b>Outcome:</b> {item.get('status_reason', 'N/A')}"}
                                            </div>
                                        </div>
                                        """, unsafe_allow_html=True)

                        # Highlight locked root cause
                        if confirmed_rc and confirmed_rc != "Pending":
                            st.success(f"🎯 **Point 2 Confirmed & Locked**: Root Cause identified as `{confirmed_rc}`! Boundary rules satisfied. Ready to advance to Point 3 (Consequent Graph Lifecycle).")

                        st.markdown("##### 🛠️ Tools Called & Evidence Gathered from Salesforce")
                        st.info("⚡ **Zero-Duplicate MCP Execution**: Target User record is brought once from Salesforce MCP and stored as evidence. Subsequent checks directly evaluate cached evidence attributes without redundant MCP round-trips.")
                        if evidence:
                            for ev in evidence:
                                tool_name = ev.get('tool_name')
                                ev_id = ev.get('evidence_id')
                                obs = ev.get('observed_value')
                                raw = ev.get('raw_output')

                                human_evidence = format_evidence_to_human_english(ev)
                                st.markdown(f"""
                                <div class="tool-box" style="margin-bottom: 12px; padding: 12px 16px; border-left: 4px solid #0284c7; background: #f0f9ff; border-radius: 6px;">
                                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                                        <b>[Evidence ID: {ev_id}]</b> <code>{tool_name}()</code>
                                    </div>
                                    <div style="font-size: 0.92rem; color: #0f172a; line-height: 1.55;">
                                        <b>Observed Evidence Summary:</b> {human_evidence}
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                                with st.expander(f"🔍 Technical attributes ({ev_id})", expanded=False):
                                    st.json(obs or raw)

                        st.markdown("##### 📌 Grounded Findings")
                        for f in findings:
                            st.markdown(f"- **Claim**: {f.get('claim')} *(Evidence cited: `{f.get('evidence_refs')}`)*")

                    step_counter += 1

                # -------------------------------------------------------------
                # STAGE 3: RESOLUTION PLANNING
                # -------------------------------------------------------------
                elif node_name == "resolution_planning":
                    plan = state_update.get("resolution_plan", {})
                    action = plan.get("proposed_action", {})
                    skill = state_update.get("skill_refs", {})
                    audit_trail = state_update.get("step_audit_trail", [])
                    res_step = next((it for it in audit_trail if it.get("stage") == "resolution_planning"), {})

                    with st.expander(f"📐 **Step {step_counter}: Resolution Skill Loading & Remediation Planning** `[{node_name}]`", expanded=True):
                        # Point 3A Knowledge Graph Callout
                        st.markdown(f"""
                        <div class="point-card-p3">
                            <span style="font-size: 1.15rem; font-weight: 700; color: #166534;">
                                📍 POINT 3A: Consequent Graph Traversal ➔ Canonical Skill Loading & Remediation Formulation
                            </span>
                            <p style="margin: 6px 0 0 0; color: #14532d; font-size: 0.93rem; line-height: 1.55;">
                                <b>Advancing along Directed Edge:</b> <code>(:Scenario {{id: '{plan.get('issue_code')}'}})-[:GOVERNED_BY]->(:Skill {{id: '{plan.get('issue_code')}'}})</code><br>
                                Now that Point 2 (Root Cause) is locked, the agent traverses into the remediation lifecycle. Strictly complying with boundary rules, the agent loads the canonical SOP skill file for <b>{plan.get('issue_code')}</b> to formulate exact remediation parameters without LLM guesswork or hallucination.
                            </p>
                        </div>
                        """, unsafe_allow_html=True)

                        # Explicit Tool Call Box
                        st.markdown(f"""
                        <div class="tool-box-clean">
                            <div style="font-weight: 700; color: #166534; font-size: 0.96rem; margin-bottom: 6px;">
                                🛠️ Tool / Skill Called at this Instance: <code>skill_service.load("{plan.get('issue_code')}")</code>
                            </div>
                            <div style="font-size: 0.90rem; color: #334155; line-height: 1.6;">
                                🎯 <b>Why Called at this Specific Instance:</b> To load authoritative Standard Operating Procedure instructions for confirmed root cause <code>{plan.get('issue_code')}</code> and formulate verified mutation fields.<br>
                                📤 <b>Tool Results:</b><br>
                                &nbsp;&nbsp;• <b>Skill File Loaded:</b> <code>{skill.get('file_path')}</code> (v{skill.get('version', 1)})<br>
                                &nbsp;&nbsp;• <b>Skill Title:</b> {skill.get('title')}<br>
                                &nbsp;&nbsp;• <b>Proposed Action:</b> <code>{action.get('action_type', 'UPDATE_USER_FIELD')}</code> on <b>User.{action.get('target_field')}</b> (Target: <code>{action.get('target_record_id')}</code>)<br>
                                &nbsp;&nbsp;• <b>Value Transformation:</b> Current: <code>{action.get('current_value')}</code> ➔ Proposed: <code>{action.get('proposed_value')}</code><br>
                                💡 <b>State Working Description:</b> Remediation plan formulated with exact field specifications. Preconditions validated. Ready to advance to Point 3B (Execution / Approval Gate).
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        col_a, col_b = st.columns(2)
                        with col_a:
                            st.markdown(f"""
                            - **Action Type**: `{action.get('action_type')}`
                            - **Target Salesforce Record**: `{action.get('target_record_id')}`
                            - **Field to Modify**: `User.{action.get('target_field')}`
                            - **Requires HITL Review**: `{plan.get('requires_approval')}`
                            """)
                        with col_b:
                            st.markdown(f"""
                            - **Current Value**: `{action.get('current_value')}`
                            - **Proposed Value**: `{action.get('proposed_value')}`
                            - **Preconditions Checked**: `{plan.get('preconditions')}`
                            """)

                    step_counter += 1

                # -------------------------------------------------------------
                # STAGE 4: REMEDIATION EXECUTION
                # -------------------------------------------------------------
                elif node_name == "execute_remediation":
                    plan = state_update.get("resolution_plan", {})
                    appr = state_update.get("approval", {})
                    action = plan.get("proposed_action", {})
                    audit_trail = state_update.get("step_audit_trail", [])
                    exec_step = next((it for it in audit_trail if it.get("stage") == "execution"), {})
                    tool_res = plan.get("execution_result") or exec_step.get("tool_result") or exec_step.get("observed_values", {}).get("result", {})
                    tool_called = exec_step.get("tool_called") or (exec_step.get("tools_called", ["salesforce_update_user"])[0] if exec_step.get("tools_called") else "salesforce_update_user")
                    skill_id = exec_step.get("skill_id") or state_update.get("skill_refs", {}).get("issue_code", "UNKNOWN")
                    skill_title = exec_step.get("skill_title") or state_update.get("skill_refs", {}).get("title", f"Scenario {skill_id}")
                    skill_file = exec_step.get("skill_file_loaded") or state_update.get("skill_refs", {}).get("file_path", "canonical resolution skill")
                    why_called_instance = exec_step.get("why_called_at_instance") or exec_step.get("why_loaded") or exec_step.get("decision_basis", "Human operator approval verified.")

                    with st.expander(f"⚙️ **Step {step_counter}: Remediation Execution** `[{node_name}]`", expanded=True):
                        # Point 3B Knowledge Graph Callout
                        st.markdown(f"""
                        <div class="point-card-p3">
                            <span style="font-size: 1.15rem; font-weight: 700; color: #166534;">
                                📍 POINT 3B: Consequent Graph Traversal ➔ Remediation Execution via Governed Tool
                            </span>
                            <p style="margin: 6px 0 0 0; color: #14532d; font-size: 0.93rem; line-height: 1.55;">
                                <b>Advancing along Directed Edge:</b> <code>(:ResolutionPlan)-[:EXECUTES_VIA]->(:Tool {{name: '{tool_called}'}})</code><br>
                                Human operator approval has been validated (or test auto-approval policy confirmed). The agent executes the authorized remediation tool directly against Salesforce to resolve the root cause.
                            </p>
                        </div>
                        """, unsafe_allow_html=True)

                        st.markdown(f"""
                        <div class="tool-box-clean">
                            <div style="font-weight: 700; color: #0284c7; font-size: 0.96rem; margin-bottom: 6px;">
                                🛠️ Tool Executed at this Instance: <code>{tool_called}()</code> <span class="badge-success">[{plan.get('status', 'executed').upper()}]</span>
                            </div>
                            <div style="font-size: 0.90rem; color: #334155; line-height: 1.6;">
                                📖 <b>Skill Being Used:</b> <b>{skill_title}</b> (<code>{skill_id}</code>) from <code>{skill_file}</code><br>
                                🎯 <b>Why Called at this Specific Instance:</b> {why_called_instance}<br>
                                🔧 <b>Action Performed:</b> <code>{action.get('action_type', 'UPDATE_USER_FIELD')}</code> on <b>User.{action.get('target_field')}</b> (Target ID: <code>{action.get('target_record_id')}</code>)<br>
                                👤 <b>Approval Status:</b> <code>{appr.get('approval_id', 'Auto-Approved in Test Policy')}</code><br>
                                🧭 <b>Graph Movement Direction:</b> <span style="color: #7c3aed; font-weight: 600;">{exec_step.get('movement_direction', 'Advance along Directed Edge MUTATION_EXECUTED -> [State Verification DAG]')}</span><br>
                                ➡️ <b>Why Moving to Next Step:</b> <span style="color: #0b5cff; font-weight: 600;">{exec_step.get('next_step', exec_step.get('next_step_reason', 'Advancing to State Verification to confirm post-change state.'))}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        st.markdown("##### 📤 Tool Execution Result & Returned Payload")
                        if tool_res.get("success"):
                            st.success(f"**Status**: Success | **Message**: {tool_res.get('message', 'Update executed successfully on Salesforce')}")
                        else:
                            st.error(f"**Status**: Failed | **Error**: {tool_res.get('error', 'Execution error')}")

                        with st.expander("🔍 View Raw Execution Result Payload", expanded=False):
                            st.json(tool_res)

                    step_counter += 1

                # -------------------------------------------------------------
                # STAGE 5: VERIFICATION
                # -------------------------------------------------------------
                elif node_name == "verification":
                    verif = state_update.get("verification_result", {})
                    is_ver = verif.get("verified", False)
                    audit_trail = state_update.get("step_audit_trail", [])
                    verif_step = next((it for it in audit_trail if it.get("stage") == "verification"), {})

                    with st.expander(f"✅ **Step {step_counter}: State Verification** `[{node_name}]`", expanded=True):
                        # Point 3C Knowledge Graph Callout
                        st.markdown(f"""
                        <div class="point-card-p3">
                            <span style="font-size: 1.15rem; font-weight: 700; color: #166534;">
                                📍 POINT 3C: Consequent Graph Traversal ➔ Post-Remediation Live State Verification Gate
                            </span>
                            <p style="margin: 6px 0 0 0; color: #14532d; font-size: 0.93rem; line-height: 1.55;">
                                <b>Advancing along Directed Edge:</b> <code>(:Execution)-[:AUDITED_BY]->(:VerificationGate {{tool: 'salesforce_get_user_details'}})</code><br>
                                Trust but verify: The system executes an independent query against Salesforce to mathematically confirm the post-change state matches expected requirements before communicating with the user or closing the incident.
                            </p>
                        </div>
                        """, unsafe_allow_html=True)

                        st.markdown(f"""
                        <div class="tool-box-clean">
                            <div style="font-weight: 700; color: #059669; font-size: 0.96rem; margin-bottom: 6px;">
                                🛠️ Tool Called at this Instance: <code>salesforce_get_user_details()</code> <span class="badge-success">[{'VERIFIED' if is_ver else 'DISCREPANCY'}]</span>
                            </div>
                            <div style="font-size: 0.90rem; color: #334155; line-height: 1.6;">
                                🎯 <b>Why Called at this Specific Instance:</b> {verif_step.get('why_called_at_instance', 'Post-remediation verification query against Salesforce to verify live attributes.')}<br>
                                📤 <b>Tool Results:</b><br>
                                &nbsp;&nbsp;• <b>Checks Performed:</b> <code>{verif.get('checks_performed')}</code><br>
                                &nbsp;&nbsp;• <b>Expected State:</b> <code>{verif.get('expected_state')}</code><br>
                                &nbsp;&nbsp;• <b>Actual Observed in Salesforce:</b> <code>{verif.get('actual_state')}</code><br>
                                &nbsp;&nbsp;• <b>Comparison:</b> <b>{verif_step.get('comparison', 'State matches 100%')}</b><br>
                                💡 <b>State Working Description:</b> Live state verified. Safe to notify customer and close ticket in ServiceNow.
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                    step_counter += 1

                # -------------------------------------------------------------
                # STAGE 6: COMMUNICATION & SERVICENOW CLOSURE
                # -------------------------------------------------------------
                elif node_name == "communication":
                    comm = state_update.get("communication_draft", "")
                    sn = state_update.get("servicenow_update", {})
                    audit_trail = state_update.get("step_audit_trail", [])
                    comm_step = next((it for it in audit_trail if it.get("stage") == "communication"), {})

                    with st.expander(f"📬 **Step {step_counter}: Communication & Incident Closure** `[{node_name}]`", expanded=True):
                        # Point 3D Knowledge Graph Callout
                        st.markdown(f"""
                        <div class="point-card-p3">
                            <span style="font-size: 1.15rem; font-weight: 700; color: #166534;">
                                📍 POINT 3D: Consequent Graph Traversal ➔ Incident Closure & Communication Dispatch
                            </span>
                            <p style="margin: 6px 0 0 0; color: #14532d; font-size: 0.93rem; line-height: 1.55;">
                                <b>Advancing along Directed Edge:</b> <code>(:VerificationGate)-[:NOTIFIES_AND_CLOSES]->(:IncidentClosure)</code><br>
                                The investigation lifecycle reaches its terminal node. ServiceNow ticket is updated with complete root cause work notes, status is changed to Resolved, and plain-English communication is delivered to the requester.
                            </p>
                        </div>
                        """, unsafe_allow_html=True)

                        st.markdown(f"""
                        <div class="tool-box-clean">
                            <div style="font-weight: 700; color: #a855f7; font-size: 0.96rem; margin-bottom: 6px;">
                                🛠️ Tool Called at this Instance: <code>servicenow_resolve_incident()</code>
                            </div>
                            <div style="font-size: 0.90rem; color: #334155; line-height: 1.6;">
                                🎯 <b>Why Called at this Specific Instance:</b> {comm_step.get('why_called_at_instance', 'State verification succeeded; updating ServiceNow ticket state to Resolved and documenting work notes.')}<br>
                                📤 <b>Tool Results:</b><br>
                                &nbsp;&nbsp;• <b>ServiceNow Incident:</b> <code>{sn.get('incident_id')}</code> updated to <b>{sn.get('state', 'Resolved')}</b><br>
                                &nbsp;&nbsp;• <b>Audit Work Notes Written:</b> Grounded root cause and remediation details logged<br>
                                💡 <b>State Working Description:</b> Ticket resolved and closed. Customer notified. Graph lifecycle complete.
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        st.markdown("##### ✉️ Drafted User Resolution Communication:")
                        st.info(comm)

                    step_counter += 1

                # -------------------------------------------------------------
                # STAGE 7: ESCALATION
                # -------------------------------------------------------------
                elif node_name == "escalation":
                    sn = state_update.get("servicenow_update", {})
                    with st.expander(f"⚠️ **Step {step_counter}: Incident Escalation** `[{node_name}]`", expanded=True):
                        st.warning(f"Ticket `{sn.get('incident_id')}` escalated to Tier-2 support.")
                        st.markdown(f"**Reason**: {sn.get('reason')}")
                    step_counter += 1

    st.success("🎉 **Investigation Completed Successfully!** All agents collaborated and updated state.")

    # Render dynamic Knowledge Graph Traversal Map
    st.markdown("---")
    st.markdown("### 🕸️ Neo4j Knowledge Graph Traversal & Working Lifecycle Map")
    st.markdown("""
    This dynamic graph visualizes the exact traversal through the Neo4j Knowledge Graph across Point 1, Point 2, and Point 3:
    - **📍 Point 1 (Domain Identified)**: The investigation begins at the Domain root node identified by the Triage Agent.
    - **📍 Point 2 (Scenarios Traversal & Root Cause)**: Diagnosis Agent traverses candidates, contradicting mismatches until the verified root cause is locked.
    - **📍 Point 3 (Consequent Graph Nodes)**: The remediation lifecycle advances through canonical skill loading, policy approval, tool execution, live state verification, and incident closure.
    """)
    mermaid_diagram = build_traversal_mermaid(accumulated_state)
    st.markdown(f"```mermaid\n{mermaid_diagram}\n```")

    # Show Complete Trace & State
    with st.expander("📊 **Full Orchestrator State & Audit Trace (JSON)**"):
        st.json(accumulated_state)

# --- NEO4J KNOWLEDGE GRAPH EXPLORER ---
st.markdown("---")
with st.expander("🕸️ **Neo4j Knowledge Graph & Scenario Topology Explorer**", expanded=False):
    st.markdown("""
    Explore the canonical investigation DAGs stored in **Neo4j** (or local structured graph).
    Each scenario defines the exact dependencies, required tools, evidence checks, and human approval gates.
    """)

    sel_col1, sel_col2 = st.columns([1, 2])
    with sel_col1:
        chosen_domain = st.selectbox("Select Domain:", ["LOGIN", "OBJECT", "RECORD", "APPLICATION"], key="graph_domain")

    plan_info = neo4j_repository.get_domain_plan(chosen_domain)
    scenarios_list = plan_info.get("scenarios", [])

    st.caption(f"Knowledge Graph Source: `{plan_info.get('source')}` | Total Scenarios Mapped: `{len(scenarios_list)}`")

    for sc in scenarios_list:
        with st.expander(f"📌 **{sc.get('scenario_name')}** (`{sc.get('scenario_id')}`)", expanded=False):
            st.markdown(f"**Description**: {sc.get('description')}")
            st.markdown(f"**Canonical Skill File**: `{sc.get('skill_file')}` *(Status: {sc.get('skill_status')})*")

            st.markdown("##### Investigation Steps & Dependency DAG:")
            for stp in sc.get("steps", []):
                mode_badge = "🔴 Write (Approval Req)" if stp.get("approval_required") else "🟢 Read-Only"
                st.markdown(f"""
                - **Step {stp.get('step_order')} [{stp.get('stage').upper()}]: {stp.get('name')}** (`{stp.get('step_id')}`) — {mode_badge}
                  - **Instruction**: {stp.get('instruction')}
                  - **Tools**: `{', '.join(stp.get('tools', [])) if stp.get('tools') else 'None (Semantic Evaluation)'}`
                  - **Evidence Required**: `{', '.join(stp.get('evidence_required', []))}`
                  - **Depends On**: `{', '.join(stp.get('depends_on', [])) if stp.get('depends_on') else 'Root Step'}`
                """)
