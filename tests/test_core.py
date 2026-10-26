from agents import build_team
from ai_providers import ProviderRouter


def test_team_members_and_roles():
    team = build_team()
    assert len(team) == 8
    assert [m["name"] for m in team] == ["Atlas", "Mira", "Scout", "Nova", "Dev", "Tara", "Shield", "Seller"]


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
