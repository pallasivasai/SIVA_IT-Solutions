from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Agent registry: each role has a clear owner and required output.
AGENT_ROLES: tuple[dict[str, str], ...] = (
    {"name": "Market Gap Research", "group": "market", "deliverable": "Ranked customer problems with dated source URLs and confidence"},
    {"name": "Competitor Analysis", "group": "market", "deliverable": "Competitor matrix, alternatives, differentiators and evidence"},
    {"name": "Customer Validation", "group": "market", "deliverable": "Validation plan, interview/survey questions and evidence gaps"},
    {"name": "Market Sizing", "group": "market", "deliverable": "TAM/SAM/SOM assumptions with calculation and source notes"},
    {"name": "Opportunity Scoring", "group": "market", "deliverable": "Weighted opportunity score, risks and recommendation"},
    {"name": "Product Manager", "group": "strategy", "deliverable": "Approved MVP scope, user stories and acceptance criteria"},
    {"name": "IT Services Strategy", "group": "strategy", "deliverable": "Service packages, delivery model and customer fit"},
    {"name": "Pricing and Financial Analysis", "group": "strategy", "deliverable": "Cost assumptions, pricing hypotheses and sensitivity notes"},
    {"name": "Software Architect", "group": "strategy", "deliverable": "Architecture, interfaces, data flows and threat boundaries"},
    {"name": "Backend Developer", "group": "engineering", "deliverable": "Backend source, API and unit tests"},
    {"name": "Frontend Developer", "group": "engineering", "deliverable": "UI source and component tests"},
    {"name": "Database Engineer", "group": "engineering", "deliverable": "Schema, migrations and data access tests"},
    {"name": "API Integration Agent", "group": "engineering", "deliverable": "Integration adapters, contracts and failure handling"},
    {"name": "Code Review Agent", "group": "engineering", "deliverable": "Independent maintainability and correctness review"},
    {"name": "QA Test Engineer", "group": "quality-security", "deliverable": "Runnable tests, test matrix and execution evidence"},
    {"name": "Independent QA Auditor", "group": "quality-security", "deliverable": "Independent acceptance-criteria audit and uncovered risks"},
    {"name": "Defensive Cybersecurity Engineer", "group": "quality-security", "deliverable": "Threat model and concrete defensive fixes"},
    {"name": "Security Verification Auditor", "group": "quality-security", "deliverable": "Independent security verification and residual risks"},
    {"name": "Product Positioning", "group": "marketing-sales", "deliverable": "Positioning and value proposition tied to implemented features"},
    {"name": "Marketing Content", "group": "marketing-sales", "deliverable": "Landing-page copy and launch content drafts"},
    {"name": "Sales Strategy", "group": "marketing-sales", "deliverable": "Buyer profile, sales motion and ethical outreach drafts"},
    {"name": "Lead Research", "group": "marketing-sales", "deliverable": "Permitted prospect research with source and confidence; no unsolicited sends"},
    {"name": "Customer Feedback Analyst", "group": "marketing-sales", "deliverable": "Feedback themes, evidence and product backlog proposals"},
    {"name": "CEO / Workflow Orchestrator", "group": "governance", "deliverable": "Dependency-aware task plan, approvals and blocker escalation"},
    {"name": "Final Release Auditor", "group": "governance", "deliverable": "Evidence-based release gate and unresolved-risk checklist"},
)

# Dependency edges make handoffs explicit. Each stage consumes the preceding stages' messages.
WORKFLOW_STAGES: tuple[dict[str, Any], ...] = (
    {"id": "market_gap", "owner": "Market Gap Research", "depends_on": [], "approval": "none"},
    {"id": "competitors", "owner": "Competitor Analysis", "depends_on": ["market_gap"], "approval": "none"},
    {"id": "validation", "owner": "Customer Validation", "depends_on": ["market_gap", "competitors"], "approval": "none"},
    {"id": "market_size", "owner": "Market Sizing", "depends_on": ["market_gap", "competitors"], "approval": "none"},
    {"id": "score", "owner": "Opportunity Scoring", "depends_on": ["market_gap", "competitors", "validation", "market_size"], "approval": "founder_opportunity"},
    {"id": "product_plan", "owner": "Product Manager", "depends_on": ["score"], "approval": "founder_scope"},
    {"id": "architecture", "owner": "Software Architect", "depends_on": ["product_plan"], "approval": "none"},
    {"id": "implementation", "owner": "Backend Developer", "depends_on": ["architecture"], "approval": "none"},
    {"id": "frontend", "owner": "Frontend Developer", "depends_on": ["implementation"], "approval": "none"},
    {"id": "database", "owner": "Database Engineer", "depends_on": ["architecture"], "approval": "none"},
    {"id": "integrations", "owner": "API Integration Agent", "depends_on": ["architecture"], "approval": "none"},
    {"id": "code_review", "owner": "Code Review Agent", "depends_on": ["implementation", "frontend", "database", "integrations"], "approval": "none"},
    {"id": "qa", "owner": "QA Test Engineer", "depends_on": ["code_review"], "approval": "none"},
    {"id": "qa_audit", "owner": "Independent QA Auditor", "depends_on": ["qa"], "approval": "none"},
    {"id": "security", "owner": "Defensive Cybersecurity Engineer", "depends_on": ["implementation", "frontend", "database", "integrations", "qa"], "approval": "none"},
    {"id": "security_audit", "owner": "Security Verification Auditor", "depends_on": ["security", "qa_audit"], "approval": "none"},
    {"id": "positioning", "owner": "Product Positioning", "depends_on": ["product_plan", "market_gap"], "approval": "none"},
    {"id": "marketing", "owner": "Marketing Content", "depends_on": ["positioning"], "approval": "none"},
    {"id": "sales", "owner": "Sales Strategy", "depends_on": ["positioning", "market_size"], "approval": "none"},
    {"id": "lead_research", "owner": "Lead Research", "depends_on": ["sales"], "approval": "none"},
    {"id": "feedback", "owner": "Customer Feedback Analyst", "depends_on": ["validation", "product_plan"], "approval": "none"},
    {"id": "release_audit", "owner": "Final Release Auditor", "depends_on": ["qa_audit", "security_audit", "marketing", "sales"], "approval": "founder_release"},
    {"id": "github_pr", "owner": "CEO / Workflow Orchestrator", "depends_on": ["release_audit"], "approval": "founder_repository_and_pr"},
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkflowLedger:
    """Durable SQLite run, task, message/handoff and approval ledger.

    Point SIVA_WORKFLOW_DB at a persistent local disk path. Streamlit Cloud's
    ephemeral filesystem is not a durable shared database across app restarts or workers.
    """

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or os.getenv("SIVA_WORKFLOW_DB", "data/workflow-ledger.db")
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS workflow_runs (
                    run_id TEXT PRIMARY KEY, project TEXT NOT NULL, requirement TEXT NOT NULL,
                    status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS workflow_tasks (
                    task_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, stage_id TEXT NOT NULL,
                    owner TEXT NOT NULL, dependencies TEXT NOT NULL, status TEXT NOT NULL,
                    approval TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                    result TEXT NOT NULL DEFAULT '', error TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    UNIQUE(run_id, stage_id)
                );
                CREATE TABLE IF NOT EXISTS agent_messages (
                    message_id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
                    stage_id TEXT NOT NULL, sender TEXT NOT NULL, recipient TEXT NOT NULL,
                    message_type TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS approval_requests (
                    approval_id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
                    stage_id TEXT NOT NULL, approval_type TEXT NOT NULL, status TEXT NOT NULL,
                    decision_by TEXT NOT NULL DEFAULT '', decision_note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS workflow_audit (
                    audit_id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
                    actor TEXT NOT NULL, action TEXT NOT NULL, details TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_task_ready ON workflow_tasks(run_id,status,created_at);
                CREATE INDEX IF NOT EXISTS idx_messages_run ON agent_messages(run_id,message_id);
            """)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=15000")
        return conn

    def create_run(self, project: str, requirement: str, run_id: str | None = None) -> str:
        ident, now = run_id or str(uuid.uuid4()), _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("INSERT INTO workflow_runs VALUES(?,?,?,?,?,?)",
                         (ident, project, requirement, "queued", now, now))
            for stage in WORKFLOW_STAGES:
                conn.execute(
                    "INSERT INTO workflow_tasks(task_id,run_id,stage_id,owner,dependencies,status,approval,created_at,updated_at) VALUES(?,?,?,?,?,'blocked',?,?,?)",
                    (str(uuid.uuid4()), ident, stage["id"], stage["owner"], json.dumps(stage["depends_on"]), stage["approval"], now, now))
            conn.execute("UPDATE workflow_tasks SET status='ready' WHERE run_id=? AND dependencies='[]'", (ident,))
            conn.execute("UPDATE workflow_runs SET status='running',updated_at=? WHERE run_id=?", (now, ident))
            conn.execute("INSERT INTO workflow_audit(run_id,actor,action,details,created_at) VALUES(?,?,?,?,?)",
                         (ident, "system", "run_created", json.dumps({"project": project, "task_count": len(WORKFLOW_STAGES)}), now))
            conn.commit()
        return ident

    def send_message(self, run_id: str, stage_id: str, sender: str, recipient: str,
                     payload: dict[str, Any], message_type: str = "handoff") -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO agent_messages(run_id,stage_id,sender,recipient,message_type,payload,created_at) VALUES(?,?,?,?,?,?,?)",
                (run_id, stage_id, sender, recipient, message_type, json.dumps(payload, ensure_ascii=False), _now()))
            conn.execute("INSERT INTO workflow_audit(run_id,actor,action,details,created_at) VALUES(?,?,?,?,?)",
                         (run_id, sender, "message_sent", json.dumps({"stage": stage_id, "recipient": recipient}), _now()))
            return int(cur.lastrowid)

    def inbox(self, run_id: str, recipient: str, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM agent_messages WHERE run_id=? AND recipient=? ORDER BY message_id LIMIT ?",
                                (run_id, recipient, min(max(1, int(limit)), 500))).fetchall()
        items = [dict(row) for row in rows]
        for item in items:
            item["payload"] = json.loads(item["payload"])
        return items

    def messages(self, run_id: str, limit: int = 200) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM agent_messages WHERE run_id=? ORDER BY message_id LIMIT ?",
                                (run_id, min(max(1, int(limit)), 1000))).fetchall()
        items = [dict(row) for row in rows]
        for item in items:
            item["payload"] = json.loads(item["payload"])
        return items

    def complete_stage(self, run_id: str, stage_id: str, result: dict[str, Any]) -> None:
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT task_id,owner,status FROM workflow_tasks WHERE run_id=? AND stage_id=?",
                               (run_id, stage_id)).fetchone()
            if row is None:
                raise KeyError(f"Unknown workflow stage: {stage_id}")
            if row["status"] == "completed":
                conn.commit()
                return
            conn.execute("UPDATE workflow_tasks SET status='completed',result=?,updated_at=? WHERE task_id=?",
                         (json.dumps(result, ensure_ascii=False), now, row["task_id"]))
            conn.execute("INSERT INTO workflow_audit(run_id,actor,action,details,created_at) VALUES(?,?,?,?,?)",
                         (run_id, row["owner"], "stage_completed", json.dumps({"stage": stage_id}), now))
            all_tasks = conn.execute("SELECT stage_id,dependencies,status FROM workflow_tasks WHERE run_id=?", (run_id,)).fetchall()
            statuses = {t["stage_id"]: t["status"] for t in all_tasks}
            for task in all_tasks:
                if task["status"] != "blocked":
                    continue
                deps = json.loads(task["dependencies"])
                if all(statuses.get(dep) == "completed" for dep in deps):
                    conn.execute("UPDATE workflow_tasks SET status='ready',updated_at=? WHERE run_id=? AND stage_id=?",
                                 (now, run_id, task["stage_id"]))
            remaining = conn.execute("SELECT COUNT(*) FROM workflow_tasks WHERE run_id=? AND status!='completed'", (run_id,)).fetchone()[0]
            conn.execute("UPDATE workflow_runs SET status=?,updated_at=? WHERE run_id=?",
                         ("completed" if remaining == 0 else "running", now, run_id))
            conn.commit()

    def request_approval(self, run_id: str, stage_id: str, approval_type: str) -> int:
        now = _now()
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO approval_requests(run_id,stage_id,approval_type,status,created_at,updated_at) VALUES(?,?,?,'pending',?,?)",
                (run_id, stage_id, approval_type, now, now))
            conn.execute("UPDATE workflow_tasks SET status='waiting_approval',updated_at=? WHERE run_id=? AND stage_id=?",
                         (now, run_id, stage_id))
            conn.execute("INSERT INTO workflow_audit(run_id,actor,action,details,created_at) VALUES(?,?,?,?,?)",
                         (run_id, "system", "approval_requested", json.dumps({"stage": stage_id, "type": approval_type}), now))
            return int(cur.lastrowid)

    def decide_approval(self, approval_id: int, approved: bool, decided_by: str, note: str = "") -> None:
        now, status = _now(), "approved" if approved else "rejected"
        with self._connect() as conn:
            row = conn.execute("SELECT run_id,stage_id FROM approval_requests WHERE approval_id=?", (approval_id,)).fetchone()
            if row is None:
                raise KeyError(f"Unknown approval request: {approval_id}")
            conn.execute("UPDATE approval_requests SET status=?,decision_by=?,decision_note=?,updated_at=? WHERE approval_id=?",
                         (status, decided_by, note, now, approval_id))
            conn.execute("UPDATE workflow_tasks SET status=?,updated_at=? WHERE run_id=? AND stage_id=?",
                         ("completed" if approved else "failed", now, row["run_id"], row["stage_id"]))
            conn.execute("INSERT INTO workflow_audit(run_id,actor,action,details,created_at) VALUES(?,?,?,?,?)",
                         (row["run_id"], decided_by, "approval_decided", json.dumps({"approval_id": approval_id, "status": status, "note": note}), now))

    def task_board(self, run_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM workflow_tasks WHERE run_id=? ORDER BY rowid", (run_id,)).fetchall()
        result = [dict(row) for row in rows]
        for item in result:
            item["dependencies"] = json.loads(item["dependencies"])
            try:
                item["result"] = json.loads(item["result"]) if item["result"] else {}
            except json.JSONDecodeError:
                pass
        return result

    def audit_log(self, run_id: str, limit: int = 200) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM workflow_audit WHERE run_id=? ORDER BY audit_id DESC LIMIT ?",
                                (run_id, min(max(1, int(limit)), 1000))).fetchall()
        result = [dict(row) for row in rows]
        for item in result:
            try:
                item["details"] = json.loads(item["details"])
            except json.JSONDecodeError:
                pass
        return result
