from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import streamlit as st

from agents import build_team, run_agent_step
from ai_providers import ProviderError, ProviderRouter
from github_service import GitHubError, GitHubService
from storage import EventStore

st.set_page_config(page_title="SIVA IT Solutions · AI Office", page_icon="🏢", layout="wide")

# This repo is public. Require an owner-configured password before exposing API-backed actions.
import hmac
APP_PASSWORD = os.getenv("APP_PASSWORD", "")
try:
    APP_PASSWORD = APP_PASSWORD or str(st.secrets.get("APP_PASSWORD", ""))
except Exception:
    pass

if not APP_PASSWORD or APP_PASSWORD == "change-this-to-a-long-random-password":
    st.error("Access is locked: configure a strong APP_PASSWORD in Streamlit Secrets before using this public dashboard.")
    st.stop()
if not st.session_state.get("authenticated", False):
    st.title("🔐 SIVA IT Solutions · Secure Office Login")
    entered = st.text_input("Office access password", type="password")
    if st.button("Unlock dashboard", type="primary"):
        if hmac.compare_digest(entered, APP_PASSWORD):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()
st.markdown("""
<style>
.stApp { background: radial-gradient(circle at 14% 0%, #17314b 0%, #0b1422 44%, #070c14 100%); }
.block-container { padding-top: 1.5rem; max-width: 1500px; }
.hero { padding: 1.4rem 1.6rem; border: 1px solid #29425b; border-radius: 20px; background: linear-gradient(120deg,rgba(29,57,79,.94),rgba(13,24,40,.94)); margin-bottom: 1rem; }
.kicker { color:#64e2b7; font-weight:700; letter-spacing:.16em; font-size:.72rem; }
.hero h1 { margin:.25rem 0; font-size:2.25rem; color:#f2f7ff; }
.hero p { color:#a9bbd0; margin:0; }
.person { border:1px solid #293d54; background:rgba(16,27,43,.94); border-radius:16px; padding:14px; min-height:174px; margin-bottom:10px; }
.person .name { font-size:1.05rem; font-weight:750; color:#eaf2ff; }
.person .role { font-size:.78rem; color:#8fa2bd; margin:.15rem 0 .6rem; }
.pill { display:inline-block; border:1px solid #315a55; background:#142e32; padding:3px 8px; border-radius:100px; color:#75e0bb; font-size:.72rem; }
.smallmuted { color:#8fa2bd; font-size:.84rem; }
.taskline { border-left:3px solid #64e2b7; background:rgba(17,31,48,.9); border-radius:0 10px 10px 0; padding:10px 14px; margin:.45rem 0; }
div[data-testid="stMetric"] { background:rgba(16,27,43,.85); border:1px solid #26364d; padding:12px 14px; border-radius:14px; }
.office-shell { background:#182b35; border:10px solid #31434a; border-radius:18px; padding:18px; box-shadow:inset 0 0 0 2px #0c1820, 0 12px 30px #0005; }
.office-top { display:flex; justify-content:space-between; align-items:center; padding:8px 12px 16px; color:#d5e8e1; border-bottom:2px solid #3a5358; margin-bottom:16px; }
.office-top strong { letter-spacing:.12em; font-size:.8rem; }
.office-top span { font-size:.75rem; color:#9db9b3; }
.office-room { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:18px; }
.workstation { position:relative; min-height:220px; padding:14px; border-radius:12px; background:linear-gradient(135deg,#28434a,#20363d); border:1px solid #426066; overflow:hidden; }
.station-head { display:flex; justify-content:space-between; align-items:center; gap:8px; }
.station-name { color:#f0faf5; font-weight:800; font-size:1rem; }
.station-role { color:#9db9b3; font-size:.73rem; margin-top:2px; }
.state-dot { width:9px; height:9px; display:inline-block; border-radius:50%; margin-right:5px; background:#83969a; }
.state-dot.running { background:#5ee2a0; box-shadow:0 0 12px #5ee2a0; }
.state-dot.completed { background:#68b9ff; }
.state-dot.failed { background:#ff7373; }
.desk { display:grid; grid-template-columns:66px 1fr; gap:12px; align-items:center; margin:16px 0 10px; }
.worker { width:60px; height:72px; display:flex; align-items:center; justify-content:center; font-size:2.3rem; background:#15272d; border:1px solid #48636a; border-radius:12px; box-shadow:0 6px 0 #101c20; }
.monitor { background:#0b151b; border:4px solid #607b7d; border-radius:8px; padding:9px; min-height:58px; box-shadow:0 5px 0 #17252a; }
.screen-line { height:4px; margin:4px 0; border-radius:4px; background:#4cae91; opacity:.8; }
.screen-line:nth-child(2) { width:72%; background:#70a9ee; }
.screen-line:nth-child(3) { width:48%; background:#d6b56f; }
.task-slip { padding:9px 10px; background:#102128; border-left:3px solid #62d9b1; border-radius:5px; color:#dcece8; font-size:.79rem; line-height:1.4; min-height:48px; overflow-wrap:anywhere; }
.task-slip.failed { border-left-color:#ff7373; }
.task-slip.completed { border-left-color:#68b9ff; }
.task-meta { display:flex; justify-content:space-between; gap:8px; color:#91aaa8; font-size:.68rem; margin-top:8px; }
.office-corridor { text-align:center; color:#8eaaa5; font-size:.72rem; letter-spacing:.22em; padding:15px 0 4px; }
.office-legend { display:flex; flex-wrap:wrap; gap:14px; color:#9db9b3; font-size:.75rem; padding:12px 2px 0; }
@media (max-width:700px) { .office-room { grid-template-columns:1fr; } }
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
    st.markdown("## 🏢 SIVA IT Solutions")
    st.caption("AI Company Control Center")
    page = st.radio("Workspace", ["Office Floor", "Task Board", "AI Project Room", "GitHub Pull Requests", "Settings & Setup"])
    st.divider()
    st.markdown("**System map**")
    st.write("🧠 OpenAI → Gemini fallback")
    st.write("🧭 Plan → 💻 Build proposal")
    st.write("🧪 QA → 🛡️ Security")
    st.write("🔀 Human-reviewed GitHub PR")
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
    st.subheader("🏢 The office")
    st.caption("Code-rendered floor plan. Each workstation is tied to a real workflow event; agents are marked available when no task is active.")
    latest: dict[str, dict[str, Any]] = {}
    for ev in events:
        name = ev.get("agent_name", "")
        if name and name not in latest:
            latest[name] = ev
    labels = {"running":"Working", "completed":"Task finished", "failed":"Needs attention", "waiting_approval":"Waiting for review", "idle":"Available"}
    state_classes = {"running":"running", "completed":"completed", "failed":"failed", "waiting_approval":"running", "idle":"idle"}
    role_to_icon = {"Mira":"🧑🏻‍💼", "Dev":"👩🏽‍💻", "Tara":"🧑🏼‍🔬", "Shield":"🧑🏽‍🔒"}
    cards = []
    for agent in team:
        ev = latest.get(agent["name"], {})
        status_key = ev.get("status", "idle")
        status = labels.get(status_key, "Available")
        css_status = state_classes.get(status_key, "idle")
        task = str(ev.get("task", "No task assigned yet"))
        summary = str(ev.get("summary", "Waiting for the next assignment"))
        stamp = str(ev.get("created_at", "No activity yet"))
        def safe(value: str) -> str:
            return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
        cards.append(f'''
        <div class="workstation">
          <div class="station-head">
            <div><div class="station-name"><span class="state-dot {css_status}"></span>{safe(agent["name"])}</div>
            <div class="station-role">{safe(agent["role"])}</div></div>
            <span class="pill">{safe(status)}</span>
          </div>
          <div class="desk">
            <div class="worker">{role_to_icon.get(agent["name"], "🧑‍💻")}</div>
            <div class="monitor" aria-label="computer monitor">
              <div class="screen-line"></div><div class="screen-line"></div><div class="screen-line"></div>
            </div>
          </div>
          <div class="task-slip {css_status}"><b>TASK AT THIS DESK</b><br>{safe(task[:230])}<br><span style="color:#8fa9a7">{safe(summary[:150])}</span></div>
          <div class="task-meta"><span>{safe(status)}</span><span>{safe(stamp[:25])}</span></div>
        </div>''')
    st.markdown('<div class="office-shell"><div class="office-top"><strong>FLOOR 01 · ENGINEERING & QUALITY</strong><span>WORKSTATIONS · TASK-DRIVEN</span></div><div class="office-room">' + "".join(cards) + '</div><div class="office-corridor">— MAIN WALKWAY · TEAM HAND-OFF ZONE —</div><div class="office-legend"><span>🟢 Working</span><span>🔵 Completed</span><span>🔴 Needs attention</span><span>⚪ Available / no active task</span></div></div>', unsafe_allow_html=True)
    st.divider()
    st.subheader("Task hand-off pipeline")
    stages = [
        ("01 · Mira / Product", "Reads the requirement and creates scope, assumptions and acceptance criteria."),
        ("02 · Dev / Engineering", "Uses the plan and writes an implementation proposal."),
        ("03 · Tara / QA", "Creates test cases and checks the proposal for missing acceptance criteria."),
        ("04 · Shield / Security", "Reviews security risks, secrets handling and release controls."),
        ("05 · GitHub Integrator", "Creates a reviewable pull request when explicitly requested in the project room.")
    ]
    for title, desc in stages:
        st.markdown(f'<div class="taskline"><b>{title}</b><br><span class="smallmuted">{desc}</span></div>', unsafe_allow_html=True)
    st.info("This floor plan is rendered from HTML/CSS in app.py—no generated images. Status reflects recorded task events; idle seats are not shown as actively working.")
    if st.button("Refresh office floor"):
        st.rerun()

elif page == "Task Board":
    st.subheader("📋 Task board / activity log")
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
    st.subheader("🧩 Assign a task to the AI team")
    st.write("Mira plans, Dev writes an implementation proposal, Tara defines QA and Shield reviews security. Outputs are visible at each hand-off.")
    with st.form("task_form"):
        project = st.text_input("Project name", value=st.session_state.selected_project)
        task = st.text_area("Requirement", height=170, placeholder="Describe the feature, constraints, acceptance criteria and what must not change.")
        base_branch = st.text_input("Target base branch for PR (optional)", "main")
        submitted = st.form_submit_button("Start workflow", type="primary")
    if submitted:
        if not task.strip():
            st.error("Enter a task description first.")
        else:
            run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            current_project = project.strip() or "Unnamed project"
            st.session_state.selected_project = current_project
            outputs: dict[str, Any] = {}
            progress = st.status("Starting task workflow…", expanded=True)
            try:
                plan = run_agent_step(router, store, run_id, team[0], current_project, task, outputs)
                outputs["plan"] = plan["output"]
                progress.write(f"✅ Mira completed the plan · {plan['provider']}")
                implementation = run_agent_step(router, store, run_id, team[1], current_project, task, outputs)
                outputs["implementation"] = implementation["output"]
                progress.write(f"✅ Dev prepared an implementation proposal · {implementation['provider']}")
                qa = run_agent_step(router, store, run_id, team[2], current_project, task, outputs)
                outputs["qa"] = qa["output"]
                progress.write(f"✅ Tara completed the QA report · {qa['provider']}")
                security = run_agent_step(router, store, run_id, team[3], current_project, task, outputs)
                outputs["security"] = security["output"]
                progress.write(f"✅ Shield completed the security review · {security['provider']}")
                st.session_state.last_run = {"run_id":run_id,"project":current_project,"task":task,"outputs":outputs,"base_branch":base_branch}
                progress.update(label="Workflow completed", state="complete", expanded=False)
            except ProviderError as exc:
                store.add_event(run_id, "System", task, "workflow_failed", "failed", summary=str(exc))
                progress.update(label="Workflow stopped", state="error", expanded=True)
                st.error(str(exc))
            except Exception as exc:
                store.add_event(run_id, "System", task, "workflow_failed", "failed", summary=f"{type(exc).__name__}: {exc}")
                progress.update(label="Workflow stopped", state="error", expanded=True)
                st.exception(exc)
    result = st.session_state.last_run
    if result:
        st.markdown(f"### Latest run · {result['project']}")
        st.caption(f"Run ID: {result['run_id']}")
        for label, key in [("🧭 Product plan","plan"),("💻 Implementation proposal","implementation"),("🧪 QA report","qa"),("🛡️ Security review","security")]:
            with st.expander(label, expanded=(key == "plan")):
                st.markdown(result["outputs"].get(key, "No report available."))
        st.warning("GitHub integration creates a review document from these outputs, not arbitrary executable code. Inspect before approval.")
        if st.button("Create feature branch + GitHub Pull Request", type="primary", key=f"pr_{result['run_id']}"):
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
    st.subheader("🔀 Human review queue")
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
    st.subheader("⚙️ Setup and guardrails")
    st.markdown("### Streamlit Secrets")
    st.code('OPENAI_API_KEY = "your-key"\nOPENAI_MODEL = "gpt-4.1-mini"\nGEMINI_API_KEY = "your-key"\nGEMINI_MODEL = "gemini-2.5-flash"\nGITHUB_TOKEN = "fine-grained-token"\nGITHUB_OWNER = "pallasivasai"\nGITHUB_REPO = "SIVA_IT-Solutions"', language="toml")
    st.write("✅ AI can create feature branches and PRs.\n\n✅ CI runs unit tests.\n\n⛔ No automatic PR merge.\n\n⛔ No production deploy or generated-code execution.")
    st.warning("Configure branch protection on main and require PR review / passing checks where supported. Never commit keys.")
    st.markdown("Deploy using [Streamlit Community Cloud](https://share.streamlit.io/) with this repository and `app.py`; configure Settings → Secrets.")
    st.markdown("### Honest limitations")
    st.write("This is task-triggered, not an always-on workforce. Cards show recorded events. Streamlit local SQLite history may reset after restarts. Add authentication and persistent storage before handling confidential company tasks.")
