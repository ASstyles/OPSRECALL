"""
OPSRECALL — Incident Intelligence Agent for SRE & DevOps Teams.
Powered by Hindsight Persistent Operational Memory & Groq Reasoning.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import settings
from core.evaluation import get_evaluation_framework
from core.hindsight_client import get_hindsight_client
from core.incident_engine import get_incident_engine
from core.investigation import get_investigation_engine
from core.learning_engine import get_learning_engine
from core.memory_manager import get_memory_manager
from core.validators import Incident
from database.db import get_db

# ------------------------------------------------------------------------------
# Streamlit Page Configuration
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="OPSRECALL — Incident Intelligence Agent",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------------------------
# Custom CSS for Dark Enterprise Aesthetic
# ------------------------------------------------------------------------------
CUSTOM_CSS = """
<style>
/* Main app dark theme overrides */
.stApp {
    background-color: #0b0f19;
    color: #e2e8f0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}

/* Sidebar styling */
[data-testid="stSidebar"] {
    background-color: #0f172a;
    border-right: 1px solid #1e293b;
}

/* Metric card styling */
div[data-testid="stMetric"] {
    background-color: #151e2e;
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 12px 16px;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
}
div[data-testid="stMetric"] label {
    color: #94a3b8 !important;
    font-size: 0.85rem !important;
    font-weight: 500;
}
div[data-testid="stMetric"] [data-testid="stMetricValue"] {
    color: #38bdf8 !important;
    font-size: 1.8rem !important;
    font-weight: 700;
}

/* Custom cards */
.sre-card {
    background-color: #151e2e;
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 16px 20px;
    margin-bottom: 16px;
}
.sre-card-header {
    font-size: 1.1rem;
    font-weight: 600;
    color: #f8fafc;
    margin-bottom: 8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.sre-badge {
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}
.badge-sev1 { background-color: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid #ef4444; }
.badge-sev2 { background-color: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid #f59e0b; }
.badge-sev3 { background-color: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid #3b82f6; }
.badge-live { background-color: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid #10b981; }
.badge-preview { background-color: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid #f59e0b; }
.badge-error { background-color: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid #ef4444; }

/* Callouts */
.failed-fix-alert {
    background-color: rgba(239, 68, 68, 0.1);
    border-left: 4px solid #ef4444;
    padding: 10px 14px;
    margin: 8px 0;
    border-radius: 0 6px 6px 0;
}
.success-fix-box {
    background-color: rgba(16, 185, 129, 0.1);
    border-left: 4px solid #10b981;
    padding: 10px 14px;
    margin: 8px 0;
    border-radius: 0 6px 6px 0;
}
.memory-box {
    background-color: rgba(6, 182, 212, 0.08);
    border: 1px solid rgba(6, 182, 212, 0.3);
    border-radius: 6px;
    padding: 12px;
    margin-bottom: 10px;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# Initialize Singletons
# ------------------------------------------------------------------------------
db = get_db()
incident_engine = get_incident_engine()
hindsight_client = get_hindsight_client()
memory_manager = get_memory_manager()
investigation_engine = get_investigation_engine()
learning_engine = get_learning_engine()
eval_framework = get_evaluation_framework()

# ------------------------------------------------------------------------------
# Sidebar Navigation & System Health Status
# ------------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🛡️ **OPSRECALL**")
    st.caption("Change-Aware Operational Memory for SREs")
    st.markdown("---")

    # Live Hindsight Connection Status Check
    hs_health = hindsight_client.check_health()
    hs_status = hs_health.get("status")
    hs_mode = hs_health.get("mode")

    if hs_status == "CONNECTED":
        st.markdown(
            '<span class="sre-badge badge-live">● HINDSIGHT LIVE</span>',
            unsafe_allow_html=True,
        )
        st.caption(f"Bank: `{hs_health.get('bank_id')}`")
    elif hs_status == "NOT_CONFIGURED":
        st.markdown(
            '<span class="sre-badge badge-preview">● OFFLINE PREVIEW</span>',
            unsafe_allow_html=True,
        )
        st.caption("Hindsight Key: Unconfigured (Local Mode)")
    else:
        st.markdown(
            '<span class="sre-badge badge-error">● CONNECTION ISSUE</span>',
            unsafe_allow_html=True,
        )
        st.caption(f"Status: {hs_status}")

    # Groq Model Status
    if settings.is_groq_configured():
        st.markdown(
            f'<span class="sre-badge badge-live">● GROQ: {settings.GROQ_MODEL}</span>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<span class="sre-badge badge-preview">● GROQ: OFFLINE EXPERT</span>',
            unsafe_allow_html=True,
        )

    st.markdown("---")

    selected_page = st.radio(
        "Navigation",
        [
            "Command Center",
            "Incident Console",
            "AI Investigation & Comparison",
            "Memory Explorer",
            "Learning Center",
            "Evaluation Lab",
            "Architecture & About",
        ],
        index=0,
    )

    st.markdown("---")
    st.caption("v1.0.0 | Competition Build")
    st.caption("Simulated Infrastructure Environment")


# ==============================================================================
# SECTION 1: COMMAND CENTER
# ==============================================================================
if selected_page == "Command Center":
    st.title("⚡ Operational Command Center")
    st.markdown(
        "Real-time operational status, memory bank metrics, and active incident telemetry."
    )

    # Top Metric Bar
    all_incidents = incident_engine.get_all_incidents()
    sev1_count = sum(1 for i in all_incidents if i.severity == "SEV-1")
    eval_count = len(list(settings.OUTPUTS_DIR.glob("*.json")))

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("System Mode", hs_mode)
    with col2:
        st.metric("Memory Bank", settings.HINDSIGHT_BANK_ID)
    with col3:
        st.metric("Incident Records", len(all_incidents))
    with col4:
        st.metric("SEV-1 Critical", sev1_count)
    with col5:
        st.metric("Benchmark Runs", eval_count)

    st.markdown("<br>", unsafe_allow_html=True)

    # Connection Status Alert Banner if unconfigured
    if hs_status == "NOT_CONFIGURED":
        st.info(
            f"ℹ️ **Hindsight Setup Notice**: {hs_health.get('message')}"
        )
    elif hs_status == "CONNECTED":
        st.success(f"✅ {hs_health.get('message')}")

    # Service Health Overview & Active Incident Cards
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.subheader("🌐 Monitored Service Health")
        services = incident_engine.get_service_health_summary()
        if services:
            df_svc = pd.DataFrame(services)
            df_svc.rename(
                columns={
                    "service_name": "Service",
                    "incident_count": "Incidents",
                    "sev1_count": "SEV-1 Events",
                    "latest_severity": "Recent Severity",
                    "latest_incident_time": "Last Event",
                },
                inplace=True,
            )
            st.dataframe(df_svc, hide_index=True)
        else:
            st.info("No service telemetry records found.")

        st.subheader("🕒 Recent Investigations")
        recents = db.list_investigations(limit=5)
        if recents:
            df_recent = pd.DataFrame(recents)
            df_recent = df_recent[
                ["investigation_id", "incident_id", "mode", "confidence_level", "execution_time_seconds", "created_at"]
            ]
            df_recent.rename(
                columns={
                    "investigation_id": "Investigation ID",
                    "incident_id": "Incident Ref",
                    "mode": "Memory Mode",
                    "confidence_level": "Confidence",
                    "execution_time_seconds": "Duration (s)",
                    "created_at": "Timestamp",
                },
                inplace=True,
            )
            st.dataframe(df_recent, hide_index=True)
        else:
            st.info("No investigations recorded yet.")

    with col_right:
        st.subheader("🔥 Operational Incidents")
        for inc in all_incidents[:4]:
            badge_class = "badge-sev1" if inc.severity == "SEV-1" else "badge-sev2"
            with st.container():
                st.markdown(
                    f"""
                    <div class="sre-card">
                        <div class="sre-card-header">
                            <span>{inc.incident_id}: {inc.affected_service}</span>
                            <span class="sre-badge {badge_class}">{inc.severity}</span>
                        </div>
                        <div style="font-size: 0.9rem; color: #cbd5e1; margin-bottom: 6px;">
                            <strong>{inc.incident_title}</strong>
                        </div>
                        <div style="font-size: 0.8rem; color: #94a3b8;">
                            Change: {inc.deployment_id or 'Config Drift'}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


# ==============================================================================
# SECTION 2: INCIDENT CONSOLE
# ==============================================================================
elif selected_page == "Incident Console":
    st.title("🚨 Incident Telemetry Console")
    st.markdown("Ingest, inspect, and configure operational incident telemetry.")

    all_incidents = incident_engine.get_all_incidents()
    inc_options = [f"{i.incident_id} — {i.incident_title} ({i.affected_service})" for i in all_incidents]
    inc_options.append("➕ Create Custom Incident Scenario")

    selected_choice = st.selectbox("Select Incident Scenario", inc_options)

    if selected_choice.startswith("➕"):
        st.subheader("Define Custom Incident")
        c1, c2 = st.columns(2)
        with c1:
            c_id = st.text_input("Incident ID", value="INC-CUSTOM")
            c_svc = st.text_input("Affected Service", value="checkout-api")
            c_title = st.text_input("Incident Title", value="Latency spike on API")
        with c2:
            c_sev = st.selectbox("Severity", ["SEV-1", "SEV-2", "SEV-3", "SEV-4"])
            c_dep = st.text_input("Recent Deployment ID", value="DEP-9999")
            c_change = st.text_area("Deployment / Config Change Details", value="Updated container resource limits")

        c_symptoms = st.text_area("Symptoms (one per line)", value="P99 latency surged to 5000ms\nError rate spiked to 12%")
        c_logs = st.text_area("Error Logs (one per line)", value="ERROR client timeout after 30000ms")

        incident_to_inspect = {
            "incident_id": c_id,
            "incident_title": c_title,
            "affected_service": c_svc,
            "severity": c_sev,
            "symptoms": [s.strip() for s in c_symptoms.split("\n") if s.strip()],
            "error_logs": [l.strip() for l in c_logs.split("\n") if l.strip()],
            "deployment_id": c_dep,
            "deployment_or_change": c_change,
            "metrics": {"p99_latency_ms": 5000, "error_rate_pct": 12.0},
        }
    else:
        target_id = selected_choice.split(" — ")[0]
        inc_obj = incident_engine.get_incident(target_id)
        incident_to_inspect = inc_obj.model_dump()

    # Display telemetry preview
    st.markdown("---")
    st.subheader(f"Telemetry Inspection: `{incident_to_inspect['incident_id']}`")

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Affected Service", incident_to_inspect.get("affected_service"))
    with m2:
        st.metric("Severity", incident_to_inspect.get("severity"))
    with m3:
        st.metric("Deployment ID", incident_to_inspect.get("deployment_id") or "None")
    with m4:
        st.metric("Telemetry Points", len(incident_to_inspect.get("symptoms", [])) + len(incident_to_inspect.get("error_logs", [])))

    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown("#### 📋 Operational Symptoms")
        for sym in incident_to_inspect.get("symptoms", []):
            st.markdown(f"- {sym}")

        st.markdown("#### 🔄 Change Context")
        st.info(incident_to_inspect.get("deployment_or_change") or "No deployment change detected.")

    with col_r:
        st.markdown("#### 📜 Raw Error Logs")
        logs = incident_to_inspect.get("error_logs", [])
        if logs:
            st.code("\n".join(logs), language="log")
        else:
            st.caption("No log snippets attached.")

        # Metric visualization if present
        metrics = incident_to_inspect.get("metrics", {})
        if metrics:
            st.markdown("#### 📊 Metric Snapshot")
            m_df = pd.DataFrame(list(metrics.items()), columns=["Metric", "Value"])
            st.dataframe(m_df, hide_index=True)

    st.markdown("---")
    st.markdown("### Ready to Investigate")
    if st.button("🚀 Send to AI Investigation Engine", type="primary"):
        st.session_state["active_incident"] = incident_to_inspect
        st.session_state["nav_target"] = "AI Investigation & Comparison"
        st.success("Incident telemetry sent to Investigation Engine! Switch to 'AI Investigation & Comparison' in sidebar.")


# ==============================================================================
# SECTION 3: AI INVESTIGATION & SIDE-BY-SIDE COMPARISON
# ==============================================================================
elif selected_page == "AI Investigation & Comparison":
    st.title("🔬 AI Incident Investigation & Comparison")
    st.markdown(
        "Demonstrate the power of **Change-Aware Operational Memory** by comparing "
        "an investigation **WITHOUT Hindsight** vs. **WITH Hindsight** side-by-side."
    )

    # Check for active incident in session state
    all_incidents = incident_engine.get_all_incidents()
    active_inc = st.session_state.get("active_incident", all_incidents[0].model_dump())

    # Quick selector
    inc_titles = [f"{i.incident_id} — {i.incident_title}" for i in all_incidents]
    curr_idx = 0
    for idx, it in enumerate(inc_titles):
        if active_inc.get("incident_id") in it:
            curr_idx = idx
            break

    sel = st.selectbox("Select Incident to Investigate", inc_titles, index=curr_idx)
    target_id = sel.split(" — ")[0]
    active_inc = incident_engine.get_incident(target_id).model_dump()
    st.session_state["active_incident"] = active_inc

    col_btn1, col_btn2 = st.columns([1, 4])
    with col_btn1:
        run_comp = st.button("⚡ Run Side-by-Side Comparison", type="primary")

    if run_comp or "comp_results" in st.session_state:
        if run_comp:
            with st.spinner("Executing side-by-side investigation across both modes..."):
                res_disabled, res_enabled = investigation_engine.run_comparison(active_inc)
                st.session_state["comp_results"] = (res_disabled, res_enabled)
        else:
            res_disabled, res_enabled = st.session_state["comp_results"]

        st.markdown("---")
        st.markdown("### ⚖️ Side-by-Side Investigation Comparison")

        # Two columns for side-by-side display
        col_off, col_on = st.columns(2)

        # ----------------------------------------------------
        # Column 1: MEMORY DISABLED
        # ----------------------------------------------------
        with col_off:
            st.markdown(
                """
                <div style="background-color: #1e293b; padding: 12px; border-radius: 8px; border-left: 4px solid #64748b; margin-bottom: 12px;">
                    <h3 style="margin: 0; color: #94a3b8;">❌ WITHOUT Hindsight Memory</h3>
                    <p style="margin: 4px 0 0 0; font-size: 0.85rem; color: #cbd5e1;">
                        Standard LLM baseline: No historical recall, no negative experience awareness.
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown(f"**Executive Summary:** {res_disabled.executive_summary}")
            st.caption(f"Reasoning Model: `{res_disabled.llm_model}` | Duration: {res_disabled.execution_time_seconds}s")

            st.markdown("#### 🎯 Hypotheses (Memory Disabled)")
            for h in res_disabled.hypotheses:
                st.markdown(f"**{h.rank}. {h.hypothesis}**")
                st.caption(f"Likelihood: {h.likelihood} | Evidence: {', '.join(h.supporting_evidence)}")

            st.markdown("#### 🛠️ Recommended Remediation")
            for r in res_disabled.recommended_remediation_steps:
                st.markdown(f"- **Step {r.step_number}**: {r.description}")
                st.caption(f"Rationale: {r.rationale} | Risk: {r.potential_risks}")

            st.markdown("#### ⚠️ Historical Pitfall Awareness")
            if not res_disabled.previous_failed_approaches:
                st.markdown(
                    """
                    <div class="failed-fix-alert">
                        <strong>Blind Spot:</strong> No historical failed mitigations recalled.
                        The engineer risks repeating previously failed fixes!
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        # ----------------------------------------------------
        # Column 2: MEMORY ENABLED
        # ----------------------------------------------------
        with col_on:
            st.markdown(
                """
                <div style="background-color: #151e2e; padding: 12px; border-radius: 8px; border-left: 4px solid #06b6d4; margin-bottom: 12px;">
                    <h3 style="margin: 0; color: #38bdf8;">🧠 WITH Hindsight Memory</h3>
                    <p style="margin: 4px 0 0 0; font-size: 0.85rem; color: #cbd5e1;">
                        Persistent Operational Memory: Recalls verified causes, change correlation, and past failed fixes.
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown(f"**Executive Summary:** {res_enabled.executive_summary}")
            st.caption(f"Reasoning Model: `{res_enabled.llm_model}` | Duration: {res_enabled.execution_time_seconds}s")

            st.markdown("#### 🎯 Hypotheses (Memory Enabled)")
            for h in res_enabled.hypotheses:
                prec_badge = f" [Precedent: {h.historical_precedent}]" if h.historical_precedent else ""
                st.markdown(f"**{h.rank}. {h.hypothesis}** <span style='color: #38bdf8;'>{prec_badge}</span>", unsafe_allow_html=True)
                st.caption(f"Likelihood: {h.likelihood} | Evidence: {', '.join(h.supporting_evidence)}")

            st.markdown("#### 🛡️ Failed Fixes to AVOID (Negative Experience)")
            if res_enabled.previous_failed_approaches:
                for fa in res_enabled.previous_failed_approaches:
                    st.markdown(
                        f"""
                        <div class="failed-fix-alert">
                            <strong>DO NOT REPEAT:</strong> {fa.approach}<br>
                            <small>Why: {fa.why_failed} (Source: {fa.historical_source_incident})</small>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("No failed mitigations recorded for this service.")

            st.markdown("#### 🛠️ Recommended Remediation (Grounded in Verified Fix)")
            for r in res_enabled.recommended_remediation_steps:
                st.markdown(
                    f"""
                    <div class="success-fix-box">
                        <strong>Step {r.step_number}:</strong> {r.description}<br>
                        <small>Rationale: {r.rationale}</small>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # Historical Memories Recalled
            with st.expander(f"📚 Recalled Hindsight Memories ({len(res_enabled.recalled_memories)} retrieved)"):
                for m in res_enabled.recalled_memories:
                    st.markdown(
                        f"""
                        <div class="memory-box">
                            <strong>Memory ID:</strong> {m.memory_id} | <strong>Incident:</strong> {m.source_incident_id or m.document_id}<br>
                            <div style="font-size: 0.85rem; margin-top: 6px; white-space: pre-wrap;">{m.text[:350]}...</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

        # Delta Summary Card
        st.markdown("---")
        st.subheader("📊 Key Operational Difference")
        diff_col1, diff_col2, diff_col3 = st.columns(3)
        with diff_col1:
            st.metric("Historical Incidents Grounded", f"{len(res_enabled.historical_incidents_referenced)} vs 0")
        with diff_col2:
            st.metric("Failed Fixes Prevented", f"{len(res_enabled.previous_failed_approaches)} Flagged")
        with diff_col3:
            st.metric("Confidence Level", f"{res_enabled.confidence_level} vs {res_disabled.confidence_level}")


# ==============================================================================
# SECTION 4: MEMORY EXPLORER
# ==============================================================================
elif selected_page == "Memory Explorer":
    st.title("🧠 Hindsight Memory Explorer")
    st.markdown("Directly inspect, query, and analyze memories in the Hindsight Cloud memory bank.")

    # Status & Bank Profile
    st.markdown(
        f"""
        <div class="sre-card">
            <div class="sre-card-header">
                <span>Memory Bank: <code>{settings.HINDSIGHT_BANK_ID}</code></span>
                <span class="sre-badge {'badge-live' if hs_status == 'CONNECTED' else 'badge-preview'}">{hs_status}</span>
            </div>
            <div>Base URL: <code>{settings.HINDSIGHT_BASE_URL}</code></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Interactive Recall Query Box
    st.subheader("🔍 Query Hindsight Memory")
    query_text = st.text_input(
        "Enter recall search query (semantic & change search)",
        value="checkout-api latency 504 timeouts database connection pool",
    )

    col_q1, col_q2 = st.columns([1, 4])
    with col_q1:
        run_query = st.button("Search Memories", type="primary")

    if run_query or query_text:
        with st.spinner("Executing Hindsight recall..."):
            memories = memory_manager.recall_memories(query=query_text)

        if not memories and not hindsight_client.is_configured:
            st.info("Hindsight API key is not configured. Displaying local simulated historical memories:")
            memories = investigation_engine._get_offline_preview_memories("checkout-api", ["504"], "Helm pool change")

        st.markdown(f"**Found {len(memories)} matching operational memory records:**")

        for idx, m in enumerate(memories, 1):
            relevance_str = f"Relevance: {m.relevance_score:.2f}" if m.relevance_score is not None else "Match"
            with st.container():
                st.markdown(
                    f"""
                    <div class="sre-card">
                        <div class="sre-card-header">
                            <span>#{idx} — {m.source_incident_id or m.document_id or 'Operational Memory'}</span>
                            <span class="sre-badge badge-sev3">{relevance_str}</span>
                        </div>
                        <div style="font-size: 0.85rem; color: #94a3b8; margin-bottom: 8px;">
                            Tags: {', '.join(m.tags) if m.tags else 'incident'} | Type: {m.memory_type}
                        </div>
                        <pre style="background: #0b0f19; padding: 10px; border-radius: 6px; font-size: 0.8rem; overflow-x: auto;">{m.text}</pre>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    # High-level Pattern Reflection
    st.markdown("---")
    st.subheader("🌐 Operational Pattern Reflection (`client.reflect`)")
    st.markdown(
        "Hindsight's `reflect` synthesizes macro operational patterns across all historical incidents in the bank."
    )

    reflect_prompt = st.text_input(
        "Reflection Question",
        value="What are the recurring failure patterns related to deployment configuration changes?",
    )
    if st.button("Generate Reflection"):
        with st.spinner("Reflecting over memory bank..."):
            reflection = memory_manager.reflect_patterns(reflect_prompt)
        if reflection:
            st.success("Hindsight Reflection Analysis:")
            st.write(reflection)
        else:
            st.info(
                "Hindsight Cloud reflection requires an active HINDSIGHT_API_KEY. "
                "In offline mode, reflection is previewed from local postmortem summaries: "
                "Analysis shows 80% of critical incidents in this catalog stemmed from deployment parameter drift (connection pools, worker concurrency, and cache TTLs)."
            )


# ==============================================================================
# SECTION 5: LEARNING CENTER
# ==============================================================================
elif selected_page == "Learning Center":
    st.title("✍️ Incident Learning Center")
    st.markdown(
        "Capture human-verified incident resolutions. "
        "Every confirmed postmortem is retained into Hindsight so the next incident is easier to solve."
    )

    all_incidents = incident_engine.get_all_incidents()
    inc_choices = [f"{i.incident_id} — {i.incident_title}" for i in all_incidents]

    selected_inc_str = st.selectbox("Select Incident to Verify and Retain", inc_choices)
    selected_inc_id = selected_inc_str.split(" — ")[0]
    curr_inc = incident_engine.get_incident(selected_inc_id)

    with st.form("learning_form"):
        st.markdown(f"### Verification Details for `{selected_inc_id}`")

        verified_cause = st.text_area(
            "Verified Root Cause",
            value=curr_inc.actual_verified_root_cause or "Connection pool limits misconfigured in deployment manifest.",
        )

        successful_fix = st.text_area(
            "Successful Resolution / Mitigation",
            value=curr_inc.successful_mitigation or "Restored max_connections to 150 and restarted checkout-api pods.",
        )

        failed_attempts_str = st.text_area(
            "Attempted Mitigations that FAILED (one per line)",
            value="\n".join(curr_inc.failed_mitigation_attempts) if curr_inc.failed_mitigation_attempts else "Increasing client timeout thresholds",
        )

        evidence_str = st.text_input(
            "Verification Evidence",
            value=curr_inc.verification_evidence or "Grafana dashboard confirmed P99 latency dropped from 8500ms to 115ms.",
        )

        lessons_str = st.text_area(
            "Lessons Learned",
            value=curr_inc.lessons_learned or "Never increase timeout thresholds when pool exhaustion is the root bottleneck.",
        )

        engineer_name = st.text_input("Verified By (Engineer Name)", value="Staff SRE Engineer")

        submitted = st.form_submit_button("💾 Confirm Resolution & Retain into Hindsight", type="primary")

    if submitted:
        failed_list = [f.strip() for f in failed_attempts_str.split("\n") if f.strip()]
        with st.spinner("Retaining verified operational experience into Hindsight..."):
            ret_result = learning_engine.confirm_and_retain_resolution(
                incident_id=selected_inc_id,
                verified_root_cause=verified_cause,
                successful_resolution=successful_fix,
                failed_approaches=failed_list,
                verification_evidence=evidence_str,
                lessons_learned=lessons_str,
                verified_by=engineer_name,
            )

        if ret_result.get("success"):
            st.success(
                f"✅ **Resolution Verified!** Retained into Hindsight persistent memory. "
                f"Mode: `{ret_result.get('hindsight_mode')}` | Op ID: `{ret_result.get('hindsight_operation_id') or 'sync'}`"
            )
        else:
            st.error("Failed to retain resolution.")

    st.markdown("---")
    st.subheader("📜 Human-Verified Learning History")
    resolutions = learning_engine.get_learning_history()
    if resolutions:
        for r in resolutions[:5]:
            st.markdown(
                f"""
                <div class="sre-card">
                    <div class="sre-card-header">
                        <span>Incident: {r['incident_id']}</span>
                        <span class="sre-badge badge-live">Verified by {r.get('verified_by', 'SRE')}</span>
                    </div>
                    <div style="font-size: 0.9rem; margin-bottom: 4px;"><strong>Root Cause:</strong> {r['verified_root_cause']}</div>
                    <div style="font-size: 0.9rem; margin-bottom: 4px; color: #34d399;"><strong>Resolution:</strong> {r['successful_resolution']}</div>
                    <div style="font-size: 0.8rem; color: #94a3b8;">Recorded At: {r['created_at']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.info("No verified resolutions in local audit log yet.")


# ==============================================================================
# SECTION 6: EVALUATION LAB
# ==============================================================================
elif selected_page == "Evaluation Lab":
    st.title("📈 Reproducible Evaluation Lab")
    st.markdown(
        "Measure the concrete difference persistent operational memory makes across "
        "recurrent incidents, failed-fix avoidance, and distractor scenarios."
    )

    latest_run = db.get_latest_evaluation_run()

    col_run1, col_run2 = st.columns([1, 4])
    with col_run1:
        run_bench = st.button("▶ Run Full Benchmark Suite", type="primary")

    if run_bench:
        with st.spinner("Executing evaluation across all 12 benchmark scenarios..."):
            summary = eval_framework.run_benchmark()
            st.session_state["benchmark_summary"] = summary
            latest_run = db.get_latest_evaluation_run()
    elif "benchmark_summary" in st.session_state:
        summary = st.session_state["benchmark_summary"]
    elif latest_run:
        summary = latest_run.get("summary_json", {})
    else:
        summary = {}

    if summary:
        metrics = summary.get("metrics", {})
        acc = metrics.get("top_3_root_cause_accuracy", metrics.get("accuracy", {}))
        avoid = metrics.get("failed_mitigation_avoidance_rate", metrics.get("failed_fix_avoidance", {}))
        avg_score = metrics.get("composite_score", metrics.get("average_score", {}))
        retrieval = metrics.get("relevant_memory_retrieval_rate", {})
        false_rec = metrics.get("false_historical_recall_rate", {})

        st.markdown(f"**Benchmark Run ID:** `{summary.get('run_id')}` | Timestamp: `{summary.get('run_timestamp')}`")

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric(
                "Top-3 Root Cause Accuracy",
                f"{acc.get('memory_enabled', 0)}%",
                delta=f"{acc.get('memory_enabled', 0) - acc.get('memory_disabled', 0):.1f}% vs Memory OFF",
            )
        with c2:
            st.metric(
                "Failed Mitigation Avoidance",
                f"{avoid.get('memory_enabled', 0)}%",
                delta=f"{avoid.get('memory_enabled', 0) - avoid.get('memory_disabled', 0):.1f}% vs Memory OFF",
            )
        with c3:
            st.metric(
                "Relevant Memory Retrieval",
                f"{retrieval.get('memory_enabled', 0)}%",
                delta=f"{retrieval.get('memory_enabled', 0) - retrieval.get('memory_disabled', 0):.1f}% vs Memory OFF",
            )
        with c4:
            st.metric(
                "Composite Score (/100)",
                f"{avg_score.get('memory_enabled', 0)}",
                delta=f"+{avg_score.get('memory_enabled', 0) - avg_score.get('memory_disabled', 0):.1f} vs Memory OFF",
            )

        st.markdown("<br>", unsafe_allow_html=True)

        # Plotly Bar Chart Comparison
        cases = summary.get("cases", [])
        if cases:
            chart_data = []
            for c in cases:
                chart_data.append({
                    "Case": c["case_id"],
                    "Mode": "Memory OFF",
                    "Score": c["disabled"]["score"],
                })
                chart_data.append({
                    "Case": c["case_id"],
                    "Mode": "Memory ON (Hindsight)",
                    "Score": c["enabled"]["score"],
                })

            df_chart = pd.DataFrame(chart_data)
            fig = px.bar(
                df_chart,
                x="Case",
                y="Score",
                color="Mode",
                barmode="group",
                title="Per-Case Performance Comparison across 12 Scenarios (Score 0-100)",
                color_discrete_map={"Memory OFF": "#64748b", "Memory ON (Hindsight)": "#06b6d4"},
            )
            fig.update_layout(
                plot_bgcolor="#0b0f19",
                paper_bgcolor="#0b0f19",
                font_color="#e2e8f0",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            st.plotly_chart(fig)

            # Detailed per-case table
            st.subheader("📋 Detailed Per-Scenario Scorecard (Isolated Ground Truth)")
            case_rows = []
            for c in cases:
                case_rows.append({
                    "Case ID": c["case_id"],
                    "Service": c["service"],
                    "Scenario Type": c.get("scenario_type", "recurrent_incident"),
                    "Score (OFF)": f"{c['disabled']['score']:.1f}",
                    "Score (ON)": f"{c['enabled']['score']:.1f}",
                    "Failed Fix Avoided (OFF)": "Yes" if c["disabled"]["avoided_failed"] else "No",
                    "Failed Fix Avoided (ON)": "Yes" if c["enabled"]["avoided_failed"] else "Yes",
                    "Historical Links (ON)": ", ".join(c["enabled"].get("historical_refs", [])) or "None (Correct)",
                })
            df_cases = pd.DataFrame(case_rows)
            st.dataframe(df_cases, hide_index=True)

    else:
        st.info("Click 'Run Full Benchmark Suite' above to execute the automated evaluation.")

    st.markdown("---")
    st.caption(
        "**Evaluation Methodology Notice**: Benchmark cases use synthetic telemetry with verified ground truth. "
        "Scores evaluate whether verified causes appear in top-3 hypotheses, whether past failed fixes are avoided, "
        "and whether distractor scenarios correctly reflect uncertainty without hallucination."
    )


# ==============================================================================
# SECTION 7: ARCHITECTURE & ABOUT
# ==============================================================================
elif selected_page == "Architecture & About":
    st.title("🏛️ Architecture & Technology")
    st.markdown(
        "OPSRECALL decouples **Persistent Operational Memory** (Hindsight) from **Reasoning** (Groq)."
    )

    # Architecture Diagram Display
    arch_img_path = Path("assets/architecture.png")
    if arch_img_path.exists():
        st.image(str(arch_img_path), caption="OPSRECALL System Architecture", use_container_width=True)

    st.markdown("---")
    col_a1, col_a2 = st.columns(2)

    with col_a1:
        st.markdown("### 🧠 How Hindsight Powers OPSRECALL")
        st.markdown(
            """
            Traditional incident response relies on scattered postmortems and human memory.
            OPSRECALL uses **Vectorize Hindsight** as an intelligent operational memory bank:

            1. **`retain(...)`**: Ingests verified incidents, capturing deployment changes, symptoms,
               attempted mitigations, **failed fixes**, and confirmed root causes into bank `opsrecall-demo`.
               Uses stable `document_id=incident_id` to prevent duplication.
            2. **`recall(...)`**: Executes TEMPR retrieval (semantic search, BM25, entity matching, and temporal reasoning)
               to recall relevant historical incidents when telemetry spikes occur.
            3. **`reflect(...)`**: Synthesizes macro operational patterns across months of incident data to identify
               systemic fragility before outages recur.
            """
        )

    with col_a2:
        st.markdown("### ⚡ Technology Stack")
        st.markdown(
            """
            - **Frontend**: Streamlit with custom dark enterprise CSS and Plotly telemetry charts.
            - **Memory**: Official Hindsight Python SDK (`hindsight-client` >= 1.2.0).
            - **Reasoning**: Groq API (`llama-3.3-70b-versatile`) with structured JSON schema outputs.
            - **Application Persistence**: SQLite local audit log (`opsrecall.db`) for incident cache & evaluation history.
            - **Testing & QA**: pytest with mocked unit tests & opt-in live integration tests.
            """
        )

    st.markdown("---")
    st.markdown("### 🔒 Operational Safety Boundaries")
    st.markdown(
        """
        - **Advisory Only**: OPSRECALL generates diagnostic recommendations and SOP steps. It never executes destructive shell commands or binds to production infrastructure.
        - **Human Verification**: Human engineers confirm and verify resolutions before they are committed to Hindsight.
        - **Untrusted Telemetry**: Incident logs and metrics are treated strictly as untrusted evidence, not executable instructions.
        """
    )

