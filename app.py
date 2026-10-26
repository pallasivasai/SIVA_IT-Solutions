from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import streamlit as st

from agents import build_team, run_agent_step
from code_builder import CodeBuildError, build_project_files
from ai_providers import ProviderError, ProviderRouter
from github_service import GitHubError, GitHubService
from project_checks import inspect_generated_files
from market_research import build_research_context, collect_market_research
from pipeline_gates import evaluate_market_gate, evaluate_release_gate
from storage import EventStore

st.set_page_config(page_title="SIVA IT Solutions · AI Office", page_icon="", layout="wide")

# This repo is public. Require an owner-configured password before exposing API-backed actions.
import hmac
APP_PASSWORD = os.getenv("APP_PASSWORD", "")
try:
    APP_PASSWORD = APP_PASSWORD or str(st.secrets.get("APP_PASSWORD", ""))
except Exception:
    pass

PASSWORD_CONFIGURED = bool(APP_PASSWORD and APP_PASSWORD != "change-this-to-a-long-random-password")
if PASSWORD_CONFIGURED and not st.session_state.get("authenticated", False):
    st.title(" SIVA IT Solutions · Secure Office Login")
    entered = st.text_input("Office access password", type="password")
    if st.button("Unlock dashboard", type="primary"):
        if hmac.compare_digest(entered, APP_PASSWORD):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()

if not PASSWORD_CONFIGURED:
    st.warning("Read-only mode: set a strong APP_PASSWORD in Streamlit Cloud → App settings → Secrets to enable AI task execution and GitHub PR actions.")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&family=Inter:wght@400;500;600;700;800&display=swap');
.stApp{background:radial-gradient(circle at 12% 0%,#20384a 0%,#101a28 46%,#080d16 100%);color:#edf4ff}.block-container{padding-top:1.15rem;max-width:1600px}
.hero{padding:1.25rem 1.5rem;border:1px solid #365269;border-radius:18px;background:linear-gradient(120deg,rgba(25,54,72,.96),rgba(13,24,40,.96));margin-bottom:1rem;box-shadow:0 12px 30px #0003}
.kicker{color:#76efc5;font-weight:800;letter-spacing:.16em;font-size:.7rem}.hero h1{margin:.35rem 0;font-size:2.1rem;color:#f4f8ff}.hero p{color:#b4c5d8;margin:0}
.person{border:1px solid #293d54;background:rgba(16,27,43,.94);border-radius:16px;padding:14px;min-height:174px;margin-bottom:10px}.person .name{font-size:1.05rem;font-weight:750;color:#eaf2ff}.person .role{font-size:.78rem;color:#8fa2bd;margin:.15rem 0 .6rem}.pill{display:inline-block;border:1px solid #315a55;background:#142e32;padding:3px 8px;border-radius:100px;color:#75e0bb;font-size:.72rem}
.smallmuted{color:#a5b5c9;font-size:.78rem}
/* Keep form labels, typed text, and placeholders readable in Streamlit light input widgets. */
.stApp [data-testid="stTextInput"] label,.stApp [data-testid="stTextArea"] label,.stApp [data-testid="stSelectbox"] label{color:#dce7f5!important;font-weight:600!important}
.stApp [data-testid="stTextInput"] input,.stApp [data-testid="stTextArea"] textarea,.stApp [data-testid="stSelectbox"] div[data-baseweb="select"]{color:#182334!important;background:#f8fafc!important;caret-color:#182334!important;-webkit-text-fill-color:#182334!important}
.stApp [data-testid="stTextInput"] input::placeholder,.stApp [data-testid="stTextArea"] textarea::placeholder{color:#64748b!important;opacity:1!important;-webkit-text-fill-color:#64748b!important}
.stApp [data-testid="stTextArea"] textarea{border:1px solid #94a3b8!important;line-height:1.55!important}
.stApp [data-testid="stTextArea"] textarea:focus,.stApp [data-testid="stTextInput"] input:focus{border-color:#38bdf8!important;box-shadow:0 0 0 2px #38bdf844!important}
.taskline{border-left:3px solid #64e2b7;background:rgba(17,31,48,.9);border-radius:0 10px 10px 0;padding:10px 14px;margin:.45rem 0}div[data-testid="stMetric"]{background:rgba(16,27,43,.85);border:1px solid #26364d;padding:12px 14px;border-radius:14px}
.office-shell{border:3px solid #b8c5c7;border-radius:8px;overflow:hidden;background:#c5d9d3;box-shadow:0 14px 35px #0006}.office-top{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;color:#eaf3f8;background:#182838;font-size:.76rem;letter-spacing:.08em;font-weight:800}
.office-floor{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;padding:20px;background-color:#b8d0c9;background-image:linear-gradient(#90afa6 1px,transparent 1px),linear-gradient(90deg,#90afa6 1px,transparent 1px);background-size:46px 46px}
.agent-station{min-height:155px;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;padding:10px 7px 9px;border:2px solid #77968e;border-radius:5px;background:rgba(222,235,225,.72);box-shadow:inset 0 0 0 3px #d9e6dd}
.agent-sprite{width:45px;height:45px;display:flex;align-items:center;justify-content:center;border:3px solid #233748;border-radius:5px;background:#f0d6ae;font-size:25px;box-shadow:4px 4px 0 #526c69}
.agent-desk{margin-top:8px;width:82%;height:28px;border:3px solid #795c42;border-radius:3px;background:repeating-linear-gradient(90deg,#d8b486 0 12px,#c89e6e 12px 14px);position:relative}.agent-desk:before{content:'▣';position:absolute;left:calc(50% - 11px);top:-20px;width:22px;height:16px;display:grid;place-items:center;color:#7ae9ff;background:#1a2835;border:2px solid #d4dfe0;font-size:10px}
.agent-name{margin-top:9px;font-weight:900;font-size:.78rem;color:#142c34}.agent-role{font-size:.61rem;text-align:center;color:#3c5b5b;min-height:27px}.agent-status{margin-top:5px;padding:4px 7px;border:1px solid #78948c;border-radius:4px;background:#f1f6ec;color:#29463f;font-size:.62rem;font-weight:800;text-align:center}.agent-status.running{background:#c6f6d9;color:#125b3c;border-color:#389b6a}.agent-status.failed{background:#ffe0de;color:#9b2525;border-color:#c85b55}.agent-status.waiting{background:#fff0bf;color:#795514;border-color:#c9a24a}
.office-bottom{padding:10px 14px;background:#182838;color:#9db1c4;font-size:.7rem;display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap}
/* Task-specific agent workbench lives inside AI Project Room. */
.workbench{border:1px solid #2c455d;border-radius:16px;padding:14px;background:linear-gradient(135deg,#101d2c,#0b1320);margin:12px 0 18px}
.workbench-head{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;color:#eaf3ff;margin-bottom:12px}
.workbench-head .sub{color:#9fb3c9;font-size:.8rem}
.workbench-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}
.workbench-agent{position:relative;border:1px solid #314b63;border-radius:18px;padding:15px;background:linear-gradient(155deg,rgba(26,45,65,.98),rgba(12,23,37,.98));min-height:170px;box-shadow:0 10px 28px #0003;transition:transform .22s ease,border-color .22s ease,box-shadow .22s ease;overflow:hidden}
.workbench-agent:before{content:"";position:absolute;inset:0 0 auto;height:3px;background:linear-gradient(90deg,#16c5e7,#5be6b4);opacity:.45}
.workbench-agent:hover{transform:translateY(-3px);border-color:#54cfe7;box-shadow:0 16px 34px #0005}
.workbench-agent .wb-name{letter-spacing:-.02em}.workbench-agent .wb-role{font-size:.72rem}
.wb-icon{box-shadow:0 5px 14px #0003}.wb-person{height:164px;border-radius:14px;background:radial-gradient(ellipse at 50% 8%,#385f7b 0%,#1b354c 63%,#132437 100%);border-color:#456984;box-shadow:inset 0 1px 0 #ffffff18,0 7px 16px #0002}
.wb-state{letter-spacing:.035em;padding:5px 10px}.wb-task{font-size:.79rem;line-height:1.5}.wb-summary{font-size:.72rem;line-height:1.55}
.wb-progress{height:6px;background:#293d52}.wb-progress span{box-shadow:0 0 12px #21d6cb55}
.workbench{border-color:#2b455d;background:radial-gradient(ellipse at top left,#172b3f,#0b1421 70%);box-shadow:0 16px 40px #0003}
.workbench-head{padding:2px 2px 10px;border-bottom:1px solid #263d52}
@media(prefers-reduced-motion:reduce){.workbench-agent{transition:none}.workbench-agent:hover{transform:none}}
.workbench-agent.active{border-color:#29c7f4;box-shadow:0 0 0 1px #29c7f455,0 8px 22px #0004}
.workbench-agent.done{border-color:#248d69}.workbench-agent.failed{border-color:#d65757}.workbench-agent.waiting{opacity:.83}
.wb-top{display:flex;gap:9px;align-items:center}.wb-icon{width:40px;height:40px;border-radius:10px;display:grid;place-items:center;background:#21384e;border:1px solid #42617c;font-size:23px;flex-shrink:0}
/* Professional, code-rendered vector portraits: consistent lighting, facial features, desk and role accents. */
.wb-person{position:relative;width:100%;height:150px;margin:8px 0 10px;border:1px solid #38566b;border-radius:12px;overflow:hidden;background:radial-gradient(ellipse at 50% 10%,#31536d 0%,#1b354c 66%,#16283a 100%);box-shadow:inset 0 1px 0 #ffffff12}
.wb-person svg{display:block;width:100%;height:100%}
.wb-person .avatar-glow{filter:drop-shadow(0 4px 5px #0005)}
.wb-person .avatar-screen{font:700 10px Inter,Arial,sans-serif;fill:#70e9f5}
.wb-person .avatar-prop{font:700 20px Inter,Arial,sans-serif;fill:#eaf5ff}

.wb-name{color:#f2f7ff;font-weight:800;font-size:.95rem}.wb-role{color:#9fb3c9;font-size:.68rem;margin-top:2px}
.wb-state{display:inline-block;margin:10px 0 7px;border-radius:20px;padding:3px 8px;font-size:.66rem;font-weight:800;background:#27384a;color:#c5d5e7}
.workbench-agent.active .wb-state{background:#063e54;color:#65e0ff}.workbench-agent.done .wb-state{background:#103c30;color:#77f0bb}.workbench-agent.failed .wb-state{background:#4a2026;color:#ff9b9b}
.wb-task{color:#e2eaf5;font-size:.76rem;line-height:1.4;min-height:35px;overflow-wrap:anywhere}.wb-summary{color:#8ea4bb;font-size:.68rem;line-height:1.4;margin-top:7px;overflow-wrap:anywhere}
.wb-progress{height:5px;background:#26374a;border-radius:8px;margin-top:10px;overflow:hidden}.wb-progress span{display:block;height:100%;background:linear-gradient(90deg,#0db8dc,#45e1b0);border-radius:8px}
@media(max-width:1100px){.workbench-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:600px){.workbench-grid{grid-template-columns:1fr}.workbench-agent{min-height:0}}

@media(max-width:900px){.office-floor{grid-template-columns:repeat(2,minmax(0,1fr));padding:10px;gap:8px}.agent-station{min-height:140px}.hero h1{font-size:1.6rem}}@media(max-width:480px){.office-floor{grid-template-columns:repeat(2,minmax(0,1fr))}.agent-role{font-size:.55rem}}

/* Enterprise UI polish: restrained palette, clear hierarchy, consistent surfaces. */
.stApp{background:linear-gradient(145deg,#0b1220 0%,#101b2b 48%,#0b1220 100%);color:#e7edf6;font-family:Inter,ui-sans-serif,system-ui,sans-serif}
.block-container{max-width:1680px;padding-top:1.35rem;padding-bottom:2.5rem}
[data-testid="stSidebar"]{background:#f4f6fa;border-right:1px solid #dce3ed}
[data-testid="stSidebar"] *{color:#263449}
[data-testid="stSidebar"] [data-testid="stRadio"] label{padding:7px 10px;border-radius:9px}
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover{background:#e8edf5}
.hero{border:1px solid #263b54;border-radius:18px;background:linear-gradient(120deg,#162b40,#101a2a);padding:1.6rem 1.8rem;box-shadow:0 16px 40px #0003}
.hero h1{font-size:clamp(1.7rem,3vw,2.35rem);letter-spacing:-.04em;font-weight:800}
.kicker{font-size:.68rem;letter-spacing:.18em;color:#55d6c2}
.stButton>button,.stDownloadButton>button,[data-testid="stLinkButton"] a{border-radius:10px;border:1px solid #3b526d;font-weight:650;transition:transform .15s ease,box-shadow .15s ease,border-color .15s ease}
.stButton>button[kind="primary"]{background:linear-gradient(100deg,#087fa8,#0e9b91);border-color:#21b7bd;color:white}
.stButton>button:hover,.stDownloadButton>button:hover{transform:translateY(-1px);border-color:#35c5d8;box-shadow:0 7px 18px #0002}
div[data-testid="stMetric"]{border:1px solid #263b52;background:linear-gradient(145deg,#17263a,#111c2d);border-radius:14px;padding:15px 16px;box-shadow:0 8px 20px #0002}
div[data-testid="stMetric"] label{color:#9fb1c8}
div[data-testid="stMetric"] [data-testid="stMetricValue"]{font-weight:800;letter-spacing:-.03em}
.stApp h1,.stApp h2,.stApp h3{letter-spacing:-.025em}
.stApp hr{border-color:#2b3e54}
.stApp [data-testid="stExpander"]{border:1px solid #2a4058;border-radius:12px;background:#111d2d;overflow:hidden}
.stApp [data-testid="stExpander"] summary{font-weight:650}
.workbench{padding:18px;border-radius:18px;border-color:#293f58;background:linear-gradient(145deg,#142438,#0c1523);box-shadow:0 18px 44px #0003}
.workbench-head{padding:4px 3px 14px;margin-bottom:16px;border-bottom:1px solid #293d52}
.workbench-grid{gap:14px}
.workbench-agent{border:1px solid #2d455f;border-radius:15px;background:linear-gradient(155deg,#1a2b40,#101b2a);padding:16px;box-shadow:0 8px 22px #0002}
.workbench-agent:before{height:2px;opacity:.75}
.workbench-agent:hover{transform:translateY(-2px);box-shadow:0 14px 30px #0004}
.wb-person{height:138px;border-radius:12px;background:linear-gradient(145deg,#213e57,#13283d);border-color:#35546e}
.wb-state{font-size:.65rem;letter-spacing:.07em;text-transform:uppercase}
.wb-task{font-size:.8rem;line-height:1.55}
.wb-summary{font-size:.72rem;line-height:1.55}
.wb-progress{height:5px;background:#2b3c50}
.taskline{border:1px solid #2a4057;border-left:3px solid #36c8ba;border-radius:0 10px 10px 0;background:#122033;padding:13px 15px}
.office-shell{border:1px solid #2d4558;border-radius:14px;background:#111c2b}
.office-top,.office-bottom{background:#101a28}
.office-floor{background-color:#dfe8e5;background-image:linear-gradient(#d1ddd9 1px,transparent 1px),linear-gradient(90deg,#d1ddd9 1px,transparent 1px)}
.agent-station{border:1px solid #b6c9c3;border-radius:10px;box-shadow:0 5px 14px #172b3214}
.agent-sprite{border-radius:50%;box-shadow:0 3px 8px #1d344433}
.agent-desk{border-radius:4px}
@media(max-width:900px){.block-container{padding-left:1rem;padding-right:1rem}.hero{padding:1.2rem}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;transition:none!important}}

</style>
""", unsafe_allow_html=True)

store = EventStore()
router = ProviderRouter()
team = build_team()
if "selected_project" not in st.session_state:
    st.session_state.selected_project = "SIVA IT Solutions"
if "last_run" not in st.session_state:
    st.session_state.last_run = None

with st.sidebar:
    st.markdown("##  SIVA IT Solutions")
    st.caption("AI Company Control Center")
    page = st.radio("Workspace", ["AI Project Room", "Task Board", "Office Floor", "GitHub Pull Requests", "Settings & Setup"])
    st.divider()
    st.markdown("**Agent hand-offs**")
    st.write(" Scout research →  Nova Project Manager plan")
    st.write(" Dev →  QA →  Security")
    st.write(" Security →  GitHub Release Agent")
    st.write(" Leads →  Seller follow-up")
    st.caption("No API keys belong in source code.")

st.markdown("""
<div class="hero">
 <div class="kicker">SIVA IT SOLUTIONS · AGENT OPERATIONS</div>
 <h1>AI Company Office</h1>
 <p>Follow task ownership, workflow hand-offs, provider usage, QA/security reports and review-ready GitHub changes.</p>
</div>""", unsafe_allow_html=True)


events = store.recent_events(limit=300)
failed = sum(e.get("status") == "failed" for e in events)
pr_count = sum(e.get("event_type") == "pull_request_created" for e in events)
m1, m2, m3, m4 = st.columns(4)
m1.metric("AI team roles", len(team))
m2.metric("Recorded events", len(events))
m3.metric("Failed events", failed)
m4.metric("PRs recorded", pr_count)

if page == "Office Floor":
    import html
    st.subheader(" Virtual AI Office")
    st.caption("Auto-refreshes every 5 seconds and displays events from the newest workflow run only. WORKING/DONE/ERROR are event-driven; this refresh does not itself run a background worker.")
    latest: dict[str, dict[str, Any]] = {}
    def canonical_agent_name(raw_name: str) -> str:
        raw = raw_name.strip()
        aliases = {"Dev · Code Builder": "Dev", "GitHub Integrator": "System"}
        if raw in aliases:
            return aliases[raw]
        return raw.split(" · ", 1)[0].strip()
    # Show only the newest workflow run; old DONE events must not masquerade as current activity.
    latest_run_id = str(events[0].get("run_id", "")) if events else ""
    current_run_events = [ev for ev in events if str(ev.get("run_id", "")) == latest_run_id] if latest_run_id else []
    for ev in current_run_events:
        name = canonical_agent_name(str(ev.get("agent_name", "")))
        if name and name not in latest:
            latest[name] = ev
    labels = {"running": ("WORKING", "running"), "completed": ("DONE", "done"), "failed": ("ERROR", "failed"), "waiting_approval": ("WAITING FOR REVIEW", "waiting"), "idle": ("IDLE", "idle"), "code_files_generated": ("DONE", "done"), "agent_started": ("WORKING", "running"), "agent_completed": ("DONE", "done"), "agent_failed": ("ERROR", "failed"), "agent_queued": ("WAITING", "waiting")}
    stations = []
    for agent in team:
        ev = latest.get(agent["name"], {})
        status, css_status = labels.get(ev.get("status", "idle"), ("IDLE", "idle"))
        task = html.escape(str(ev.get("task", "Waiting for workflow hand-off"))[:105])
        summary = html.escape(str(ev.get("summary", "No activity recorded for this agent yet"))[:180])
        name = html.escape(str(agent["name"]))
        role = html.escape(str(agent["role"].split("·")[0].strip()))
        emoji = html.escape(str(agent.get("emoji", "")))
        stations.append('<div class="agent-station"><div class="agent-sprite">' + emoji + '</div><div class="agent-desk"></div><div class="agent-name">' + name + '</div><div class="agent-role">' + role + '</div><div class="agent-status ' + css_status + '">' + status + '</div><div style="margin-top:5px;text-align:center;color:#3c5b5b;font-size:.65rem">' + task + '</div><div style="margin-top:5px;text-align:center;color:#243f45;font-size:.62rem;line-height:1.35">' + summary + '</div></div>')
    office_html = '<div class="office-shell"><div class="office-top"><span>▦ SIVA IT SOLUTIONS · FLOOR 01</span><span>8 SPECIALIST WORKSTATIONS · AUTO-REFRESH 5s</span></div><div class="office-floor">' + "".join(stations) + '</div><div class="office-bottom"><span>● VIEW OF RECORDED EVENTS</span><span>Human approval required · No auto-merge/deploy</span></div></div>'
    st.markdown(office_html, unsafe_allow_html=True)
    st.divider()
    st.subheader(" Workflow lane")
    stages = [("1 · Scout — Market research", "Finds evidence-backed industry gaps and competitors before any product plan."), ("2 · Nova — Product plan", "Defines the MVP, target users and acceptance criteria from research."), ("3 · Dev — Build", "Creates the actual product source and fixes reviewer findings."), ("4 · Tara — QA", "Tests acceptance criteria and reports defects to Dev."), ("5 · Shield — Security", "Reviews security and re-checks fixes; release stays blocked on unresolved high risks."), ("6 · GitHub Integrator — Publish product", "Creates a reviewable product PR after QA, security and static checks pass; never merges or deploys."), ("7 · Lead Research — Buyer leads", "Finds relevant prospects with verifiable public sources after release readiness."), ("8 · Seller — Outreach/follow-up", "Creates prospect-specific messages and a follow-up schedule; sending requires approval.")]
    for title, desc in stages:
        st.markdown('<div class="taskline"><b>' + title + '</b><br><span class="smallmuted">' + desc + '</span></div>', unsafe_allow_html=True)
    with st.expander("View latest agent activity"):
        if not events:
            st.info("No activity recorded yet. Start a workflow in AI Project Room.")
        for ev in events[:35]:
            st.markdown("**" + html.escape(str(ev.get("agent_name", "System"))) + "** · `" + html.escape(str(ev.get("status", "unknown")).upper()) + "` · " + html.escape(str(ev.get("created_at", ""))))
            st.caption(str(ev.get("task", "No task description"))[:240])
    if st.button("Refresh office"):
        st.rerun()

elif page == "Task Board":
    st.subheader(" Task board / activity log")
    ids = sorted({str(e.get("run_id")) for e in events if e.get("run_id")}, reverse=True)
    selected = st.selectbox("Filter by workflow run", ["All runs"] + ids)
    shown = events if selected == "All runs" else [e for e in events if str(e.get("run_id")) == selected]
    if not shown:
        st.info("No tasks recorded yet. Start one in AI Project Room.")
    for ev in shown[:150]:
        st.markdown(f"**{ev.get('agent_name','System')}** · `{ev.get('status','unknown').upper()}` · {ev.get('created_at','')}")
        st.write(ev.get("task", "No task description"))
        if ev.get("summary"):
            st.caption(ev["summary"])
        if ev.get("provider"):
            st.caption(f"Provider: {ev['provider']} · Model: {ev.get('model','configured default')}")
        st.divider()

elif page == "AI Project Room":
    import html
    st.subheader(" AI Project Room · Live Agent Workbench")
    st.write("Enter one product goal below. Every specialist's workstation, assigned task and live status stays visible on this page—no need to open Office Floor. The workflow hands each deliverable to the next agent automatically.")
    agent_board_slot = st.empty()

    def agent_avatar_svg(index: int, emoji: str) -> str:
        # Inline SVG keeps every character crisp and responsive without external image assets.
        palettes = [
            ("#16b6c9", "#25324a", "#f2c49a", "#17344b"),
            ("#d69a45", "#553326", "#e8b58d", "#493a51"),
            ("#168cc7", "#252a36", "#dca77f", "#233a59"),
            ("#9870c9", "#492b3e", "#e9bd98", "#3d3a63"),
            ("#62814f", "#2b2725", "#c9916d", "#2d4b48"),
            ("#3287a7", "#292d37", "#d6a17c", "#273c5a"),
            ("#24a47f", "#5b3928", "#e8b68e", "#284b52"),
            ("#cf7953", "#34242b", "#d99f7a", "#4b3546"),
        ]
        shirt, hair, skin, jacket = palettes[(index - 1) % len(palettes)]
        safe_emoji = html.escape(emoji)
        return (
            '<svg viewBox="0 0 300 150" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
            '<defs><linearGradient id="desk' + str(index) + '" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#7e9da5"/><stop offset="1" stop-color="#334e60"/></linearGradient>'
            '<linearGradient id="screen' + str(index) + '" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#203d54"/><stop offset="1" stop-color="#0b1d2d"/></linearGradient></defs>'
            '<circle cx="150" cy="63" r="53" fill="#ffffff" opacity=".025"/>'
            '<path d="M0 118 H300 V150 H0Z" fill="url(#desk' + str(index) + ')"/>'
            '<path d="M0 119 H300" stroke="#a9c6ce" stroke-opacity=".55"/>'
            '<g class="avatar-glow">'
            '<path d="M95 117 Q97 78 126 72 L174 72 Q203 78 205 117Z" fill="' + shirt + '" stroke="#102638" stroke-width="3"/>'
            '<path d="M126 75 L150 94 L174 75" fill="' + jacket + '" stroke="#d3e3eb" stroke-opacity=".25" stroke-width="2"/>'
            '<path d="M137 59 H163 V78 Q150 89 137 78Z" fill="' + skin + '"/>'
            '<path d="M119 34 Q120 10 150 10 Q180 10 181 35 L178 59 Q174 76 150 78 Q126 76 122 59Z" fill="' + skin + '" stroke="#342f35" stroke-width="2.5"/>'
            '<path d="M118 39 Q112 9 145 6 Q179 4 184 28 L181 40 Q171 28 162 23 Q144 34 119 31Z" fill="' + hair + '" stroke="#1a2635" stroke-width="2"/>'
            '<path d="M127 45 Q133 40 139 45 M161 45 Q167 40 173 45" fill="none" stroke="' + hair + '" stroke-width="3" stroke-linecap="round"/>'
            '<ellipse cx="135" cy="49" rx="3" ry="4" fill="#172737"/><ellipse cx="165" cy="49" rx="3" ry="4" fill="#172737"/>'
            '<circle cx="136" cy="48" r="1" fill="#fff"/><circle cx="166" cy="48" r="1" fill="#fff"/>'
            '<path d="M143 62 Q150 67 157 62" fill="none" stroke="#9d5149" stroke-width="2.5" stroke-linecap="round"/>'
            '<path d="M106 87 Q89 90 81 103 L105 111 M194 87 Q211 91 219 103 L195 111" fill="none" stroke="' + skin + '" stroke-width="13" stroke-linecap="round"/>'
            '</g>'
            '<g><path d="M108 105 L192 105 L198 133 L102 133Z" fill="#d0e2e8" stroke="#162a3b" stroke-width="3"/>'
            '<rect x="111" y="108" width="78" height="23" rx="3" fill="url(#screen' + str(index) + ')" stroke="#5d8399" stroke-width="1.5"/>'
            '<text x="150" y="123" text-anchor="middle" class="avatar-screen">SIVA AI</text>'
            '<path d="M97 135 H203 L193 140 H107Z" fill="#e3edf0" stroke="#627f8b" stroke-width="1.5"/></g>'
            '<g transform="translate(235 22)"><circle cx="0" cy="0" r="17" fill="#102438" stroke="#4e7187" stroke-width="1.5"/><text x="0" y="7" text-anchor="middle" class="avatar-prop">' + safe_emoji + '</text></g>'
            '<path d="M22 24 H61 M22 31 H48 M239 72 H272" stroke="#72d8e8" stroke-opacity=".22" stroke-width="2" stroke-linecap="round"/>'
            '</svg>'
        )

    def draw_project_room_agents(active_run_id: str | None = None) -> None:
        recent = store.recent_events(limit=300)
        run_id_for_board = active_run_id or (
            str(st.session_state.last_run.get("run_id")) if st.session_state.get("last_run") else
            str(recent[0].get("run_id", "")) if recent else ""
        )
        run_events = [ev for ev in recent if str(ev.get("run_id", "")) == run_id_for_board] if run_id_for_board else []
        latest_by_agent: dict[str, dict[str, Any]] = {}
        aliases = {"Dev · Code Builder": "Dev", "Dev · Remediation": "Dev", "GitHub Integrator": "GitHub Integrator"}
        for ev in run_events:
            raw_name = str(ev.get("agent_name", "")).strip()
            canonical = aliases.get(raw_name, raw_name.split(" · ", 1)[0].strip())
            if canonical and canonical not in latest_by_agent:
                latest_by_agent[canonical] = ev
        status_map = {
            "running": ("WORKING NOW", "active", 45),
            "completed": ("COMPLETED", "done", 100),
            "failed": ("ERROR · BLOCKED", "failed", 100),
            "blocked": ("BLOCKED", "failed", 100),
            "waiting": ("WAITING FOR HAND-OFF", "waiting", 0),
            "waiting_approval": ("WAITING FOR APPROVAL", "waiting", 100),
            "idle": ("NOT STARTED", "waiting", 0),
        }
        default_tasks = {
            "Scout": "Research customer pain, competitors and market gaps",
            "Nova": "Turn Scout's evidence into an MVP plan and specialist task breakdown",
            "Dev": "Build the actual product files from Nova's plan",
            "Tara": "Test the generated product against acceptance criteria",
            "Shield": "Review source code and QA findings for security risks",
            "GitHub Integrator": "Package reviewed product and create a human-reviewable PR",
            "Lead Research": "Find relevant buyers with verifiable public evidence",
            "Seller": "Prepare tailored outreach and follow-up from sourced leads",
        }
        cards = []
        for index, agent in enumerate(team, start=1):
            name = str(agent["name"])
            ev = latest_by_agent.get(name, {})
            raw_status = str(ev.get("status", "idle"))
            label, css_state, pct = status_map.get(raw_status, ("WAITING FOR HAND-OFF", "waiting", 0))
            event_type = str(ev.get("event_type", ""))
            if event_type in {"agent_started", "code_generation_started"}:
                label, css_state, pct = "WORKING NOW", "active", 45
            elif event_type in {"agent_completed", "code_files_generated", "code_remediated", "pull_request_created"}:
                label, css_state, pct = "COMPLETED", "done", 100
            elif event_type in {"agent_failed", "code_generation_failed", "remediation_failed", "github_publish_failed"}:
                label, css_state, pct = "ERROR · BLOCKED", "failed", 100
            task_text = html.escape(str(ev.get("task") or default_tasks.get(name, "Waiting for upstream hand-off"))[:210])
            summary_text = html.escape(str(ev.get("summary") or "Waiting for its prerequisite deliverable.")[:180])
            role_text = html.escape(str(agent["role"].split("·")[0].strip()))
            emoji = html.escape(str(agent.get("emoji", "")))
            safe_name = html.escape(name)
            cards.append(
                f'<div class="workbench-agent {css_state}"><div class="wb-top"><div class="wb-icon">{emoji}</div>'
                f'<div><div class="wb-name">{index}. {safe_name}</div><div class="wb-role">{role_text}</div></div></div>'
                f'<div class="wb-person" role="img" aria-label="{safe_name}, illustrated AI specialist at a workstation">{agent_avatar_svg(index, emoji)}</div>'
                f'<div class="wb-state">{label}</div><div class="wb-task"><b>Assigned task</b><br>{task_text}</div>'
                f'<div class="wb-summary">{summary_text}</div><div class="wb-progress"><span style="width:{pct}%"></span></div></div>'
            )
        current = html.escape(run_id_for_board or "No workflow started")
        agent_board_slot.markdown(
            '<div class="workbench"><div class="workbench-head"><div><b> Specialist workstations</b>'
            '<div class="sub">Each card shows the task and latest recorded state · same page · no simulated background worker</div></div>'
            f'<div class="sub">Run: {current}</div></div><div class="workbench-grid">{"".join(cards)}</div></div>',
            unsafe_allow_html=True,
        )

    draw_project_room_agents()
    st.write("Give one product goal. Scout searches the normal public web (not ResearchGate-specific), collects source URLs, and uses the configured AI model to identify customer pain, competitors and gaps. Nova acts as Project Manager: reviews Scout's entire evidence pack, writes the product plan and splits work into specialist hand-offs. Then Dev builds, Tara tests, Shield reviews security, Dev fixes findings, QA/Security re-review, GitHub Integrator prepares a PR, Lead Research finds sourced buyers, and Seller drafts outreach. You do not assign agent tasks manually. Sending outreach requires your approval.")
    with st.form("task_form"):
        project = st.text_input("Project name", value=st.session_state.selected_project)
        task = st.text_area("Requirement", height=170, placeholder="Example: Find an underserved problem for small businesses in India, build a secure MVP, test it, then research suitable buyers and prepare follow-up messages.")
        base_branch = st.text_input("Target base branch for PR (optional)", "main")
        submitted = st.form_submit_button("Start workflow", type="primary", disabled=not PASSWORD_CONFIGURED)
    if submitted:
        if not PASSWORD_CONFIGURED:
            st.warning("AI task execution is disabled until APP_PASSWORD is configured in Streamlit Secrets.")
        elif not task.strip():
            st.error("Enter a task description first.")
        else:
            run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            current_project = project.strip() or "Unnamed project"
            st.session_state.selected_project = current_project
            outputs: dict[str, Any] = {}
            generated_files: dict[str, str] = {}
            progress = st.status("Starting task workflow…", expanded=True)
            # Queue every specialist up front so a failed hand-off never leaves
            # downstream stations misleadingly showing IDLE.
            queued_tasks = {
                "Scout": "Search public web sources and identify customer pain and market gaps",
                "Nova": "Review Scout evidence; create product plan and split specialist tasks",
                "Dev": "Build actual product files from Nova's plan",
                "Tara": "Test generated product against acceptance criteria",
                "Shield": "Review source and QA findings for security risks",
                "GitHub Integrator": "Publish reviewed product as a feature branch and PR after gates pass",
                "Lead Research": "Find sourced buyers after release readiness",
                "Seller": "Prepare tailored outreach and follow-up from verified leads",
            }
            for queued_agent in team:
                store.add_event(
                    run_id, queued_agent["name"], queued_tasks.get(queued_agent["name"], "Waiting for hand-off"),
                    "agent_queued", "waiting",
                    summary="Queued; waiting for required upstream hand-off and gates.",
                )
            draw_project_room_agents(run_id)
            try:
                # Record Scout as the current owner before external research starts so the
                # Virtual Office shows the real active task even if web search fails.
                store.add_event(run_id, "Scout", task, "agent_started", "running",
                                summary="Scout is collecting public market evidence and competitor sources")
                draw_project_room_agents(run_id)
                progress.write(" Scout · Market Researcher — collecting public evidence and competitor sources…")
                research_pack = collect_market_research(task)
                outputs["market_evidence"] = research_pack["context"]
                outputs["market_sources"] = research_pack["results"]
                outputs["market_search_diagnostics"] = research_pack["diagnostics"]
                # Gate against actual search-result URLs, not URLs parsed from formatted prose.
                market_gate = evaluate_market_gate("\n".join(research_pack["source_urls"]))
                outputs["market_gate"] = market_gate
                store.add_event(run_id, "Research Gate", task, "market_gate_checked",
                                "completed" if market_gate["passed"] else "failed",
                                summary=f"{market_gate['source_count']} distinct source URLs; passed={market_gate['passed']}")
                if not market_gate["passed"]:
                    store.add_event(run_id, "Scout", task, "agent_failed", "failed",
                                    summary=market_gate["reason"])
                    outputs["research"] = (
                        "SCOUT BLOCKED — public web research did not return enough distinct source URLs. "
                        "The agent did not fabricate evidence. Check Streamlit dependency/network access and retry.\n\n"
                        + outputs["market_evidence"]
                    )
                    outputs["workflow_blocker"] = market_gate["reason"]
                    st.session_state.last_run = {
                        "run_id": run_id, "project": current_project, "task": task,
                        "outputs": outputs, "files": {}, "base_branch": base_branch,
                    }
                    progress.update(label="Workflow blocked · Scout needs public sources",
                                    state="error", expanded=True)
                    st.error(market_gate["reason"])
                    draw_project_room_agents(run_id)
                    st.info("Scout's task and blocker are shown in the specialist workstations above. Product planning stays blocked until real public sources are available.")
                else:
                    progress.write(f"Research gate passed with {market_gate['source_count']} distinct source URLs")
                if market_gate["passed"]:
                    scout = run_agent_step(router, store, run_id, team[0], current_project, task, outputs)
                    outputs["research"] = scout["output"]
                    draw_project_room_agents(run_id)
                    progress.write("Scout completed gap research")
                    progress.write(" Nova · Project Manager — reviewing Scout's evidence and creating the product plan/task breakdown…")
                    store.add_event(run_id, "Nova", task, "agent_started", "running", summary="Reviewing Scout's evidence and planning the MVP")
                    draw_project_room_agents(run_id)
                    strategy = run_agent_step(
                        router, store, run_id, team[1], current_project,
                        task,
                        outputs,
                    )
                    outputs["product_strategy"] = strategy["output"]
                    draw_project_room_agents(run_id)
                    progress.write("Nova completed the project plan and specialist task breakdown")
                    dev_handoff = (
                        "DEV IMPLEMENTATION HAND-OFF FROM NOVA (PROJECT MANAGER). Build the product described in Nova's approved plan; "
                        "do not merely write recommendations. Follow the MVP scope and acceptance criteria exactly. "
                        "Your output must specify concrete files, modules, interfaces, data model, validation, error handling, and tests. "
                        "The next code-builder step will generate the actual source files from your implementation notes.\n\n"
                        "USER REQUIREMENT:\n" + task + "\n\nPRODUCT PLAN:\n" +
                        outputs.get("product_strategy", "")[:12000] + "\n\nSCOUT EVIDENCE:\n" +
                        outputs.get("research", "")[:6000]
                    )
                    progress.write(" Dev · Software Engineer — accepting Nova's plan and preparing implementation…")
                    store.add_event(run_id, "Dev", dev_handoff, "agent_started", "running", summary="Translating Nova's plan into an implementation design")
                    draw_project_room_agents(run_id)
                    implementation = run_agent_step(router, store, run_id, team[2], current_project, dev_handoff, outputs)
                    outputs["implementation"] = implementation["output"]
                    store.add_event(run_id, "Dev", dev_handoff, "implementation_ready", "completed",
                                    summary="Implementation hand-off prepared for source generation")
                    draw_project_room_agents(run_id)
                    progress.write("Dev implementation hand-off ready; generating actual source files next")
                    generated_files: dict[str, str] = {}
                    try:
                        progress.write(" Dev · Code Builder — generating the actual MVP source files from Nova's plan…")
                        store.add_event(run_id, "Dev · Code Builder", task, "code_generation_started", "running",
                                        summary="Generating actual product source files from the project plan")
                        draw_project_room_agents(run_id)
                        build_brief = (
                            task + "\n\nPRODUCT STRATEGY / GAP TO FILL:\n" + outputs["product_strategy"] +
                            "\n\nSCOUT RESEARCH / SOURCE EVIDENCE:\n" + outputs["market_evidence"] +
                            "\n\nIMPLEMENTATION DESIGN FROM DEV:\n" + outputs["implementation"]
                        )
                        generated_files = build_project_files(router, current_project, build_brief, outputs["product_strategy"], outputs["implementation"])
                        outputs["generated_files_summary"] = "\n".join(f"- {path}" for path in generated_files)
                        outputs["generated_files_context"] = "\n\n".join(f"### {path}\n{body[:6000]}" for path, body in list(generated_files.items())[:8])[:24000]
                        static_check = inspect_generated_files(generated_files)
                        outputs["static_qa"] = "\n".join("- " + item["status"] + ": " + item["detail"] for item in static_check["checks"])
                        outputs["generated_files_context"] += "\n\n## Deterministic non-executing checks\n" + outputs["static_qa"]
                        store.add_event(run_id, "Dev · Code Builder", task, "code_files_generated", "completed", summary=f"Generated {len(generated_files)} reviewable source files")
                        draw_project_room_agents(run_id)
                        progress.write(f"Generated {len(generated_files)} real source files")
                    except Exception as exc:
                        outputs["code_build_error"] = f"{type(exc).__name__}: {exc}"
                        store.add_event(run_id, "Dev", task, "code_generation_failed", "failed",
                                        summary=outputs["code_build_error"])
                        draw_project_room_agents(run_id)
                        progress.error("Dev could not generate the product source files: " + outputs["code_build_error"])
                    if generated_files:
                        store.add_event(run_id, "Tara", task, "agent_started", "running", summary="Inspecting generated files against Nova's acceptance criteria")
                        draw_project_room_agents(run_id)
                        qa = run_agent_step(router, store, run_id, team[3], current_project,
                                            "QA HAND-OFF: inspect the actual generated source files and Nova's acceptance criteria. "
                                            "Run/assess the provided tests where possible, list concrete defects, and do not claim execution without evidence.\n\n" + task,
                                            outputs)
                        outputs["qa"] = qa["output"]
                        draw_project_room_agents(run_id)
                        progress.write("Tara completed the QA report on generated files")
                        store.add_event(run_id, "Shield", task, "agent_started", "running", summary="Reviewing generated source and QA findings for security risks")
                        draw_project_room_agents(run_id)
                        security = run_agent_step(router, store, run_id, team[4], current_project,
                                                  "SECURITY HAND-OFF: inspect the actual generated source files, dependencies and QA findings. "
                                                  "Report concrete vulnerabilities and remediation. Do not claim scans were executed unless they were.\n\n" + task,
                                                  outputs)
                        outputs["security"] = security["output"]
                        draw_project_room_agents(run_id)
                        progress.write("Shield completed the security review on generated files")
                    else:
                        outputs["qa"] = "RELEASE_GATE: FAIL\nQA not run because Dev did not generate product source files. Fix the build blocker and retry."
                        outputs["security"] = "RELEASE_GATE: FAIL\nSecurity review not run because there are no generated source files to inspect."
                        store.add_event(run_id, "Tara", task, "agent_failed", "failed", summary="QA skipped: Dev source generation failed")
                        store.add_event(run_id, "Shield", task, "agent_failed", "failed", summary="Security review skipped: no source files to inspect")
                        progress.error("QA and Security were correctly blocked because Dev did not generate source files.")
                    # One bounded feedback loop: Dev receives the actual QA/security findings,
                    # regenerates the source tree, and both reviewers inspect the revised files.
                    if generated_files:
                        progress.write("Dev is receiving Tara/Shield findings for one remediation pass…")
                        review_feedback = (
                            "REQUIRED REMEDIATION PASS. Review the existing source files and fix concrete findings below. "
                            "Preserve unrelated functionality. Return file-level implementation notes; do not claim tests were run.\n\n"
                            "CURRENT SOURCE FILES:\n" + outputs.get("generated_files_context", "")[:18000] +
                            "\n\nTARA QA FINDINGS:\n" + outputs.get("qa", "")[:7000] +
                            "\n\nSHIELD SECURITY FINDINGS:\n" + outputs.get("security", "")[:7000] +
                            "\n\nSTATIC CHECK RESULTS:\n" + outputs.get("static_qa", "")
                        )
                        try:
                            store.add_event(run_id, "Dev · Remediation", review_feedback, "agent_started", "running", summary="Applying QA and security findings to the product")
                            draw_project_room_agents(run_id)
                            remediation = run_agent_step(router, store, run_id, team[2], current_project, review_feedback, outputs)
                            outputs["remediation"] = remediation["output"]
                            revised_brief = (
                                task + "\n\nAPPROVED PRODUCT STRATEGY:\n" + outputs.get("product_strategy", "") +
                                "\n\nMARKET EVIDENCE:\n" + outputs.get("market_evidence", "") +
                                "\n\nQA FINDINGS TO FIX:\n" + outputs.get("qa", "") +
                                "\n\nSECURITY FINDINGS TO FIX:\n" + outputs.get("security", "") +
                                "\n\nDEV REMEDIATION NOTES:\n" + outputs["remediation"]
                            )
                            revised_files = build_project_files(
                                router, current_project, revised_brief,
                                outputs.get("product_strategy", ""), outputs["remediation"]
                            )
                            revised_checks = inspect_generated_files(revised_files)
                            generated_files = revised_files
                            outputs["generated_files_summary"] = "\n".join(f"- {path}" for path in generated_files)
                            outputs["generated_files_context"] = "\n\n".join(
                                f"### {path}\n{body[:6000]}" for path, body in list(generated_files.items())[:8]
                            )[:24000]
                            outputs["static_qa"] = "\n".join(
                                "- " + item["status"] + ": " + item["detail"] for item in revised_checks["checks"]
                            )
                            outputs["generated_files_context"] += "\n\n## Deterministic non-executing checks\n" + outputs["static_qa"]
                            store.add_event(run_id, "Dev · Remediation", task, "code_remediated", "completed",
                                            summary=f"Regenerated {len(generated_files)} source files from QA/security feedback")
                            progress.write("Revised source generated; Tara and Shield are re-reviewing it…")
                            store.add_event(run_id, "Tara", task, "agent_started", "running", summary="Re-testing the revised source after remediation")
                            draw_project_room_agents(run_id)
                            outputs["qa"] = run_agent_step(router, store, run_id, team[3], current_project,
                                                           "RE-REVIEW revised source. Verify previous findings are fixed and identify remaining defects. " + task,
                                                           outputs)["output"]
                            store.add_event(run_id, "Shield", task, "agent_started", "running", summary="Re-checking security findings after remediation")
                            draw_project_room_agents(run_id)
                            outputs["security"] = run_agent_step(router, store, run_id, team[4], current_project,
                                                                 "RE-REVIEW revised source. Verify previous security findings are fixed and identify residual risks. " + task,
                                                                 outputs)["output"]
                        except CodeBuildError as exc:
                            outputs["remediation_error"] = str(exc)
                            store.add_event(run_id, "Dev · Remediation", task, "remediation_failed", "failed", summary=str(exc))
                            progress.warning(f"Remediation pass did not produce revised source: {exc}")
                    final_static_checks = inspect_generated_files(generated_files) if generated_files else {"passed": False, "failures": 1, "warnings": 0, "checks": []}
                    outputs["final_static_checks"] = final_static_checks
                    release_gate = evaluate_release_gate(
                        generated_files, final_static_checks, outputs.get("qa", ""), outputs.get("security", "")
                    )
                    outputs["release_gate"] = release_gate
                    store.add_event(run_id, "Final Release Auditor", task, "release_gate_checked",
                                    "completed" if release_gate["passed"] else "blocked",
                                    summary="; ".join(release_gate["reasons"]) if release_gate["reasons"] else "QA, security and deterministic checks passed")
                    if release_gate["passed"]:
                        progress.write("Release gate passed. GitHub Integrator is publishing the reviewed product bundle…")
                        try:
                            store.add_event(run_id, "GitHub Integrator", task, "agent_started", "running", summary="Preparing the reviewed product for a human-reviewable GitHub PR")
                            draw_project_room_agents(run_id)
                            github_agent = run_agent_step(
                                router, store, run_id, team[5], current_project,
                                "Publish the completed product bundle to GitHub as a reviewable pull request. "
                                "Base branch: " + (base_branch.strip() or "main") +
                                ". Do not merge or deploy. Report the exact PR URL and branch.",
                                outputs,
                            )
                            outputs["github_release"] = github_agent["output"]
                            release_result = {
                                "run_id": run_id, "project": current_project, "task": task,
                                "outputs": outputs, "files": generated_files,
                            }
                            github_service = GitHubService()
                            github_bundle = github_service.generate_file_bundle(release_result)
                            github_pr = github_service.create_change_request(
                                current_project, task, github_bundle,
                                base_branch=base_branch.strip() or "main",
                            )
                            outputs["github_pr"] = github_pr
                            store.add_event(
                                run_id, "GitHub Integrator", task, "pull_request_created", "completed",
                                summary=f"PR #{github_pr['number']}: {github_pr['url']}",
                            )
                            progress.write(f"GitHub Integrator created PR #{github_pr['number']}")
                        except Exception as exc:
                            outputs["github_publish_error"] = f"{type(exc).__name__}: {exc}"
                            store.add_event(
                                run_id, "GitHub Integrator", task, "github_publish_failed", "failed",
                                summary=outputs["github_publish_error"],
                            )
                            if "403" in raw_error or "Resource not accessible by personal access token" in raw_error:
                                outputs["github_publish_error"] = (
                                    "GitHub rejected the configured token (HTTP 403). Grant this token access to "
                                    "pallasivasai/SIVA_IT-Solutions with Contents: Read and write and Pull requests: "
                                    "Read and write permissions. Then replace GITHUB_TOKEN in Streamlit Cloud → "
                                    "App settings → Secrets and reboot the app. Never paste the token into chat."
                                )
                            else:
                                outputs["github_publish_error"] = raw_error
                            progress.error("GitHub PR creation failed. " + outputs["github_publish_error"])
                        progress.write("Lead Research is finding sourced, relevant prospects…")
                        store.add_event(run_id, "Lead Research", task, "agent_started", "running", summary="Searching for sourced buyers relevant to the finished product")
                        draw_project_room_agents(run_id)
                        lead_research_pack = collect_market_research(
                            "businesses and companies likely to buy " + current_project + " in India and relevant target markets public company websites contact page"
                        )
                        outputs["lead_evidence"] = lead_research_pack["context"]
                        outputs["lead_source_rows"] = lead_research_pack["results"]
                        leads = run_agent_step(router, store, run_id, team[6], current_project, task, outputs)
                        outputs["leads"] = leads["output"]
                        draw_project_room_agents(run_id)
                        progress.write("Lead Research handed sourced prospect findings to Seller.")
                        store.add_event(run_id, "Seller", task, "agent_started", "running", summary="Drafting tailored outreach and follow-up for sourced prospects")
                        draw_project_room_agents(run_id)
                        sales = run_agent_step(router, store, run_id, team[7], current_project, task, outputs)
                        outputs["sales"] = sales["output"]
                        try:
                            from leads_export import build_leads_workbook, save_leads_workbook
                            lead_rows = [
                                {"Company / Result": row.get("title", ""), "Public Source URL": row.get("url", ""),
                                 "Evidence / Search Snippet": row.get("snippet", ""),
                                 "Contact Status": "Needs verification — no contact details inferred",
                                 "Product": current_project, "Research Run ID": run_id}
                                for row in outputs.get("lead_source_rows", [])
                                if row.get("url", "").startswith(("https://", "http://"))
                            ]
                            workbook_bytes = build_leads_workbook(lead_rows, current_project, run_id)
                            workbook_path = save_leads_workbook(workbook_bytes, current_project, run_id)
                            outputs["leads_workbook_bytes"] = workbook_bytes
                            outputs["leads_workbook_path"] = workbook_path
                            store.add_event(run_id, "Lead Research", task, "leads_workbook_created", "completed",
                                            summary=f"Saved {len(lead_rows)} sourced research rows to {workbook_path}")
                            try:
                                github_service = GitHubService()
                                workbook_pr = github_service.create_binary_change_request(
                                    project_name=current_project,
                                    task=f"Add sourced lead research workbook for {current_project}",
                                    path=f"sales-leads/{run_id[:8]}-{GitHubService._slug(current_project)}-leads.xlsx",
                                    content=workbook_bytes, base_branch=base_branch.strip() or "main")
                                outputs["leads_github_pr"] = workbook_pr
                                store.add_event(run_id, "Lead Research", task, "leads_workbook_pr_created", "completed",
                                                summary=f"Lead workbook PR #{workbook_pr['number']}: {workbook_pr['url']}")
                            except Exception as publish_exc:
                                outputs["leads_github_error"] = f"{type(publish_exc).__name__}: {publish_exc}"
                                store.add_event(run_id, "Lead Research", task, "leads_workbook_publish_failed", "failed",
                                                summary=outputs["leads_github_error"])
                        except Exception as export_exc:
                            outputs["leads_export_error"] = f"{type(export_exc).__name__}: {export_exc}"
                            progress.warning("Lead workbook export failed: " + outputs["leads_export_error"])
                        progress.write("Seller prepared tailored outreach and a follow-up sequence; no messages were sent.")
                    else:
                        outputs["sales"] = "BLOCKED: Seller is not allowed to proceed until QA, security, and deterministic source checks explicitly pass.\n" + "\n".join(release_gate["reasons"])
                        store.add_event(run_id, "Seller", task, "sales_blocked_by_release_gate", "blocked",
                                        summary="; ".join(release_gate["reasons"]))
                        progress.warning("Release gate blocked the product. Seller and GitHub PR actions remain disabled until blockers are fixed.")
                    st.session_state.last_run = {"run_id":run_id,"project":current_project,"task":task,"outputs":outputs,"files":generated_files,"base_branch":base_branch}
                if market_gate["passed"]:
                    progress.update(
                        label="Workflow completed" if release_gate["passed"] else "Workflow blocked by release gate",
                        state="complete" if release_gate["passed"] else "error",
                        expanded=not release_gate["passed"],
                    )
            except ProviderError as exc:
                error_text = f"{type(exc).__name__}: {exc}"
                store.add_event(run_id, "System", task, "workflow_failed", "failed", summary=error_text)
                st.session_state.last_run = {
                    "run_id": run_id, "project": current_project, "task": task,
                    "outputs": {**outputs, "workflow_error": error_text},
                    "files": locals().get("generated_files", {}), "base_branch": base_branch,
                }
                progress.update(label="Workflow stopped — provider error", state="error", expanded=True)
                st.error("Workflow stopped at the last recorded agent. " + error_text)
                draw_project_room_agents(run_id)
                st.info("The workstations above show completed agents, the failing agent and downstream hand-offs on this same page.")
            except Exception as exc:
                error_text = f"{type(exc).__name__}: {exc}"
                store.add_event(run_id, "System", task, "workflow_failed", "failed", summary=error_text)
                st.session_state.last_run = {
                    "run_id": run_id, "project": current_project, "task": task,
                    "outputs": {**outputs, "workflow_error": error_text},
                    "files": locals().get("generated_files", {}), "base_branch": base_branch,
                }
                progress.update(label="Workflow stopped — see recorded error", state="error", expanded=True)
                st.error("Workflow stopped: " + error_text)
                st.info("Office Floor will show completed agents as DONE, the failing agent as ERROR, and downstream agents as WAITING.")
    draw_project_room_agents()
    result = st.session_state.last_run
    if result:
        st.markdown(f"### Latest run · {result['project']}")
        st.caption(f"Run ID: {result['run_id']}")
        if result.get("outputs", {}).get("workflow_error"):
            st.error("Workflow error: " + str(result["outputs"]["workflow_error"]))
        if result.get("outputs", {}).get("market_gate"):
            with st.expander(" Research gate evidence", expanded=False):
                st.json(result["outputs"]["market_gate"])
        if result.get("outputs", {}).get("release_gate"):
            with st.expander(" Final release gate", expanded=True):
                st.json(result["outputs"]["release_gate"])
        for label, key in [(" Industry gap research","research"),(" Product plan","product_strategy"),(" Developer hand-off","implementation"),(" QA report","qa"),(" Security review","security"),(" GitHub release agent","github_release"),(" Sourced sales leads","leads"),(" Seller outreach + follow-up plan","sales")]:
            with st.expander(label, expanded=(key == "plan")):
                st.markdown(result["outputs"].get(key, "No report available."))
        if result.get("code_build_error"):
            st.error(f"Product source files were not generated: {result['code_build_error']}")
        generated_files = result.get("files", {})
        if generated_files:
            st.success(f"Developer generated {len(generated_files)} actual project files. They will be packaged under products/<product-name>/ in the PR.")
            for path, body in generated_files.items():
                with st.expander(path, expanded=False):
                    st.code(body, language=path.rsplit(".", 1)[-1] if "." in path else "text")
        else:
            st.info("No source files are available yet. Re-run with a smaller, specific MVP requirement to generate a product.")
        if result.get("outputs", {}).get("github_pr"):
            pr_info = result["outputs"]["github_pr"]
            st.success(f"GitHub Integrator published the product bundle as PR #{pr_info['number']}.")
            st.link_button("Open product Pull Request", pr_info["url"])
        elif result.get("outputs", {}).get("github_publish_error"):
            st.error("GitHub Integrator could not publish the product: " + result["outputs"]["github_publish_error"])
        if result.get("outputs", {}).get("leads_workbook_bytes"):
            wb = result["outputs"]["leads_workbook_bytes"]
            wb_name = result["outputs"].get("leads_workbook_path", "sales-leads.xlsx").split("/")[-1]
            st.download_button("Download sourced leads Excel (.xlsx)", data=wb, file_name=wb_name,
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            if result.get("outputs", {}).get("leads_github_pr"):
                lead_pr = result["outputs"]["leads_github_pr"]
                st.success(f"Lead workbook submitted to GitHub as PR #{lead_pr['number']}.")
                st.link_button("Review leads workbook PR", lead_pr["url"])
            elif result.get("outputs", {}).get("leads_github_error"):
                st.warning("Excel was created for download, but GitHub upload failed: " + result["outputs"]["leads_github_error"] +
                           " Check GITHUB_TOKEN repository Contents and Pull requests write permissions.")
        elif result.get("outputs", {}).get("leads_export_error"):
            st.error("Could not create leads workbook: " + result["outputs"]["leads_export_error"])
        st.warning("Generated product files are published as a reviewable GitHub PR after QA/security gates. This app does not merge PRs or deploy products automatically.")
        release_ready = bool(result.get("outputs", {}).get("release_gate", {}).get("passed"))
        if not release_ready:
            st.error("Release blocked: QA, security, and deterministic checks must all pass before a product PR can be created.")
            for reason in result.get("outputs", {}).get("release_gate", {}).get("reasons", []):
                st.write("• " + reason)
        if st.button("Retry GitHub publication", type="primary", key=f"pr_{result['run_id']}", disabled=not PASSWORD_CONFIGURED or not generated_files or not release_ready or bool(result.get("outputs", {}).get("github_pr"))):
            try:
                gh = GitHubService()
                bundle = gh.generate_file_bundle(result)
                pr = gh.create_change_request(result["project"], result["task"], bundle, base_branch=result.get("base_branch") or "main")
                store.add_event(result["run_id"], "GitHub Integrator", result["task"], "pull_request_created", "waiting_approval", summary=f"PR #{pr['number']}: {pr['url']}")
                st.success(f"Pull Request created: {pr['url']}")
                st.link_button("Open PR in GitHub", pr["url"])
            except (GitHubError, Exception) as exc:
                st.error(f"Could not create PR: {exc}")

elif page == "GitHub Pull Requests":
    st.subheader(" Human review queue")
    st.write("Review and approve directly in GitHub. The app intentionally cannot merge or deploy.")
    token = os.getenv("GITHUB_TOKEN", "")
    try:
        token = token or str(st.secrets.get("GITHUB_TOKEN", ""))
    except Exception:
        pass
    if not token:
        st.warning("Add GITHUB_TOKEN to Streamlit Secrets to load open PRs.")
    if st.button("Load open PRs", disabled=not bool(token)):
        try:
            owner, repo = os.getenv("GITHUB_OWNER", "pallasivasai"), os.getenv("GITHUB_REPO", "SIVA_IT-Solutions")
            try:
                owner = str(st.secrets.get("GITHUB_OWNER", owner)); repo = str(st.secrets.get("GITHUB_REPO", repo))
            except Exception:
                pass
            prs = GitHubService().list_open_prs(owner, repo)
            if not prs:
                st.info("No open pull requests.")
            for pr in prs:
                st.markdown(f"**[#{pr['number']} · {pr['title']}]({pr['url']})**")
                st.caption(f"{pr['state']} · {pr['head']} → {pr['base']} · {pr['created_at']}")
                st.divider()
        except GitHubError as exc:
            st.error(str(exc))

else:
    st.subheader(" Setup and guardrails")
    st.markdown("### Streamlit Secrets")
    st.code('APP_PASSWORD = "your-strong-password"\nOPENAI_API_KEY = "your-key"\nOPENAI_MODEL = "gpt-4.1-mini"\nGEMINI_API_KEY = "your-key"\nGEMINI_MODEL = "gemini-2.5-flash"\nGITHUB_TOKEN = "fine-grained-token"\nGITHUB_OWNER = "pallasivasai"\nGITHUB_REPO = "SIVA_IT-Solutions"', language="toml")
    st.write(" AI can create feature branches and PRs.\n\n CI runs unit tests.\n\n No automatic PR merge.\n\n No production deploy or generated-code execution.")
    st.warning("Configure branch protection on main and require PR review / passing checks where supported. Never commit keys.")
    st.markdown("Deploy using [Streamlit Community Cloud](https://share.streamlit.io/) with this repository and `app.py`; configure Settings → Secrets.")
    st.markdown("### Honest limitations")
    st.write("Interactive app tasks run when you submit them. The separate GitHub Actions worker performs unattended market-to-product runs daily when Actions is enabled and provider secrets are configured. Cards show recorded events. Streamlit local SQLite history may reset after restarts. Add durable storage and stronger authentication before confidential company use.")