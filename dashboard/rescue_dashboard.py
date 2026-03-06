"""
Rescue Team Dashboard
=====================
Streamlit-based dashboard for real-time incident monitoring,
AI analysis reports, drone fleet status, and uploaded images.
"""

import os
import time
import requests
import streamlit as st
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SERVER_URL = os.getenv("SERVER_URL", "http://localhost:10000")

# Images directory — read files directly from disk for reliability
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGES_DIR = os.path.join(BASE_DIR, "images")

st.set_page_config(
    page_title="Rescue Operations Dashboard",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

st.markdown("""
<style>
    .stApp {
        background-color: #0a0e17;
        color: #f1f5f9;
    }
    .block-container { padding-top: 2rem; }
    .metric-card {
        background: linear-gradient(135deg, #1a2235, #111827);
        padding: 20px;
        border-radius: 14px;
        border: 1px solid rgba(255,255,255,0.06);
        text-align: center;
    }
    .metric-value {
        font-size: 2.4em;
        font-weight: 800;
        background: linear-gradient(135deg, #3b82f6, #06b6d4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .metric-label { color: #94a3b8; font-size: 0.9em; }
    .incident-card {
        background: #1a2235;
        padding: 20px;
        border-radius: 14px;
        border: 1px solid rgba(255,255,255,0.08);
        margin-bottom: 16px;
    }
    .priority-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 10px;
        font-weight: 700;
        font-size: 0.8em;
    }
    .priority-CRITICAL { background: rgba(239,68,68,0.15); color: #ef4444; }
    .priority-HIGH { background: rgba(245,158,11,0.15); color: #f59e0b; }
    .priority-MEDIUM { background: rgba(59,130,246,0.15); color: #3b82f6; }
    .section-header {
        font-size: 1.3em;
        font-weight: 700;
        margin: 24px 0 12px 0;
        padding-bottom: 8px;
        border-bottom: 1px solid rgba(255,255,255,0.06);
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Data Fetching
# ---------------------------------------------------------------------------

@st.cache_data(ttl=5)
def fetch_incidents():
    """Fetch all incidents from the backend."""
    try:
        resp = requests.get(f"{SERVER_URL}/incidents", timeout=5)
        return resp.json() if resp.status_code == 200 else []
    except Exception:
        return []


@st.cache_data(ttl=5)
def fetch_drones():
    """Fetch drone fleet status from the backend."""
    try:
        resp = requests.get(f"{SERVER_URL}/drones", timeout=5)
        return resp.json() if resp.status_code == 200 else []
    except Exception:
        return []


@st.cache_data(ttl=5)
def fetch_incident_detail(incident_id):
    """Fetch full detail for a specific incident including uploaded images."""
    try:
        resp = requests.get(f"{SERVER_URL}/incidents/{incident_id}", timeout=5)
        return resp.json() if resp.status_code == 200 else None
    except Exception:
        return None


def check_server():
    """Check whether the backend server is reachable."""
    try:
        resp = requests.get(f"{SERVER_URL}/", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


def load_image(image_url):
    """
    Load an image by filename. Tries local filesystem first,
    then falls back to HTTP download from the backend.

    Returns:
        File path (str) or image bytes on success, None on failure.
    """
    if not image_url:
        return None

    filename = os.path.basename(image_url)
    local_path = os.path.join(IMAGES_DIR, filename)

    # Prefer filesystem (faster, more reliable on same machine)
    if os.path.exists(local_path):
        return local_path

    # Fallback: fetch via HTTP from the backend
    try:
        resp = requests.get(f"{SERVER_URL}{image_url}", timeout=5)
        if resp.status_code == 200:
            return resp.content
    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("## Rescue Operations")
    st.markdown("---")

    server_online = check_server()
    if server_online:
        st.success("Backend Online")
    else:
        st.error("Backend Offline")
        st.info(f"Expected at: {SERVER_URL}")

    st.markdown("---")

    auto_refresh = st.checkbox("Auto-refresh (5s)", value=True)
    if st.button("Refresh Now"):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.markdown("### Fleet Status")

    drones = fetch_drones()
    for drone in drones:
        status_icon = "●" if drone["status"] == "idle" else "◐"
        status_color = "green" if drone["status"] == "idle" else "orange"
        st.markdown(
            f":{status_color}[{status_icon}] **{drone['name']}** — "
            f"{drone['status'].capitalize()} · {drone['battery']}%"
        )

    st.markdown("---")
    st.caption("DroneRescue AI — DRONExHACK 2026")


# ---------------------------------------------------------------------------
# Main Content
# ---------------------------------------------------------------------------

st.markdown("# Rescue Operations Dashboard")
st.markdown("Real-time incident monitoring, AI analysis, and drone coordination.")

# Overview metrics
incidents = fetch_incidents()
drones = fetch_drones()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{len(incidents)}</div>
        <div class="metric-label">Total Incidents</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    critical = sum(1 for i in incidents if i.get("priority") == "CRITICAL")
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{critical}</div>
        <div class="metric-label">Critical</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    idle = sum(1 for d in drones if d["status"] == "idle")
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{idle}/{len(drones)}</div>
        <div class="metric-label">Drones Available</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    with_drone = sum(1 for i in incidents if i.get("drone_assigned"))
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{with_drone}</div>
        <div class="metric-label">Drones Dispatched</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("")

# ---------------------------------------------------------------------------
# Incident List
# ---------------------------------------------------------------------------

if not incidents:
    st.info(
        "No incidents reported yet. Use the Telegram bot or the "
        "frontend camera to report an incident."
    )
else:
    st.markdown(
        '<div class="section-header">Incident Reports</div>',
        unsafe_allow_html=True,
    )

    for inc in reversed(incidents):
        priority = inc.get("priority", "MEDIUM")
        ai_report = inc.get("ai_report", {})
        drone_info = inc.get("drone_assigned", {})

        with st.expander(
            f"{inc['incident_id']} — "
            f"{inc.get('incident_type', 'Unknown')} [{priority}]",
            expanded=(priority == "CRITICAL"),
        ):
            col_left, col_right = st.columns([2, 1])

            with col_left:
                st.markdown("#### Incident Details")
                st.markdown(f"""
                | Field | Value |
                |---|---|
                | **ID** | `{inc['incident_id']}` |
                | **Type** | {inc.get('incident_type', 'N/A')} |
                | **Priority** | {priority} |
                | **Location** | {inc['latitude']:.6f}, {inc['longitude']:.6f} |
                | **Reported** | {inc.get('timestamp', 'N/A')} |
                """)

                # AI Analysis Report
                if ai_report:
                    st.markdown("#### AI Analysis Report")
                    matched = ', '.join(ai_report.get('matched_objects', [])) or 'None'
                    st.markdown(f"""
                    | Metric | Value |
                    |---|---|
                    | **Incident Type** | {ai_report.get('incident_type', 'N/A')} |
                    | **Confidence** | {ai_report.get('confidence', 0) * 100:.0f}% |
                    | **Objects Detected** | {ai_report.get('object_count', 0)} |
                    | **Matched Objects** | {matched} |
                    | **Model** | {ai_report.get('analysis_model', 'N/A')} |
                    """)

                    recommendation = ai_report.get("recommendation", "N/A")
                    st.info(f"**Recommendation:** {recommendation}")

                    detected = ai_report.get("detected_objects", [])
                    if detected:
                        st.markdown("**Detected Objects:**")
                        for obj in detected:
                            conf_pct = obj.get("confidence", 0) * 100
                            st.markdown(
                                f"- **{obj['label']}** — confidence: {conf_pct:.0f}%"
                            )

                # Drone Assignment
                if drone_info:
                    st.markdown("#### Drone Assignment")
                    st.markdown(f"""
                    | Field | Value |
                    |---|---|
                    | **Drone** | {drone_info.get('drone_name', 'N/A')} ({drone_info.get('drone_id', '')}) |
                    | **Distance** | {drone_info.get('distance_km', '?')} km |
                    | **ETA** | {drone_info.get('eta_minutes', '?')} min |
                    """)
                else:
                    st.warning("No drone assigned to this incident.")

            with col_right:
                # Incident image
                st.markdown("#### Incident Photo")
                image_url = inc.get("image", "")
                img_data = load_image(image_url)
                if img_data:
                    try:
                        st.image(img_data, caption="Incident Photo", width="stretch")
                    except Exception:
                        st.caption("Image could not be displayed.")
                else:
                    st.caption("No incident image available.")

                # Drone camera images
                detail = fetch_incident_detail(inc["incident_id"])
                if detail:
                    drone_images = detail.get("uploaded_images", [])
                    if drone_images:
                        st.markdown("#### Drone Camera Captures")
                        for img_url in drone_images:
                            img_data = load_image(img_url)
                            if img_data:
                                try:
                                    st.image(
                                        img_data,
                                        caption="Drone Capture",
                                        width="stretch",
                                    )
                                except Exception:
                                    st.caption("Drone image could not be displayed.")
                            else:
                                st.caption("Drone image unavailable.")
                    else:
                        st.caption("No drone images uploaded yet.")

# ---------------------------------------------------------------------------
# Auto-refresh
# ---------------------------------------------------------------------------

if auto_refresh:
    time.sleep(5)
    st.cache_data.clear()
    st.rerun()
