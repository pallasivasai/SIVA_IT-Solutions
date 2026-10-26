from __future__ import annotations

import os
import re
from datetime import datetime, timezone

from agents import build_team, run_agent_step
from ai_providers import ProviderRouter
from code_builder import build_project_files
from github_service import GitHubService
from market_research import build_research_context
from project_checks import inspect_generated_files
from pipeline_gates import evaluate_market_gate, evaluate_release_gate
from storage import EventStore


def main() -> None:
    niche = os.getenv("AUTOPILOT_MARKET_NICHE", "small business operations, local services and digital workflows in India")
    goal = (
        "Discover one specific, evidence-backed unmet customer need in this market, select a small useful software product "
        "that fills the gap, generate its runnable MVP source files, perform QA/security reviews, and prepare a sales plan. "
        "Avoid generic clones. Include source URLs; separate evidence from hypotheses. Do not spend money, contact prospects, "
        "publish listings, merge code or deploy."
    )
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    store = EventStore(os.getenv("SIVA_EVENT_DB", "data/autopilot-events.db"))
    router = ProviderRouter()
    team = build_team()
    outputs: dict[str, str] = {}
    outputs["market_evidence"] = build_research_context(niche + " customer complaints alternatives underserved users")
    market_gate = evaluate_market_gate(outputs["market_evidence"])
    outputs["market_gate"] = market_gate
    store.add_event(run_id, "Research Gate", goal, "market_gate_checked",
                    "completed" if market_gate["passed"] else "failed",
                    summary=f"{market_gate['source_count']} distinct source URLs; passed={market_gate['passed']}")
    if not market_gate["passed"]:
        raise RuntimeError(market_gate["reason"])
    dispatch = run_agent_step(router, store, run_id, team[0], "Autonomous market discovery", goal + "\nMarket: " + niche, outputs)
    outputs["dispatch_plan"] = dispatch["output"]
    assignment = run_agent_step(router, store, run_id, team[1], "Autonomous market discovery", goal + "\nMarket: " + niche, outputs)
    outputs["assignment"] = assignment["output"]
    scout = run_agent_step(router, store, run_id, team[2], "Autonomous market discovery", goal + "\nMarket: " + niche, outputs)
    outputs["research"] = scout["output"]
    strategy = run_agent_step(router, store, run_id, team[3], "Autonomous market discovery", goal + "\nMarket: " + niche, outputs)
    outputs["product_strategy"] = strategy["output"]

    match = re.search(r"(?im)^\s*(?:product name|working name|name)\s*:\s*(.{3,70})$", outputs["product_strategy"])
    project = (match.group(1).strip(" *#") if match else "Opportunity " + datetime.now(timezone.utc).strftime("%Y%m%d"))
    project = re.sub(r"[^A-Za-z0-9 &_-]", "", project)[:60].strip() or "Opportunity " + run_id
    outputs["implementation"] = run_agent_step(router, store, run_id, team[4], project, goal + "\nMarket: " + niche, outputs)["output"]

    brief = goal + "\nMARKET: " + niche + "\nPRODUCT STRATEGY:\n" + outputs["product_strategy"] + "\nMARKET EVIDENCE:\n" + outputs["market_evidence"]
    files = build_project_files(router, project, brief, outputs["product_strategy"], outputs["implementation"])
    outputs["generated_files_summary"] = "\n".join(files)
    outputs["generated_files_context"] = "\n\n".join("### " + path + "\n" + body[:4000] for path, body in list(files.items())[:8])[:20000]
    checks = inspect_generated_files(files)
    outputs["static_qa"] = "\n".join("- " + item["status"] + ": " + item["detail"] for item in checks["checks"])
    outputs["qa"] = run_agent_step(router, store, run_id, team[5], project, brief, outputs)["output"]
    outputs["security"] = run_agent_step(router, store, run_id, team[6], project, brief, outputs)["output"]
    release_gate = evaluate_release_gate(files, checks, outputs["qa"], outputs["security"])
    outputs["release_gate"] = release_gate
    store.add_event(run_id, "Final Release Auditor", brief, "release_gate_checked",
                    "completed" if release_gate["passed"] else "blocked",
                    summary="; ".join(release_gate["reasons"]) if release_gate["reasons"] else "QA, security and deterministic checks passed")
    if not release_gate["passed"]:
        raise RuntimeError("Product release blocked; no Seller hand-off or GitHub PR created. " + "; ".join(release_gate["reasons"]))
    outputs["sales"] = run_agent_step(router, store, run_id, team[7], project, brief, outputs)["output"]

    result = {"run_id": run_id, "project": project, "task": brief, "outputs": outputs, "files": files}
    pr = GitHubService().create_change_request(project, brief, GitHubService().generate_file_bundle(result), base_branch="main")
    print(f"Created product PR #{pr['number']}: {pr['url']}")
    print(f"Project folder: products/{GitHubService._slug(project)}/")
    print(f"Static checks: {checks.get('failures', 0)} failures, {checks.get('warnings', 0)} warnings")
    if not checks.get("passed", False):
        print("WARNING: static checks found failures. The PR remains for human review; no code was executed.")


if __name__ == "__main__":
    main()
