from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any
import streamlit as st

class GitHubError(RuntimeError):
    pass

def _setting(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value:
        return value
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return default

class GitHubService:
    """Creates a dedicated feature branch and PR. Does not merge or deploy."""
    def __init__(self) -> None:
        token = _setting("GITHUB_TOKEN")
        self.owner = _setting("GITHUB_OWNER", "pallasivasai")
        self.repo = _setting("GITHUB_REPO", "SIVA_IT-Solutions")
        if not token:
            raise GitHubError("GITHUB_TOKEN is missing. Add it through Streamlit Secrets or environment variables.")
        try:
            from github import Auth, Github
            self.client = Github(auth=Auth.Token(token), timeout=30)
            self.repository = self.client.get_repo(f"{self.owner}/{self.repo}")
        except Exception as exc:
            raise GitHubError(f"Could not initialize GitHub client: {exc}") from exc

    @staticmethod
    def _slug(text: str) -> str:
        result = re.sub(r"[^a-zA-Z0-9-]+", "-", text.lower()).strip("-")
        return (result or "task")[:32].strip("-")

    def generate_file_bundle(self, result: dict[str, Any]) -> dict[str, str]:
        outputs = result.get("outputs", {})
        project = str(result.get("project", "project"))
        task = str(result.get("task", ""))
        created = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        content = f"""# Product delivery: {project}\n\nCreated: {created}\n\n> AI-generated review artifact. Inspect product code and validate it before use. Nothing was auto-merged or deployed.\n\n## Original goal\n\n{task}\n\n## Task assignment\n\n{outputs.get('assignment', outputs.get('plan', 'Not available'))}\n\n## Industry-gap research and evidence\n\n{outputs.get('research', outputs.get('market_evidence', 'Not available'))}\n\n## Product strategy: how this product fills the gap\n\n{outputs.get('product_strategy', 'Not available')}\n\n## Implementation proposal\n\n{outputs.get('implementation', 'Not available')}\n\n## QA report\n\n{outputs.get('qa', 'Not available')}\n\n## Security review\n\n{outputs.get('security', 'Not available')}\n\n## Sales and go-to-market plan\n\n{outputs.get('sales', 'Not available')}\n\n## How to use this PR\n\n1. Open the matching folder under products/.\n2. Read README.md for setup and run commands.\n3. Review source, tests and dependencies; run in a disposable local environment.\n4. Confirm research links and validate pricing/market assumptions.\n5. Request human review before merging.\n\n## Human approval boundary\n\nThis PR does not merge or deploy itself.\n"""
        if len(content.encode("utf-8")) > 100_000:
            raise GitHubError("Proposal exceeds the 100 KB safety limit.")
        files = {"ai-workflow/README.md": content}
        generated = result.get("files", {})
        if generated:
            if not isinstance(generated, dict) or len(generated) > 12:
                raise GitHubError("Generated project file bundle is invalid or too large.")
            product_slug = self._slug(project)
            for path, body in generated.items():
                if not isinstance(path, str) or not path.startswith("generated-project/") or ".." in path.split("/") or not isinstance(body, str):
                    raise GitHubError("Unsafe generated project file rejected.")
                if len(body.encode("utf-8")) > 30_000:
                    raise GitHubError(f"Generated file exceeds 30 KB: {path}")
                product_path = "products/" + product_slug + "/" + path[len("generated-project/"):]
                if product_path in files:
                    raise GitHubError(f"Duplicate generated file path: {product_path}")
                files[product_path] = body
            files["products/" + product_slug + "/PRODUCT_BRIEF.md"] = (
                f"# {project}\n\n"
                "## What this product does\n\n" + str(outputs.get("product_strategy", "See the parent ai-workflow report.")) +
                "\n\n## Research and customer gap\n\n" + str(outputs.get("research", "See the parent ai-workflow report.")) +
                "\n\n## How to run\n\nRead README.md in this folder and follow its setup instructions. Review and test before production use.\n"
            )
        if sum(len(body.encode("utf-8")) for body in files.values()) > 220_000:
            raise GitHubError("Combined PR bundle exceeds the 220 KB safety limit.")
        return files

    def create_change_request(self, project_name: str, task: str, files: dict[str, str], base_branch: str = "main") -> dict[str, Any]:
        if not files or len(files) > 14:
            raise GitHubError("Empty file bundle or more than 14 files; stopping for safety.")
        if any(path.startswith("/") or ".." in path.split("/") for path in files):
            raise GitHubError("Unsafe file path rejected.")
        base = self.repository.get_branch(base_branch)
        branch_name = f"ai-proposal/{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{self._slug(project_name)}"
        self.repository.create_git_ref(ref=f"refs/heads/{branch_name}", sha=base.commit.sha)
        for path, body in files.items():
            self.repository.create_file(path=path, message=f"docs: add AI proposal for {project_name}", content=body, branch=branch_name)
        pr = self.repository.create_pull(title=f"AI proposal: {project_name[:100]}", body=f"""## Summary\nRole-based AI workflow proposal for human review.\n\n## Original requirement\n{task[:4000]}\n\n## Review checklist\n- [ ] Inspect proposed changes\n- [ ] Check acceptance criteria and tests\n- [ ] Review security and secrets\n- [ ] Approve explicitly before merge\n\n**Safety:** This app does not merge PRs, run generated code, or deploy production.\n""", head=branch_name, base=base_branch, draft=False)
        return {"number": pr.number, "url": pr.html_url, "branch": branch_name}

    def list_open_prs(self, owner: str, repo: str) -> list[dict[str, Any]]:
        try:
            target = self.client.get_repo(f"{owner}/{repo}")
            return [{"number": pr.number, "title": pr.title, "url": pr.html_url, "state": pr.state, "head": pr.head.ref, "base": pr.base.ref, "created_at": pr.created_at.isoformat()} for pr in target.get_pulls(state="open", sort="created", direction="desc")[:50]]
        except Exception as exc:
            raise GitHubError(f"Could not load pull requests: {exc}") from exc
