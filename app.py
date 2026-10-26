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
from market_research import build_research_context
from storage import EventStore

st.set_page_config(page_title="SIVA IT Solutions · AI Office", page_icon="🏢", layout="wide")

# This repo is public. Require an owner-configured password before exposing API-backed actions.
import hmac
APP_PASSWORD = os.getenv("APP_PASSWORD", "")
try:
    APP_PASSWORD = APP_PASSWORD or str(st.secrets.get("APP_PASSWORD", ""))
except Exception:
    pass

PASSWORD_CONFIGURED = bool(APP_PASSWORD and APP_PASSWORD != "change-this-to-a-long-random-password")
if PASSWORD_CONFIGURED and not st.session_state.get("authenticated", False):
    st.title("🔐 SIVA IT Solutions · Secure Office Login")
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
.smallmuted{color:#a5b5c9;font-size:.78rem}.taskline{border-left:3px solid #64e2b7;background:rgba(17,31,48,.9);border-radius:0 10px 10px 0;padding:10px 14px;margin:.45rem 0}div[data-testid="stMetric"]{background:rgba(16,27,43,.85);border:1px solid #26364d;padding:12px 14px;border-radius:14px}
.office-shell{border:3px solid #b8c5c7;border-radius:8px;overflow:hidden;background:#c5d9d3;box-shadow:0 14px 35px #0006}.office-top{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;color:#eaf3f8;background:#182838;font-size:.76rem;letter-spacing:.08em;font-weight:800}
.office-floor{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;padding:20px;background-color:#b8d0c9;background-image:linear-gradient(#90afa6 1px,transparent 1px),linear-gradient(90deg,#90afa6 1px,transparent 1px);background-size:46px 46px}
.agent-station{min-height:155px;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;padding:10px 7px 9px;border:2px solid #77968e;border-radius:5px;background:rgba(222,235,225,.72);box-shadow:inset 0 0 0 3px #d9e6dd}
.agent-sprite{width:45px;height:45px;display:flex;align-items:center;justify-content:center;border:3px solid #233748;border-radius:5px;background:#f0d6ae;font-size:25px;box-shadow:4px 4px 0 #526c69}
.agent-desk{margin-top:8px;width:82%;height:28px;border:3px solid #795c42;border-radius:3px;background:repeating-linear-gradient(90deg,#d8b486 0 12px,#c89e6e 12px 14px);position:relative}.agent-desk:before{content:'▣';position:absolute;left:calc(50% - 11px);top:-20px;width:22px;height:16px;display:grid;place-items:center;color:#7ae9ff;background:#1a2835;border:2px solid #d4dfe0;font-size:10px}
.agent-name{margin-top:9px;font-weight:900;font-size:.78rem;color:#142c34}.agent-role{font-size:.61rem;text-align:center;color:#3c5b5b;min-height:27px}.agent-status{margin-top:5px;padding:4px 7px;border:1px solid #78948c;border-radius:4px;background:#f1f6ec;color:#29463f;font-size:.62rem;font-weight:800;text-align:center}.agent-status.running{background:#c6f6d9;color:#125b3c;border-color:#389b6a}.agent-status.failed{background:#ffe0de;color:#9b2525;border-color:#c85b55}.agent-status.waiting{background:#fff0bf;color:#795514;border-color:#c9a24a}
.office-bottom{padding:10px 14px;background:#182838;color:#9db1c4;font-size:.7rem;display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap}
@media(max-width:900px){.office-floor{grid-template-columns:repeat(2,minmax(0,1fr));padding:10px;gap:8px}.agent-station{min-height:140px}.hero h1{font-size:1.6rem}}@media(max-width:480px){.office-floor{grid-template-columns:repeat(2,minmax(0,1fr))}.agent-role{font-size:.55rem}}
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

if page == "Office Floor":
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=5000, key="office_live_refresh")

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
    st.subheader("🏢 Virtual AI Office")
    st.caption("Auto-refreshes every 5 seconds. Each agent owns a defined role; statuses are based on recorded events, not simulated activity. Agents stay IDLE when no workflow is running.")
    latest: dict[str, dict[str, Any]] = {}
    def canonical_agent_name(raw_name: str) -> str:
        raw = raw_name.strip()
        aliases = {"Dev · Code Builder": "Dev", "GitHub Integrator": "Atlas"}
        if raw in aliases:
            return aliases[raw]
        return raw.split(" · ", 1)[0].strip()
    for ev in events:
        name = canonical_agent_name(str(ev.get("agent_name", "")))
        if name and name not in latest:
            latest[name] = ev
    labels = {"running": ("WORKING", "running"), "completed": ("DONE", "done"), "failed": ("ERROR", "failed"), "waiting_approval": ("WAITING FOR REVIEW", "waiting"), "idle": ("IDLE", "idle"), "code_files_generated": ("DONE", "done"), "agent_started": ("WORKING", "running"), "agent_completed": ("DONE", "done"), "agent_failed": ("ERROR", "failed")}
    stations = []
    for agent in team:
        ev = latest.get(agent["name"], {})
        status, css_status = labels.get(ev.get("status", "idle"), ("IDLE", "idle"))
        task = html.escape(str(ev.get("task", "Waiting for assignment"))[:105])
        name = html.escape(str(agent["name"]))
        role = html.escape(str(agent["role"].split("·")[0].strip()))
        emoji = html.escape(str(agent.get("emoji", "🤖")))
        stations.append('<div class="agent-station"><div class="agent-sprite">' + emoji + '</div><div class="agent-desk"></div><div class="agent-name">' + name + '</div><div class="agent-role">' + role + '</div><div class="agent-status ' + css_status + '">' + status + '</div><div style="margin-top:5px;text-align:center;color:#3c5b5b;font-size:.65rem">' + task + '</div></div>')
    office_html = '<div class="office-shell"><div class="office-top"><span>▦ SIVA IT SOLUTIONS · FLOOR 01</span><span>8 AGENT WORKSTATIONS · AUTO-REFRESH 5s</span></div><div class="office-floor">' + "".join(stations) + '</div><div class="office-bottom"><span>● VIEW OF RECORDED EVENTS</span><span>Human approval required · No auto-merge/deploy</span></div></div>'
    st.markdown(office_html, unsafe_allow_html=True)
    st.divider()
    st.subheader("🧭 Workflow lane")
    stages = [("1 · Mira — Task assignment", "Breaks the goal into owned tasks and acceptance criteria."), ("2 · Scout — Market research", "Collects public evidence and identifies customer/industry gaps."), ("3 · Nova — Product strategy", "Turns the strongest opportunity into a scoped MVP."), ("4 · Dev — Source generation", "Creates reviewable product source files."), ("5 · Tara + Shield — QA and security", "Reviews quality, edge cases, secrets and release risks."), ("6 · Seller — Go-to-market", "Prepares positioning, pricing hypotheses and launch assets."), ("7 · GitHub Pull Request", "Packages product files for human review; no automatic merge or deployment.")]
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
    st.write("Atlas dispatches tasks → Mira coordinates dependencies → Scout researches industry gaps → Nova designs a product to fill a gap → Dev builds source files → Tara checks quality → Shield reviews security → Seller prepares a sales plan. The files are packaged into a reviewable GitHub PR; generated code is never executed by this dashboard.")
    with st.form("task_form"):
        project = st.text_input("Project name", value=st.session_state.selected_project)
        task = st.text_area("Requirement", height=170, placeholder="Describe the feature, constraints, acceptance criteria and what must not change.")
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
            progress = st.status("Starting task workflow…", expanded=True)
            try:
                dispatch = run_agent_step(router, store, run_id, team[0], current_project, task, outputs)
                outputs["dispatch_plan"] = dispatch["output"]
                progress.write("Atlas created the team dispatch plan")
                assignment = run_agent_step(router, store, run_id, team[1], current_project, task, outputs)
                outputs["assignment"] = assignment["output"]
                progress.write("Mira refined task ownership")
                progress.write("Scout is collecting public market evidence…")
                outputs["market_evidence"] = build_research_context(task)
                scout = run_agent_step(router, store, run_id, team[2], current_project, task, outputs)
                outputs["research"] = scout["output"]
                progress.write("Scout completed gap research")
                strategy = run_agent_step(router, store, run_id, team[3], current_project, task, outputs)
                outputs["product_strategy"] = strategy["output"]
                progress.write("Nova selected an MVP direction")
                implementation = run_agent_step(router, store, run_id, team[4], current_project, task, outputs)
                outputs["implementation"] = implementation["output"]
                progress.write("Dev prepared implementation notes")
                generated_files: dict[str, str] = {}
                try:
                    progress.write("Dev is generating actual product source files…")
                    build_brief = task + "\n\nPRODUCT STRATEGY / GAP TO FILL:\n" + outputs["product_strategy"] + "\n\nMARKET EVIDENCE:\n" + outputs["market_evidence"]
                    generated_files = build_project_files(router, current_project, build_brief, outputs["product_strategy"], outputs["implementation"])
                    outputs["generated_files_summary"] = "\n".join(f"- {path}" for path in generated_files)
                    outputs["generated_files_context"] = "\n\n".join(f"### {path}\n{body[:6000]}" for path, body in list(generated_files.items())[:8])[:24000]
                    static_check = inspect_generated_files(generated_files)
                    outputs["static_qa"] = "\n".join("- " + item["status"] + ": " + item["detail"] for item in static_check["checks"])
                    outputs["generated_files_context"] += "\n\n## Deterministic non-executing checks\n" + outputs["static_qa"]
                    store.add_event(run_id, "Dev · Code Builder", task, "code_files_generated", "completed", summary=f"Generated {len(generated_files)} reviewable source files")
                    progress.write(f"Generated {len(generated_files)} real source files")
                except CodeBuildError as exc:
                    outputs["code_build_error"] = str(exc)
                    store.add_event(run_id, "Dev · Code Builder", task, "code_generation_failed", "failed", summary=str(exc))
                    progress.write(f"Code generation needs retry: {exc}")
                qa = run_agent_step(router, store, run_id, team[5], current_project, task, outputs)
                outputs["qa"] = qa["output"]
                progress.write("Tara completed the QA report")
                security = run_agent_step(router, store, run_id, team[6], current_project, task, outputs)
                outputs["security"] = security["output"]
                progress.write("Shield completed the security review")
                sales = run_agent_step(router, store, run_id, team[7], current_project, task, outputs)
                outputs["sales"] = sales["output"]
                progress.write("Seller prepared go-to-market assets")
                st.session_state.last_run = {"run_id":run_id,"project":current_project,"task":task,"outputs":outputs,"files":generated_files,"base_branch":base_branch}
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
        for label, key in [("🧭 Atlas dispatch plan","dispatch_plan"),("🗂️ Task assignments","assignment"),("🔎 Industry gap research","research"),("💡 Product strategy","product_strategy"),("💻 Implementation proposal","implementation"),("🧪 QA report","qa"),("🛡️ Security review","security"),("📈 Sales and go-to-market plan","sales")]:
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
        st.warning("Generated files are reviewed as a GitHub PR. This app does not execute generated code, merge PRs, or deploy products automatically.")
        if st.button("Create feature branch + GitHub Pull Request", type="primary", key=f"pr_{result['run_id']}", disabled=not PASSWORD_CONFIGURED or not generated_files):
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
    st.code('APP_PASSWORD = "your-strong-password"\nOPENAI_API_KEY = "your-key"\nOPENAI_MODEL = "gpt-4.1-mini"\nGEMINI_API_KEY = "your-key"\nGEMINI_MODEL = "gemini-2.5-flash"\nGITHUB_TOKEN = "fine-grained-token"\nGITHUB_OWNER = "pallasivasai"\nGITHUB_REPO = "SIVA_IT-Solutions"', language="toml")
    st.write("✅ AI can create feature branches and PRs.\n\n✅ CI runs unit tests.\n\n⛔ No automatic PR merge.\n\n⛔ No production deploy or generated-code execution.")
    st.warning("Configure branch protection on main and require PR review / passing checks where supported. Never commit keys.")
    st.markdown("Deploy using [Streamlit Community Cloud](https://share.streamlit.io/) with this repository and `app.py`; configure Settings → Secrets.")
    st.markdown("### Honest limitations")
    st.write("Interactive app tasks run when you submit them. The separate GitHub Actions worker performs unattended market-to-product runs daily when Actions is enabled and provider secrets are configured. Cards show recorded events. Streamlit local SQLite history may reset after restarts. Add durable storage and stronger authentication before confidential company use.")
