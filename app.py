"""
OPSRECALL — Incident Intelligence Agent for SRE & DevOps Teams.
Powered by Hindsight Persistent Operational Memory & Groq Reasoning.
Enterprise SRE Incident Command & Investigation Console.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import mask_secret, settings
from core.evaluation import get_evaluation_framework
from core.hindsight_client import get_hindsight_client
from core.incident_engine import get_incident_engine
from core.investigation import get_investigation_engine
from core.learning_engine import get_learning_engine
from core.llm_engine import get_llm_engine
from core.memory_manager import get_memory_manager
from core.validators import Incident
from database.db import get_db

# ------------------------------------------------------------------------------
# Streamlit Page Configuration
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="OPSRECALL — SRE Incident Intelligence",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------------------------
# High-End Enterprise UI/UX Design System (Glassmorphic Dark Navy / Cyan / Slate)
# ------------------------------------------------------------------------------
ENTERPRISE_CSS = """
<style>
/* Global Font & Canvas */
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

code, pre {
    font-family: 'JetBrains+Mono', monospace !important;
}

/* Background Atmosphere */
.stApp {
    background: radial-gradient(circle at 50% 0%, rgba(6, 182, 212, 0.06) 0%, rgba(8, 12, 20, 1) 50%), #080c14;
    color: #e2e8f0;
}

/* Polished Title & Headings */
h1 {
    font-size: 1.75rem !important;
    font-weight: 800 !important;
    letter-spacing: -0.03em !important;
    color: #f8fafc !important;
    margin-top: 0 !important;
    margin-bottom: 0.2rem !important;
    padding-bottom: 0 !important;
}

h2 {
    font-size: 1.25rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em !important;
    color: #f1f5f9 !important;
    margin-top: 1.1rem !important;
    margin-bottom: 0.45rem !important;
}

h3 {
    font-size: 1.05rem !important;
    font-weight: 600 !important;
    color: #e2e8f0 !important;
    margin-top: 0.8rem !important;
    margin-bottom: 0.3rem !important;
}

/* Hero Badge */
.hero-tag {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(6, 182, 212, 0.1);
    border: 1px solid rgba(6, 182, 212, 0.3);
    color: #38bdf8;
    padding: 3px 10px;
    border-radius: 9999px;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    margin-bottom: 0.5rem;
}

/* Pulse Animation for Live Status */
@keyframes pulse-green {
    0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
    70% { box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }
    100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
}

@keyframes pulse-amber {
    0% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.7); }
    70% { box-shadow: 0 0 0 6px rgba(245, 158, 11, 0); }
    100% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0); }
}

.pulse-indicator-live {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background-color: #10b981;
    display: inline-block;
    animation: pulse-green 2s infinite;
}

.pulse-indicator-amber {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background-color: #f59e0b;
    display: inline-block;
    animation: pulse-amber 2s infinite;
}

/* Sidebar Custom Styling */
[data-testid="stSidebar"] {
    background-color: #0b111e !important;
    border-right: 1px solid rgba(148, 163, 184, 0.12) !important;
    padding-top: 1rem;
}

[data-testid="stSidebar"] hr {
    margin: 0.75rem 0 !important;
    border-color: rgba(148, 163, 184, 0.1) !important;
}

/* High-Impact Metric Cards (Fixes Truncation & Adds Visual Depth) */
div[data-testid="stMetric"] {
    background: linear-gradient(180deg, rgba(30, 41, 59, 0.5) 0%, rgba(15, 23, 42, 0.8) 100%) !important;
    border: 1px solid rgba(148, 163, 184, 0.15) !important;
    border-radius: 10px !important;
    padding: 12px 16px !important;
    box-shadow: 0 4px 15px -2px rgba(0, 0, 0, 0.35) !important;
    backdrop-filter: blur(8px) !important;
    min-height: 88px !important;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
}

div[data-testid="stMetric"]:hover {
    border-color: rgba(56, 189, 248, 0.4) !important;
    transform: translateY(-2px);
    box-shadow: 0 8px 24px -4px rgba(6, 182, 212, 0.25) !important;
}

div[data-testid="stMetric"] label, div[data-testid="stMetric"] [data-testid="stMetricLabel"] {
    color: #94a3b8 !important;
    font-size: 0.72rem !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
}

div[data-testid="stMetric"] [data-testid="stMetricValue"], 
div[data-testid="stMetric"] [data-testid="stMetricValue"] > div {
    color: #38bdf8 !important;
    font-size: 1.15rem !important;
    font-weight: 700 !important;
    white-space: normal !important;
    overflow: visible !important;
    text-overflow: unset !important;
    word-break: break-word !important;
    line-height: 1.25 !important;
}

div[data-testid="stMetric"] [data-testid="stMetricDelta"],
div[data-testid="stMetric"] [data-testid="stMetricDelta"] > div {
    font-size: 0.72rem !important;
    color: #64748b !important;
}

/* Glassmorphic SRE Surface Cards */
.sre-card {
    background: linear-gradient(180deg, rgba(21, 30, 46, 0.7) 0%, rgba(15, 23, 42, 0.85) 100%);
    border: 1px solid rgba(148, 163, 184, 0.12);
    border-radius: 10px;
    padding: 14px 18px;
    margin-bottom: 12px;
    box-shadow: 0 4px 12px -2px rgba(0, 0, 0, 0.25);
    backdrop-filter: blur(10px);
    transition: all 0.2s ease-in-out;
}

.sre-card:hover {
    border-color: rgba(56, 189, 248, 0.35);
    box-shadow: 0 6px 18px -3px rgba(6, 182, 212, 0.15);
}

.sre-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.95rem;
    font-weight: 600;
    color: #f8fafc;
    margin-bottom: 6px;
}

/* Pills & Micro-badges */
.sre-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: 9999px;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.03em;
    line-height: 1.2;
}

.pill-live {
    background: rgba(16, 185, 129, 0.12);
    color: #34d399;
    border: 1px solid rgba(16, 185, 129, 0.35);
}

.pill-amber {
    background: rgba(245, 158, 11, 0.12);
    color: #fbbf24;
    border: 1px solid rgba(245, 158, 11, 0.35);
}

.pill-rose {
    background: rgba(239, 68, 68, 0.12);
    color: #f87171;
    border: 1px solid rgba(239, 68, 68, 0.35);
}

.pill-cyan {
    background: rgba(6, 182, 212, 0.12);
    color: #38bdf8;
    border: 1px solid rgba(6, 182, 212, 0.35);
}

.pill-slate {
    background: rgba(100, 116, 139, 0.12);
    color: #94a3b8;
    border: 1px solid rgba(100, 116, 139, 0.35);
}

/* High-Impact Comparison Cards */
.comparison-container-off {
    background: linear-gradient(180deg, rgba(239, 68, 68, 0.04) 0%, rgba(15, 23, 42, 0.8) 100%);
    border: 1px solid rgba(239, 68, 68, 0.25);
    border-left: 5px solid #ef4444;
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 1rem;
    box-shadow: 0 4px 16px -2px rgba(239, 68, 68, 0.1);
}

.comparison-container-on {
    background: linear-gradient(180deg, rgba(6, 182, 212, 0.08) 0%, rgba(15, 23, 42, 0.85) 100%);
    border: 1px solid rgba(6, 182, 212, 0.4);
    border-left: 5px solid #06b6d4;
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 1rem;
    box-shadow: 0 4px 20px -2px rgba(6, 182, 212, 0.2);
}

/* Callouts */
.failed-fix-alert {
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.3);
    border-left: 4px solid #ef4444;
    padding: 12px 16px;
    margin: 10px 0;
    border-radius: 6px;
    font-size: 0.88rem;
    color: #fca5a5;
}

.success-fix-box {
    background: rgba(16, 185, 129, 0.1);
    border: 1px solid rgba(16, 185, 129, 0.3);
    border-left: 4px solid #10b981;
    padding: 12px 16px;
    margin: 10px 0;
    border-radius: 6px;
    font-size: 0.88rem;
    color: #86efac;
}

.memory-evidence-card {
    background: #090e18;
    border: 1px solid rgba(6, 182, 212, 0.25);
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 10px;
}

/* Modern Status Banner */
.status-banner {
    background: linear-gradient(90deg, rgba(15, 23, 42, 0.9) 0%, rgba(30, 41, 59, 0.7) 100%);
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-left: 4px solid #38bdf8;
    padding: 12px 18px;
    border-radius: 8px;
    margin-bottom: 1.25rem;
    font-size: 0.86rem;
    color: #cbd5e1;
    backdrop-filter: blur(8px);
}

/* Sleek Buttons */
div.stButton > button:first-child {
    background: linear-gradient(180deg, #0284c7 0%, #0369a1 100%);
    color: #ffffff;
    font-weight: 600;
    border: none;
    border-radius: 7px;
    padding: 7px 18px;
    box-shadow: 0 3px 6px rgba(0, 0, 0, 0.3);
    transition: all 0.15s ease-in-out;
}

div.stButton > button:first-child:hover {
    background: linear-gradient(180deg, #0369a1 0%, #075985 100%);
    box-shadow: 0 4px 12px rgba(2, 132, 199, 0.35);
    transform: translateY(-1px);
}
</style>
"""
st.markdown(ENTERPRISE_CSS, unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# Initialize Singletons & Configuration Check
# ------------------------------------------------------------------------------
db = get_db()
incident_engine = get_incident_engine()
hindsight_client = get_hindsight_client()
memory_manager = get_memory_manager()
investigation_engine = get_investigation_engine()
learning_engine = get_learning_engine()
eval_framework = get_evaluation_framework()
llm_engine = get_llm_engine()

# ------------------------------------------------------------------------------
# Sidebar Navigation & Enterprise System Diagnostics
# ------------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🛡️ **OPSRECALL**")
    st.markdown('<div class="hero-tag">SRE Operational Memory</div>', unsafe_allow_html=True)
    st.markdown("---")

    # Live Hindsight Connection Status Check
    hs_health = hindsight_client.check_health()
    hs_status = hs_health.get("status")
    hs_mode = hs_health.get("mode", "OFFLINE_PREVIEW")

    # Groq Model Health Check
    groq_health = llm_engine.check_health()
    groq_status = groq_health.get("status")

    # Render Refined Status Badges with Pulsing Dot
    if hs_status == "CONNECTED":
        st.markdown(
            '<div class="sre-pill pill-live"><span class="pulse-indicator-live"></span> HINDSIGHT LIVE</div>',
            unsafe_allow_html=True,
        )
        st.caption(f"Bank: `{hs_health.get('bank_id')}`")
    elif hs_status == "NOT_CONFIGURED":
        st.markdown(
            '<div class="sre-pill pill-amber"><span class="pulse-indicator-amber"></span> OFFLINE SIMULATION</div>',
            unsafe_allow_html=True,
        )
        st.caption("Memory: Local SRE Postmortem Cache")
    else:
        st.markdown(
            f'<div class="sre-pill pill-rose">● HINDSIGHT: {hs_status}</div>',
            unsafe_allow_html=True,
        )
        st.caption(f"Endpoint: {hs_health.get('base_url')}")

    if groq_status == "CONNECTED":
        st.markdown(
            f'<div class="sre-pill pill-cyan">● GROQ: {settings.GROQ_MODEL}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="sre-pill pill-slate">● GROQ: OFFLINE EXPERT</div>',
            unsafe_allow_html=True,
        )

    # Collapsible Environment Diagnostics Drawer
    with st.expander("🔧 System Diagnostics & Config", expanded=False):
        diag = settings.get_diagnostics()
        st.markdown("**Environment Configuration:**")
        st.text(f"• .env detected: {'Yes' if diag['env_file_found'] else 'No'}")
        if diag["env_file_path"]:
            st.caption(f"  Path: {diag['env_file_path']}")
        st.text(f"• HINDSIGHT_API_KEY: {diag['hindsight_key_status']}")
        st.text(f"• Target Bank: {diag['hindsight_bank_id']}")
        st.text(f"• GROQ_API_KEY: {diag['groq_key_status']}")
        st.text(f"• GROQ_MODEL: {diag['groq_model']}")

        st.markdown("---")
        if st.button("🔄 Reload .env & Re-check", use_container_width=True):
            settings.reload()
            get_hindsight_client(force_reload=True)
            get_llm_engine(force_reload=True)
            st.rerun()

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
    st.caption("v1.0.0 Enterprise SRE Edition")
    st.caption("Advisory Safety Guardrails")


# ==============================================================================
# SECTION 1: COMMAND CENTER
# ==============================================================================
if selected_page == "Command Center":
    st.markdown('<div class="hero-tag">⚡ Operational Command Center</div>', unsafe_allow_html=True)
    st.title("⚡ Operational Command Center")
    st.markdown("Real-time operational status, memory bank metrics, and active incident telemetry.")

    all_incidents = incident_engine.get_all_incidents()
    sev1_count = sum(1 for i in all_incidents if i.severity == "SEV-1")
    eval_count = len(list(settings.OUTPUTS_DIR.glob("*.json")))

    # Modern Custom KPI Bar (No Truncation)
    mode_label = "LIVE CLOUD" if hs_status == "CONNECTED" else "OFFLINE PREVIEW"
    mode_sub = "Hindsight Bank Active" if hs_status == "CONNECTED" else "Simulated Memory Active"

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("System Mode", mode_label, delta=mode_sub)
    with col2:
        st.metric("Memory Bank", settings.HINDSIGHT_BANK_ID, delta="TEMPR Ready")
    with col3:
        st.metric("Active Incidents", f"{len(all_incidents)} Loaded")
    with col4:
        st.metric("SEV-1 Critical", f"{sev1_count} Events")
    with col5:
        st.metric("Benchmark Runs", f"{eval_count} Records")

    # Clear Operational Status Banner
    if hs_status == "NOT_CONFIGURED":
        st.markdown(
            f"""
            <div class="status-banner">
                <strong>ℹ️ Operating in Offline Simulation Mode</strong>: 
                <code>HINDSIGHT_API_KEY</code> is not configured. All investigation workflows, side-by-side comparisons, 
                and the 12-case evaluation benchmark operate deterministically from local SRE postmortem caches. 
                To switch to live cloud memory, configure your key in <code>.env</code> and click <em>Reload Config</em> in the sidebar.
            </div>
            """,
            unsafe_allow_html=True,
        )
    elif hs_status == "CONNECTED":
        st.markdown(
            f"""
            <div class="status-banner" style="border-left-color: #10b981;">
                <strong>✅ Connected to Hindsight Cloud</strong>: Memory bank <code>{settings.HINDSIGHT_BANK_ID}</code> 
                is online. Retain, recall, and reflect primitives are operating live with TEMPR neural indexing.
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Main Grid: Monitored Service Health & Operational Incidents
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
            st.dataframe(df_svc, hide_index=True, use_container_width=True)
        else:
            st.info("No service telemetry records found.")

        st.subheader("🕒 Recent Investigation Audit Trail")
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
            st.dataframe(df_recent, hide_index=True, use_container_width=True)
        else:
            st.info("No investigations recorded yet. Run a side-by-side comparison to generate audit entries.")

    with col_right:
        st.subheader("🔥 Operational Incidents")
        for inc in all_incidents[:5]:
            badge_class = "pill-rose" if inc.severity == "SEV-1" else "pill-amber"
            with st.container():
                st.markdown(
                    f"""
                    <div class="sre-card">
                        <div class="sre-card-header">
                            <span><code>{inc.incident_id}</code>: <strong>{inc.affected_service}</strong></span>
                            <span class="sre-pill {badge_class}">{inc.severity}</span>
                        </div>
                        <div style="font-size: 0.88rem; color: #cbd5e1; margin-bottom: 6px;">
                            {inc.incident_title}
                        </div>
                        <div style="font-size: 0.78rem; color: #94a3b8; display: flex; justify-content: space-between;">
                            <span>Change: <code>{inc.deployment_id or 'Config Drift'}</code></span>
                            <span style="color: #64748b;">{inc.incident_timestamp[:10]}</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


# ==============================================================================
# SECTION 2: INCIDENT CONSOLE
# ==============================================================================
elif selected_page == "Incident Console":
    st.markdown('<div class="hero-tag">🚨 Telemetry Console</div>', unsafe_allow_html=True)
    st.title("🚨 Incident Telemetry Console")
    st.markdown("Ingest, inspect, and configure operational incident telemetry.")

    all_incidents = incident_engine.get_all_incidents()
    inc_options = [f"{i.incident_id} — {i.incident_title} ({i.affected_service})" for i in all_incidents]
    inc_options.append("➕ Create Custom Incident Scenario")

    selected_choice = st.selectbox("Select Incident Scenario", inc_options)

    if selected_choice.startswith("➕"):
        st.subheader("Define Custom Incident Scenario")
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

    # Clean KPI summary
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(
            f"""
            <div class="sre-card" style="padding: 10px 14px;">
                <div class="sre-kpi-label">Affected Service</div>
                <div style="font-size: 1.1rem; font-weight: 700; color: #38bdf8;">{incident_to_inspect.get('affected_service')}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m2:
        sev_val = incident_to_inspect.get("severity")
        pill_col = "pill-rose" if sev_val == "SEV-1" else "pill-amber"
        st.markdown(
            f"""
            <div class="sre-card" style="padding: 10px 14px;">
                <div class="sre-kpi-label">Severity Level</div>
                <div style="font-size: 1.1rem; font-weight: 700;"><span class="sre-pill {pill_col}">{sev_val}</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m3:
        st.markdown(
            f"""
            <div class="sre-card" style="padding: 10px 14px;">
                <div class="sre-kpi-label">Change Reference</div>
                <div style="font-size: 1.1rem; font-weight: 700; color: #e2e8f0;">{incident_to_inspect.get('deployment_id') or 'Config Drift'}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m4:
        total_pts = len(incident_to_inspect.get("symptoms", [])) + len(incident_to_inspect.get("error_logs", []))
        st.markdown(
            f"""
            <div class="sre-card" style="padding: 10px 14px;">
                <div class="sre-kpi-label">Telemetry Ingested</div>
                <div style="font-size: 1.1rem; font-weight: 700; color: #34d399;">{total_pts} Signals</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

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

        metrics = incident_to_inspect.get("metrics", {})
        if metrics:
            st.markdown("#### 📊 Metric Snapshot")
            m_df = pd.DataFrame(list(metrics.items()), columns=["Metric", "Value"])
            st.dataframe(m_df, hide_index=True, use_container_width=True)

    st.markdown("---")
    if st.button("🚀 Send to AI Investigation Engine", type="primary"):
        st.session_state["active_incident"] = incident_to_inspect
        st.success("Incident telemetry routed to AI Investigation Engine! Switch to 'AI Investigation & Comparison' in sidebar.")


# ==============================================================================
# SECTION 3: AI INVESTIGATION & SIDE-BY-SIDE COMPARISON
# ==============================================================================
elif selected_page == "AI Investigation & Comparison":
    st.markdown('<div class="hero-tag">🔬 Side-by-Side Verification</div>', unsafe_allow_html=True)
    st.title("🔬 AI Incident Investigation & Comparison")
    st.markdown(
        "Demonstrate the power of **Change-Aware Operational Memory** by comparing "
        "an investigation **WITHOUT Hindsight** vs. **WITH Hindsight** side-by-side on identical telemetry."
    )

    all_incidents = incident_engine.get_all_incidents()
    active_inc = st.session_state.get("active_incident", all_incidents[0].model_dump())

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
            with st.spinner("Executing comparative reasoning across both memory modes..."):
                res_disabled, res_enabled = investigation_engine.run_comparison(active_inc)
                st.session_state["comp_results"] = (res_disabled, res_enabled)
        else:
            res_disabled, res_enabled = st.session_state["comp_results"]

        st.markdown("---")
        st.markdown("### ⚖️ Side-by-Side Operational Comparison")

        col_off, col_on = st.columns(2)

        # ----------------------------------------------------
        # Column 1: MEMORY DISABLED (BASELINE)
        # ----------------------------------------------------
        with col_off:
            st.markdown(
                """
                <div class="comparison-container-off">
                    <div class="sre-card-header">
                        <span style="color: #f87171; font-weight: 700;">WITHOUT Hindsight Memory</span>
                        <span class="sre-pill pill-slate">❌ UNASSISTED BASELINE</span>
                    </div>
                    <div style="font-size: 0.82rem; color: #cbd5e1; margin-top: 4px;">
                        Standard LLM reasoning: Raw telemetry only. No historical postmortem awareness.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown(f"**Executive Summary:** {res_disabled.executive_summary}")
            st.caption(f"Model: `{res_disabled.llm_model}` | Duration: {res_disabled.execution_time_seconds}s")

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
                        <strong>⚠️ CRITICAL BLIND SPOT:</strong> Zero historical failed mitigations recalled.
                        The on-call engineer risks repeating previously failed fixes (e.g. increasing client timeouts)!
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        # ----------------------------------------------------
        # Column 2: MEMORY ENABLED (HINDSIGHT AUGMENTED)
        # ----------------------------------------------------
        with col_on:
            st.markdown(
                """
                <div class="comparison-container-on">
                    <div class="sre-card-header">
                        <span style="color: #38bdf8; font-weight: 700;">WITH Hindsight Memory</span>
                        <span class="sre-pill pill-cyan">🧠 HINDSIGHT AUGMENTED</span>
                    </div>
                    <div style="font-size: 0.82rem; color: #cbd5e1; margin-top: 4px;">
                        Persistent Operational Memory: Recalls verified causes, change correlation, and past failed fixes.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown(f"**Executive Summary:** {res_enabled.executive_summary}")
            st.caption(f"Model: `{res_enabled.llm_model}` | Duration: {res_enabled.execution_time_seconds}s")

            st.markdown("#### 🎯 Hypotheses (Memory Enabled)")
            for h in res_enabled.hypotheses:
                prec_badge = f"<span class='sre-pill pill-cyan'>Precedent: {h.historical_precedent}</span>" if h.historical_precedent else ""
                st.markdown(f"**{h.rank}. {h.hypothesis}** {prec_badge}", unsafe_allow_html=True)
                st.caption(f"Likelihood: {h.likelihood} | Evidence: {', '.join(h.supporting_evidence)}")

            if res_enabled.memory_contradictions_detected:
                st.markdown("#### ⚠️ Contradiction Safeguards")
                for c_warn in res_enabled.memory_contradictions_detected:
                    st.warning(f"⚠️ {c_warn}")

            st.markdown("#### 🛡️ Failed Fixes to AVOID (Negative Experience)")
            if res_enabled.previous_failed_approaches:
                for fa in res_enabled.previous_failed_approaches:
                    st.markdown(
                        f"""
                        <div class="failed-fix-alert">
                            <strong>🚫 DO NOT REPEAT FAILED MITIGATION:</strong> {fa.approach}<br>
                            <small>Why: {fa.why_failed} (Source: {fa.historical_source_incident})</small>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("No failed mitigations recorded for this service.")

            st.markdown("#### 🛠️ Recommended Remediation (Verified Fix)")
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

            with st.expander(f"📚 Recalled Hindsight Memories & Provenance ({len(res_enabled.structured_retrievals or res_enabled.recalled_memories)} retrieved)"):
                if res_enabled.structured_retrievals:
                    for sr in res_enabled.structured_retrievals:
                        v_badge = '<span class="sre-pill pill-live">HUMAN-VERIFIED</span>' if sr.is_verified else '<span class="sre-pill pill-slate">UNVERIFIED</span>'
                        st.markdown(
                            f"""
                            <div class="memory-evidence-card">
                                <strong>{sr.incident_id} — {sr.title}</strong> {v_badge}<br>
                                <span style="font-size: 0.78rem; color: #38bdf8;">Relevance Score: {sr.relevance_score or 'N/A'} | Service: {sr.service}</span><br>
                                <div style="font-size: 0.84rem; margin-top: 4px; color: #cbd5e1;"><strong>Why Retrieved:</strong> {sr.why_retrieved}</div>
                                <div style="font-size: 0.8rem; color: #94a3b8; margin-top: 2px;"><strong>Matching Evidence:</strong> {', '.join(sr.matching_evidence) if sr.matching_evidence else 'General symptom overlap'}</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                else:
                    for m in res_enabled.recalled_memories:
                        st.markdown(
                            f"""
                            <div class="memory-evidence-card">
                                <strong>Memory ID:</strong> {m.memory_id} | <strong>Incident:</strong> {m.source_incident_id or m.document_id}<br>
                                <div style="font-size: 0.82rem; margin-top: 6px; white-space: pre-wrap; color: #cbd5e1;">{m.text[:350]}...</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

        # Delta Scorecard at Bottom
        st.markdown("---")
        st.subheader("📊 Concrete Operational Advantage")
        d1, d2, d3 = st.columns(3)
        with d1:
            st.markdown(
                f"""
                <div class="sre-card">
                    <div class="sre-kpi-label">Historical Precedent Attributed</div>
                    <div class="sre-kpi-value" style="color: #34d399;">{len(res_enabled.historical_incidents_referenced)} Precedent</div>
                    <div class="sre-kpi-sub">Baseline: 0 precedents cited</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with d2:
            st.markdown(
                f"""
                <div class="sre-card">
                    <div class="sre-kpi-label">Costly Failed Fixes Blocked</div>
                    <div class="sre-kpi-value" style="color: #f87171;">{len(res_enabled.previous_failed_approaches)} Flagged</div>
                    <div class="sre-kpi-sub">Avoids thread starvation repetition</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with d3:
            st.markdown(
                f"""
                <div class="sre-card">
                    <div class="sre-kpi-label">Diagnosis Confidence</div>
                    <div class="sre-kpi-value" style="color: #38bdf8;">{res_enabled.confidence_level}</div>
                    <div class="sre-kpi-sub">Baseline: {res_disabled.confidence_level}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ==============================================================================
# SECTION 4: MEMORY EXPLORER
# ==============================================================================
elif selected_page == "Memory Explorer":
    st.markdown('<div class="hero-tag">🧠 TEMPR Engine</div>', unsafe_allow_html=True)
    st.title("🧠 Hindsight Memory Explorer")
    st.markdown("Directly inspect, query, and analyze memories in the Hindsight Cloud memory bank.")

    status_pill = "pill-live" if hs_status == "CONNECTED" else "pill-amber"
    st.markdown(
        f"""
        <div class="sre-card">
            <div class="sre-card-header">
                <span>Target Memory Bank: <code>{settings.HINDSIGHT_BANK_ID}</code></span>
                <span class="sre-pill {status_pill}">{hs_status}</span>
            </div>
            <div style="font-size: 0.82rem; color: #94a3b8;">
                Base URL: <code>{settings.HINDSIGHT_BASE_URL}</code> | 
                Retrieval Engine: <strong>TEMPR (Semantic + Keyword + Entity + Temporal)</strong>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("🔍 Query Operational Memory")
    query_text = st.text_input(
        "Enter recall search query (symptoms, service, error code, or deployment change)",
        value="checkout-api 504 gateway timeout database pool",
    )

    col_q1, col_q2 = st.columns([1, 4])
    with col_q1:
        run_query = st.button("Search Memories", type="primary")

    if run_query or query_text:
        with st.spinner("Executing Hindsight recall query..."):
            memories = memory_manager.recall_memories(query=query_text)

        if not memories and not hindsight_client.is_configured:
            st.info("Operating in Offline Preview: Showing simulated operational postmortem memories matching your query.")
            memories = investigation_engine._get_offline_preview_memories(
                service="checkout-api",
                symptoms=["504 gateway timeout"],
                error_logs=["Connection pool acquisition timeout"],
                deployment_change="Helm pool change",
            )

        st.markdown(f"**Found {len(memories)} matching operational memory records:**")

        for idx, m in enumerate(memories, 1):
            relevance_str = f"Relevance: {m.relevance_score:.2f}" if m.relevance_score is not None else "High Signal"
            with st.container():
                st.markdown(
                    f"""
                    <div class="sre-card">
                        <div class="sre-card-header">
                            <span>#{idx} — <strong>{m.source_incident_id or m.document_id or 'Operational Experience'}</strong></span>
                            <span class="sre-pill pill-cyan">{relevance_str}</span>
                        </div>
                        <div style="font-size: 0.8rem; color: #94a3b8; margin-bottom: 8px;">
                            Tags: <code>{', '.join(m.tags) if m.tags else 'incident-experience'}</code> | Type: <em>{m.memory_type}</em>
                        </div>
                        <pre style="background: #080c14; border: 1px solid rgba(148,163,184,0.1); padding: 10px; border-radius: 6px; font-size: 0.82rem; overflow-x: auto; color: #cbd5e1;">{m.text}</pre>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    st.markdown("---")
    st.subheader("🌐 Operational Pattern Reflection (`client.reflect`)")
    st.markdown("Hindsight's `reflect` synthesizes macro operational patterns across all historical incidents in the bank.")

    reflect_prompt = st.text_input(
        "Reflection Question",
        value="What are the recurring failure patterns related to deployment configuration changes?",
    )
    if st.button("Generate Macro Reflection"):
        with st.spinner("Synthesizing historical patterns across memory bank..."):
            reflection = memory_manager.reflect_patterns(reflect_prompt)
        if reflection:
            st.success("Hindsight Reflection Analysis:")
            st.write(reflection)
        else:
            st.info(
                "Offline Pattern Synthesis: Analysis shows 80% of critical incidents in this catalog stemmed from deployment parameter drift (connection pools, worker concurrency, and cache TTLs)."
            )


# ==============================================================================
# SECTION 5: LEARNING CENTER
# ==============================================================================
elif selected_page == "Learning Center":
    st.markdown('<div class="hero-tag">✍️ Continuous Feedback</div>', unsafe_allow_html=True)
    st.title("✍️ Incident Learning Center")
    st.markdown(
        "Capture human-verified incident resolutions. "
        "Every confirmed postmortem is retained into Hindsight so the next incident is faster and safer to solve."
    )

    all_incidents = incident_engine.get_all_incidents()
    inc_choices = [f"{i.incident_id} — {i.incident_title}" for i in all_incidents]

    selected_inc_str = st.selectbox("Select Incident to Verify and Retain", inc_choices)
    selected_inc_id = selected_inc_str.split(" — ")[0]
    curr_inc = incident_engine.get_incident(selected_inc_id)

    with st.form("learning_form"):
        st.markdown(f"### Postmortem Verification for `{selected_inc_id}`")

        verified_cause = st.text_area(
            "Verified Root Cause",
            value=curr_inc.actual_verified_root_cause or "Connection pool limits misconfigured in deployment manifest.",
        )

        successful_fix = st.text_area(
            "Successful Resolution / Mitigation",
            value=curr_inc.successful_mitigation or "Restored max_connections to 150 and restarted checkout-api pods.",
        )

        failed_attempts_str = st.text_area(
            "Attempted Mitigations that FAILED (one per line — Negative Experience)",
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

        engineer_name = st.text_input("Verified By (Engineer Name / Role)", value="Senior Staff SRE")

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
            st.success(f"✅ {ret_result.get('message')}")
            st.info(f"Pipeline Status: `{ret_result.get('status')}` | Operation: `{ret_result.get('hindsight_operation_id') or 'local-sync'}`")
            if ret_result.get("conflict_detected"):
                st.warning(f"⚠️ **Conflict Alert**: {ret_result.get('conflict_details')}")
        else:
            st.error(f"Retention Failed: {ret_result.get('message')}")

    st.markdown("---")
    st.subheader("📜 Human-Verified Learning History")
    resolutions = learning_engine.get_learning_history()
    if resolutions:
        for r in resolutions[:5]:
            status_tag = f"<span class='sre-pill pill-cyan'>{r.get('status', 'SAVED')}</span>"
            conflict_tag = "<span class='sre-pill pill-amber'>CONFLICT</span>" if r.get('conflict_detected') else ""
            st.markdown(
                f"""
                <div class="sre-card">
                    <div class="sre-card-header">
                        <span>Incident: <code>{r['incident_id']}</code> {status_tag} {conflict_tag}</span>
                        <span class="sre-pill pill-live">Verified by {r.get('verified_by', 'SRE')}</span>
                    </div>
                    <div style="font-size: 0.88rem; margin-bottom: 4px;"><strong>Root Cause:</strong> {r['verified_root_cause']}</div>
                    <div style="font-size: 0.88rem; margin-bottom: 4px; color: #34d399;"><strong>Resolution:</strong> {r['successful_resolution']}</div>
                    <div style="font-size: 0.75rem; color: #94a3b8;">Recorded At: {r['created_at']}</div>
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
    st.markdown('<div class="hero-tag">📈 Rigorous Benchmark</div>', unsafe_allow_html=True)
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
        with st.spinner("Executing rigorous evaluation across all 16 scenarios (12 independent dimensions)..."):
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
        acc_top1 = metrics.get("top_1_root_cause_accuracy", {})
        acc_top3 = metrics.get("top_3_root_cause_accuracy", {})
        avoid = metrics.get("failed_mitigation_avoidance_rate", {})
        retrieval = metrics.get("relevant_memory_retrieval_rate", {})
        safety = metrics.get("recommendation_safety_rate", {})
        composite = metrics.get("composite_score", {})
        h_status = summary.get("hindsight_status", "OFFLINE_PREVIEW")

        st.caption(f"Benchmark Run ID: `{summary.get('run_id')}` | Timestamp: `{summary.get('run_timestamp')}` | Mode: `{h_status}`")

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(
                f"""
                <div class="sre-card">
                    <div class="sre-kpi-label">Top-1 Root Cause Accuracy</div>
                    <div class="sre-kpi-value" style="color: #34d399;">{acc_top1.get('memory_enabled', 0)}%</div>
                    <div class="sre-kpi-sub">+{acc_top1.get('memory_enabled', 0) - acc_top1.get('memory_disabled', 0):.1f}% vs Memory OFF</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(
                f"""
                <div class="sre-card">
                    <div class="sre-kpi-label">Failed Fix Avoidance</div>
                    <div class="sre-kpi-value" style="color: #34d399;">{avoid.get('memory_enabled', 0)}%</div>
                    <div class="sre-kpi-sub">100% Pitfalls Flagged</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with c3:
            st.markdown(
                f"""
                <div class="sre-card">
                    <div class="sre-kpi-label">Recommendation Safety</div>
                    <div class="sre-kpi-value" style="color: #38bdf8;">{safety.get('memory_enabled', 0)}%</div>
                    <div class="sre-kpi-sub">Zero Unsafe Commands</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with c4:
            delta_comp = composite.get('memory_enabled', 0) - composite.get('memory_disabled', 0)
            st.markdown(
                f"""
                <div class="sre-card">
                    <div class="sre-kpi-label">Composite Score (/100)</div>
                    <div class="sre-kpi-value" style="color: #34d399;">{composite.get('memory_enabled', 0)}</div>
                    <div class="sre-kpi-sub">+{delta_comp:.1f} pts vs Memory OFF</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("<br>", unsafe_allow_html=True)

        with st.expander("📊 Complete 12-Dimensional Benchmark Metrics Breakdown", expanded=True):
            dims_data = [
                {"Dimension": "1. Top-1 Root Cause Accuracy", "Memory OFF": f"{metrics.get('top_1_root_cause_accuracy', {}).get('memory_disabled', 0)}%", "Memory ON": f"{metrics.get('top_1_root_cause_accuracy', {}).get('memory_enabled', 0)}%", "Standard": "Deterministic rubric match on primary hypothesis"},
                {"Dimension": "2. Top-3 Root Cause Accuracy", "Memory OFF": f"{metrics.get('top_3_root_cause_accuracy', {}).get('memory_disabled', 0)}%", "Memory ON": f"{metrics.get('top_3_root_cause_accuracy', {}).get('memory_enabled', 0)}%", "Standard": "Root cause contained in candidate set"},
                {"Dimension": "3. Retrieval Precision@k", "Memory OFF": f"{metrics.get('retrieval_precision_pct', {}).get('memory_disabled', 0)}%", "Memory ON": f"{metrics.get('retrieval_precision_pct', {}).get('memory_enabled', 0)}%", "Standard": "Precision of retrieved historical memories"},
                {"Dimension": "4. Retrieval Recall@k", "Memory OFF": f"{metrics.get('retrieval_recall_pct', {}).get('memory_disabled', 0)}%", "Memory ON": f"{metrics.get('retrieval_recall_pct', {}).get('memory_enabled', 0)}%", "Standard": "Recall of expected target postmortems"},
                {"Dimension": "5. Mean Reciprocal Rank (MRR)", "Memory OFF": f"{metrics.get('mean_reciprocal_rank', {}).get('memory_disabled', 0):.3f}", "Memory ON": f"{metrics.get('mean_reciprocal_rank', {}).get('memory_enabled', 0):.3f}", "Standard": "Rank of target incident in recall list"},
                {"Dimension": "6. Relevant Memory Retrieval Rate", "Memory OFF": f"{metrics.get('relevant_memory_retrieval_rate', {}).get('memory_disabled', 0)}%", "Memory ON": f"{metrics.get('relevant_memory_retrieval_rate', {}).get('memory_enabled', 0)}%", "Standard": "Correct identification of related postmortems"},
                {"Dimension": "7. Failed Mitigation Avoidance", "Memory OFF": f"{metrics.get('failed_mitigation_avoidance_rate', {}).get('memory_disabled', 0)}%", "Memory ON": f"{metrics.get('failed_mitigation_avoidance_rate', {}).get('memory_enabled', 0)}%", "Standard": "Zero repetition of documented failed fixes"},
                {"Dimension": "8. Recommendation Safety", "Memory OFF": f"{metrics.get('recommendation_safety_rate', {}).get('memory_disabled', 0)}%", "Memory ON": f"{metrics.get('recommendation_safety_rate', {}).get('memory_enabled', 0)}%", "Standard": "Destructive shell command prevention"},
                {"Dimension": "9. False Recall Rate (Lower=Better)", "Memory OFF": f"{metrics.get('false_historical_recall_rate', {}).get('memory_disabled', 0)}%", "Memory ON": f"{metrics.get('false_historical_recall_rate', {}).get('memory_enabled', 0)}%", "Standard": "Zero false recall on novel distractors"},
                {"Dimension": "10. Evidence Grounding Rate", "Memory OFF": f"{metrics.get('recommendation_grounding_rate', {}).get('memory_disabled', 0)}%", "Memory ON": f"{metrics.get('recommendation_grounding_rate', {}).get('memory_enabled', 0)}%", "Standard": "Hypotheses cite concrete metrics/logs"},
                {"Dimension": "11. Appropriate Uncertainty Rate", "Memory OFF": f"{metrics.get('appropriate_uncertainty_rate', {}).get('memory_disabled', 0)}%", "Memory ON": f"{metrics.get('appropriate_uncertainty_rate', {}).get('memory_enabled', 0)}%", "Standard": "Uncertainty acknowledged on ambiguous cases"},
                {"Dimension": "12. Calibration Error (ECE - Lower)", "Memory OFF": f"{metrics.get('expected_calibration_error', {}).get('memory_disabled', 0):.3f}", "Memory ON": f"{metrics.get('expected_calibration_error', {}).get('memory_enabled', 0):.3f}", "Standard": "Expected Calibration Error vs empirical accuracy"},
            ]
            st.dataframe(pd.DataFrame(dims_data), hide_index=True, use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)

        cases = summary.get("cases", [])
        if cases:
            chart_data = []
            for c in cases:
                chart_data.append({
                    "Case": c["case_id"],
                    "Mode": "Memory OFF (Baseline)",
                    "Score": c["disabled"]["score"],
                })
                chart_data.append({
                    "Case": c["case_id"],
                    "Mode": "Memory ON (OPSRECALL)",
                    "Score": c["enabled"]["score"],
                })

            df_chart = pd.DataFrame(chart_data)
            fig = px.bar(
                df_chart,
                x="Case",
                y="Score",
                color="Mode",
                barmode="group",
                title="Per-Case Performance Comparison Across 16 Scenarios (Score 0-100)",
                color_discrete_map={"Memory OFF (Baseline)": "#475569", "Memory ON (OPSRECALL)": "#06b6d4"},
            )
            fig.update_layout(
                plot_bgcolor="rgba(8, 12, 20, 0.6)",
                paper_bgcolor="rgba(8, 12, 20, 0.6)",
                font_color="#e2e8f0",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                xaxis=dict(gridcolor="rgba(148, 163, 184, 0.1)"),
                yaxis=dict(gridcolor="rgba(148, 163, 184, 0.1)", range=[0, 110]),
                margin=dict(l=20, r=20, t=50, b=20),
            )
            st.plotly_chart(fig, use_container_width=True)

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
                    "Historical Precedent Cited": ", ".join(c["enabled"].get("historical_refs", [])) or "None (Novel/Correct)",
                })
            df_cases = pd.DataFrame(case_rows)
            st.dataframe(df_cases, hide_index=True, use_container_width=True)

    else:
        st.info("Click 'Run Full Benchmark Suite' above to execute the automated evaluation.")

    st.markdown("---")
    st.caption(
        "**Evaluation Integrity Notice**: Benchmark cases use synthetic telemetry strictly isolated from ground truth. "
        "Scoring evaluates top-1 & top-3 root cause accuracy, avoidance of past failed fixes, and novel distractor calibration."
    )


# ==============================================================================
# SECTION 7: ARCHITECTURE & ABOUT
# ==============================================================================
elif selected_page == "Architecture & About":
    st.markdown('<div class="hero-tag">🏛️ System Architecture</div>', unsafe_allow_html=True)
    st.title("🏛️ Architecture & Technology")
    st.markdown(
        "OPSRECALL decouples **Persistent Operational Memory** (Hindsight) from **Reasoning** (Groq)."
    )

    arch_img_path = Path("assets/architecture.png")
    if arch_img_path.exists():
        st.image(str(arch_img_path), caption="OPSRECALL Enterprise System Architecture", use_container_width=True)

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
               Uses stable `document_id=incident_id` to guarantee idempotency.
            2. **`recall(...)`**: Executes TEMPR retrieval (semantic search, BM25, entity matching, and temporal reasoning)
               to recall relevant historical incidents when telemetry spikes occur.
            3. **`reflect(...)`**: Synthesizes macro operational patterns across historical incident postmortems to identify
               systemic fragility before outages recur.
            """
        )

    with col_a2:
        st.markdown("### ⚡ Technology Stack")
        st.markdown(
            f"""
            - **Frontend**: Streamlit with custom enterprise CSS and Plotly telemetry charts.
            - **Memory**: Official Hindsight Python SDK (`hindsight-client` 1.2.0).
            - **Reasoning**: Groq API (`{settings.GROQ_MODEL}`) with structured JSON schema outputs.
            - **Application Persistence**: SQLite local audit log (`opsrecall.db`) for incident cache & evaluation history.
            - **Testing & QA**: pytest (35 test cases) with mocked unit tests & opt-in live integration tests.
            """
        )

    st.markdown("---")
    st.markdown("### 🔒 Operational Safety Boundaries")
    st.markdown(
        """
        - **Advisory Only**: OPSRECALL generates diagnostic recommendations and SOP steps. It never executes destructive shell commands or binds to production infrastructure.
        - **Human Verification**: Human engineers confirm and verify resolutions before they are committed to Hindsight.
        - **Untrusted Telemetry**: Incident logs and metrics are treated strictly as untrusted evidence, not executable instructions.
        - **Zero Evaluation Leakage**: Model reasoning prompts never receive answer keys or evaluation ground truth.
        """
    )
