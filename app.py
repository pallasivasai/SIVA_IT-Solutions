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
    st.subheader("🏢 Office floor")
    st.caption("Employee-style role cards show the latest task event. Idle means no active run is currently recorded.")
    latest: dict[str, dict[str, Any]] = {}
    for ev in events:
        name = ev.get("agent_name", "")
        if name and name not in latest:
            latest[name] = ev
    cols = st.columns(2)
    labels = {"running":"🟢 Working", "completed":"✅ Completed", "failed":"🔴 Needs attention", "waiting_approval":"🟠 Waiting approval", "idle":"⚪ Available"}
    for i, agent in enumerate(team):
        ev = latest.get(agent["name"], {})
        status = labels.get(ev.get("status", "idle"), "⚪ Available")
        task = ev.get("task", "Waiting for assignment")
        stamp = ev.get("created_at", "No activity recorded yet")
        with cols[i % 2]:
            st.markdown(f"""<div class="person"><div style="font-size:1.8rem">{agent['emoji']}</div><div class="name">{agent['name']}</div><div class="role">{agent['role']}</div><div class="pill">{status}</div><p style="margin:.7rem 0 .3rem;color:#dbe7f6"><b>Task</b>: {task[:180]}</p><div class="smallmuted">Latest activity: {stamp}</div></div>""", unsafe_allow_html=True)
    st.divider()
    st.subheader("Workflow lane")
    stages = [
        ("1 · Product Manager", "Clarifies scope, assumptions, success criteria and plan."),
        ("2 · Software Engineer", "Prepares implementation proposal and instructions."),
        ("3 · QA Engineer", "Defines test cases, expected outcomes and untested areas."),
        ("4 · Security Reviewer", "Checks risk, secrets, authentication and release controls."),
        ("5 · GitHub Pull Request", "Creates a proposal on a feature branch for review."),
        ("6 · Human owner", "Inspects and approves directly on GitHub; no automatic merge or deployment.")]
    for title, desc in stages:
        st.markdown(f'<div class="taskline"><b>{title}</b><br><span class="smallmuted">{desc}</span></div>', unsafe_allow_html=True)
    st.info("The dashboard shows operational task summaries and status—not private hidden reasoning. It does not pretend agents are working in the background when no task is running.")
    if st.button("Refresh activity"):
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
