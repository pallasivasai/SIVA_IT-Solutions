from agents import build_team
from ai_providers import ProviderRouter


def test_team_members_and_roles():
    team = build_team()
    assert len(team) == 8
    assert [m["name"] for m in team] == ["Scout", "Nova", "Dev", "Tara", "Shield", "GitHub Integrator", "Lead Research", "Seller"]
    assert all("Task Assignment" not in member["role"] for member in team)


def test_fallback_detector_recognizes_quota_and_transient_errors():
    assert ProviderRouter.fallback_worthy(RuntimeError("429 rate limit exceeded"))
    assert ProviderRouter.fallback_worthy(RuntimeError("insufficient_quota"))
    assert ProviderRouter.fallback_worthy(RuntimeError("service unavailable"))


def test_fallback_detector_does_not_mask_auth_error():
    assert not ProviderRouter.fallback_worthy(RuntimeError("invalid API key"))



def test_persistent_task_queue_claim_complete(tmp_path):
    from task_queue import PersistentTaskQueue

    queue = PersistentTaskQueue(str(tmp_path / "queue.db"))
    task_id = queue.enqueue({"project": "Example", "task": "Build a tiny MVP"})
    claimed = queue.claim("worker-a")
    assert claimed is not None
    assert claimed["id"] == task_id
    assert claimed["payload"]["project"] == "Example"
    assert queue.complete(task_id, "worker-a", {"pr": "https://example.invalid/pr/1"})
    assert queue.get(task_id)["status"] == "completed"


def test_persistent_task_queue_retries_then_fails(tmp_path):
    from task_queue import PersistentTaskQueue

    queue = PersistentTaskQueue(str(tmp_path / "queue.db"), max_attempts=2)
    task_id = queue.enqueue({"task": "retry me"})
    first = queue.claim("worker-a")
    assert first and first["id"] == task_id
    assert queue.fail(task_id, "worker-a", "temporary provider error", retry_delay_seconds=0) == "queued"
    second = queue.claim("worker-b")
    assert second and second["attempts"] == 2
    assert queue.fail(task_id, "worker-b", "still failing", retry_delay_seconds=0) == "failed"
    assert queue.get(task_id)["status"] == "failed"



def test_orchestration_registry_has_25_distinct_roles():
    from orchestration import AGENT_ROLES, WORKFLOW_STAGES

    assert len(AGENT_ROLES) == 25
    assert len({role["name"] for role in AGENT_ROLES}) == 25
    assert len({stage["id"] for stage in WORKFLOW_STAGES}) == len(WORKFLOW_STAGES)


def test_workflow_ledger_persists_messages_and_dependency_handoffs(tmp_path):
    from orchestration import WorkflowLedger

    ledger = WorkflowLedger(str(tmp_path / "workflow.db"))
    run_id = ledger.create_run("Example", "Build an example product", "run-test-1")
    board = ledger.task_board(run_id)
    assert next(item for item in board if item["stage_id"] == "market_gap")["status"] == "ready"
    assert next(item for item in board if item["stage_id"] == "competitors")["status"] == "blocked"

    ledger.send_message(run_id, "market_gap", "Market Gap Research", "Competitor Analysis",
                        {"evidence": ["https://example.com"], "gap": "sample unmet need"})
    inbox = ledger.inbox(run_id, "Competitor Analysis")
    assert inbox[0]["payload"]["gap"] == "sample unmet need"

    ledger.complete_stage(run_id, "market_gap", {"gap": "sample unmet need"})
    board = ledger.task_board(run_id)
    assert next(item for item in board if item["stage_id"] == "competitors")["status"] == "ready"
    assert ledger.audit_log(run_id)


def test_market_gate_requires_multiple_source_urls():
    from pipeline_gates import evaluate_market_gate

    assert not evaluate_market_gate("No verifiable results returned.")["passed"]
    result = evaluate_market_gate(
        "Research:\\nhttps://example.com/a evidence\\nhttps://example.org/b evidence"
    )
    assert result["passed"]
    assert result["source_count"] == 2
    partial_failure = evaluate_market_gate(
        "Live web research unavailable from one provider\\nhttps://example.com/a evidence\\nhttps://example.org/b evidence"
    )
    assert partial_failure["passed"]
    assert partial_failure["source_count"] == 2


def test_release_gate_fails_closed_until_all_reviews_pass():
    from pipeline_gates import evaluate_release_gate

    files = {"generated-project/README.md": "# Demo"}
    checks = {"passed": True, "failures": 0}
    assert not evaluate_release_gate(files, checks, "QA okay", "Security okay")["passed"]
    assert not evaluate_release_gate(files, checks, "RELEASE_GATE: PASS", "RELEASE_GATE: FAIL")["passed"]
    passed = evaluate_release_gate(files, checks, "RELEASE_GATE: PASS", "RELEASE_GATE: PASS")
    assert passed["passed"]
    assert passed["status"] == "PASS"


def test_release_gate_blocks_static_failures():
    from pipeline_gates import evaluate_release_gate

    result = evaluate_release_gate(
        {"generated-project/app.py": "bad"},
        {"passed": False, "failures": 1},
        "RELEASE_GATE: PASS",
        "RELEASE_GATE: PASS",
    )
    assert not result["passed"]
    assert not result["static_checks_pass"]


def test_agents_have_fixed_specialist_scopes_and_explicit_handoffs():
    from agents import build_prompts

    team = build_team()
    by_name = {agent["name"]: agent for agent in team}
    assert "industry gaps" in by_name["Scout"]["role"].lower()
    assert "software engineer" in by_name["Dev"]["role"].lower()
    assert "qa engineer" in by_name["Tara"]["role"].lower()
    assert "security engineer" in by_name["Shield"]["role"].lower()
    assert "release engineer" in by_name["GitHub Integrator"]["role"].lower()
    assert "sales intelligence" in by_name["Lead Research"]["role"].lower()
    assert "follow-up" in by_name["Seller"]["role"].lower()
    assert "Atlas" not in by_name
    assert "Mira" not in by_name

    system, user = build_prompts(by_name["Dev"], "Demo", "Build a product", {"Nova": "MVP scope"})
    assert "Your fixed specialist scope" in system
    assert "HAND-OFF FROM Nova" in user
    assert "MVP scope" in user



def test_collect_market_research_uses_real_public_search_results(monkeypatch):
    import market_research

    calls = []

    def fake_search(query, limit=5):
        calls.append(query)
        if "competitors" in query:
            return [{"title": "Competitor review", "url": "https://example.org/competitors", "snippet": "Users report complex setup."}]
        return [{"title": "Customer discussion", "url": "https://example.com/pain", "snippet": "Small teams describe manual work."}]

    monkeypatch.setattr(market_research, "search_market_evidence", fake_search)
    pack = market_research.collect_market_research("Build a simple workflow product", limit=2)

    assert len(calls) >= 2
    assert any("complaints" in query for query in calls)
    assert any("competitors" in query for query in calls)
    assert len(pack["source_urls"]) == 2
    assert "ResearchGate" in pack["context"]
    assert "https://example.com/pain" in pack["context"]
    assert "https://example.org/competitors" in pack["context"]


def test_market_gate_counts_actual_source_urls():
    from pipeline_gates import evaluate_market_gate

    result = evaluate_market_gate("\n".join(["https://example.com/a", "https://example.org/b"]))
    assert result["passed"]
    assert result["source_count"] == 2
