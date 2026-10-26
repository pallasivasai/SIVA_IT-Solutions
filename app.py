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
    page = st.radio("Workspace", ["AI Project Room", "Task Board", "Office Floor", "GitHub Pull Requests", "Settings & Setup"])
    st.divider()
    st.markdown("**Agent hand-offs**")
    st.write("🔎 Scout research → 💡 Nova Project Manager plan")
    st.write("💻 Dev → 🧪 QA → 🛡️ Security")
    st.write("🛡️ Security → 🔀 GitHub Release Agent")
    st.write("🧭 Leads → 📈 Seller follow-up")
    st.caption("No API keys belong in source code.")

st.markdown("""
<div class="hero">
 <div class="kicker">SIVA IT SOLUTIONS · AGENT OPERATIONS</div>
 <h1>AI Company Office</h1>
 <p>Follow task ownership, workflow hand-offs, provider usage, QA/security reports and review-ready GitHub changes.</p>
</div>""", unsafe_allow_html=True)

elif page == "Office Floor":
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
        emoji = html.escape(str(agent.get("emoji", "🤖")))
        stations.append('<div class="agent-station"><div class="agent-sprite">' + emoji + '</div><div class="agent-desk"></div><div class="agent-name">' + name + '</div><div class="agent-role">' + role + '</div><div class="agent-status ' + css_status + '">' + status + '</div><div style="margin-top:5px;text-align:center;color:#3c5b5b;font-size:.65rem">' + task + '</div><div style="margin-top:5px;text-align:center;color:#243f45;font-size:.62rem;line-height:1.35">' + summary + '</div></div>')
    office_html = '<div class="office-shell"><div class="office-top"><span>▦ SIVA IT SOLUTIONS · FLOOR 01</span><span>8 SPECIALIST WORKSTATIONS · AUTO-REFRESH 5s</span></div><div class="office-floor">' + "".join(stations) + '</div><div class="office-bottom"><span>● VIEW OF RECORDED EVENTS</span><span>Human approval required · No auto-merge/deploy</span></div></div>'
    st.markdown(office_html, unsafe_allow_html=True)
    st.divider()
    st.subheader("🧭 Workflow lane")
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
    st.subheader("🧩 Give the company a product goal")
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
            try:
                # Record Scout as the current owner before external research starts so the
                # Virtual Office shows the real active task even if web search fails.
                store.add_event(run_id, "Scout", task, "agent_started", "running",
                                summary="Scout is collecting public market evidence and competitor sources")
                progress.write("🔎 Scout · Market Researcher — collecting public evidence and competitor sources…")
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
                    st.info("Open **Office Floor** to see Scout marked ERROR and the exact task it attempted. Product planning will not run until real sources are available.")
                else:
                    progress.write(f"Research gate passed with {market_gate['source_count']} distinct source URLs")
                if market_gate["passed"]:
                    scout = run_agent_step(router, store, run_id, team[0], current_project, task, outputs)
                    outputs["research"] = scout["output"]
                    progress.write("Scout completed gap research")
                    progress.write("💡 Nova · Project Manager — reviewing Scout's evidence and creating the product plan/task breakdown…")
                    strategy = run_agent_step(
                        router, store, run_id, team[1], current_project,
                        task,
                        outputs,
                    )
                    outputs["product_strategy"] = strategy["output"]
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
                    progress.write("💻 Dev · Software Engineer — accepting Nova's plan and preparing implementation…")
                    implementation = run_agent_step(router, store, run_id, team[2], current_project, dev_handoff, outputs)
                    outputs["implementation"] = implementation["output"]
                    store.add_event(run_id, "Dev", dev_handoff, "implementation_ready", "completed",
                                    summary="Implementation hand-off prepared for source generation")
                    progress.write("Dev implementation hand-off ready; generating actual source files next")
                    generated_files: dict[str, str] = {}
                    try:
                        progress.write("💻 Dev · Code Builder — generating the actual MVP source files from Nova's plan…")
                        store.add_event(run_id, "Dev", task, "code_generation_started", "running",
                                        summary="Generating actual product source files from the project plan")
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
                        progress.write(f"Generated {len(generated_files)} real source files")
                    except Exception as exc:
                        outputs["code_build_error"] = f"{type(exc).__name__}: {exc}"
                        store.add_event(run_id, "Dev", task, "code_generation_failed", "failed",
                                        summary=outputs["code_build_error"])
                        progress.error("Dev could not generate the product source files: " + outputs["code_build_error"])
                    if generated_files:
                        qa = run_agent_step(router, store, run_id, team[3], current_project,
                                            "QA HAND-OFF: inspect the actual generated source files and Nova's acceptance criteria. "
                                            "Run/assess the provided tests where possible, list concrete defects, and do not claim execution without evidence.\n\n" + task,
                                            outputs)
                        outputs["qa"] = qa["output"]
                        progress.write("Tara completed the QA report on generated files")
                        security = run_agent_step(router, store, run_id, team[4], current_project,
                                                  "SECURITY HAND-OFF: inspect the actual generated source files, dependencies and QA findings. "
                                                  "Report concrete vulnerabilities and remediation. Do not claim scans were executed unless they were.\n\n" + task,
                                                  outputs)
                        outputs["security"] = security["output"]
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
                            outputs["qa"] = run_agent_step(router, store, run_id, team[3], current_project,
                                                           "RE-REVIEW revised source. Verify previous findings are fixed and identify remaining defects. " + task,
                                                           outputs)["output"]
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
                            progress.warning("GitHub publication failed; product files remain available below. Check GitHub token and repository settings.")
                        progress.write("Lead Research is finding sourced, relevant prospects…")
                        outputs["lead_evidence"] = build_research_context(
                            "businesses and companies likely to buy " + current_project + " in India and relevant target markets public company websites contact page"
                        )
                        leads = run_agent_step(router, store, run_id, team[6], current_project, task, outputs)
                        outputs["leads"] = leads["output"]
                        progress.write("Lead Research handed sourced prospect findings to Seller.")
                        sales = run_agent_step(router, store, run_id, team[7], current_project, task, outputs)
                        outputs["sales"] = sales["output"]
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
                st.info("Office Floor will show completed agents as DONE, the failing agent as ERROR, and downstream agents as WAITING.")
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
    result = st.session_state.last_run
    if result:
        st.markdown(f"### Latest run · {result['project']}")
        st.caption(f"Run ID: {result['run_id']}")
        if result.get("outputs", {}).get("workflow_error"):
            st.error("Workflow error: " + str(result["outputs"]["workflow_error"]))
        if result.get("outputs", {}).get("market_gate"):
            with st.expander("🔎 Research gate evidence", expanded=False):
                st.json(result["outputs"]["market_gate"])
        if result.get("outputs", {}).get("release_gate"):
            with st.expander("🚦 Final release gate", expanded=True):
                st.json(result["outputs"]["release_gate"])
        for label, key in [("🔎 Industry gap research","research"),("💡 Product plan","product_strategy"),("💻 Developer hand-off","implementation"),("🧪 QA report","qa"),("🛡️ Security review","security"),("🔀 GitHub release agent","github_release"),("🧭 Sourced sales leads","leads"),("📈 Seller outreach + follow-up plan","sales")]:
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
