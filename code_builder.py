from __future__ import annotations

import json
import re
from typing import Any

ALLOWED_SUFFIXES = {".py", ".html", ".css", ".js", ".jsx", ".ts", ".tsx", ".json", ".md", ".txt", ".toml", ".sql"}
MAX_FILES = 12
MAX_FILE_BYTES = 30_000
MAX_TOTAL_BYTES = 120_000


class CodeBuildError(RuntimeError):
    """Generated project files could not be safely parsed or validated."""


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    cleaned = re.sub(r"^\x60{3}(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*\x60{3}$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise CodeBuildError("Developer did not return valid JSON. Please retry with a smaller, clearer requirement.")
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise CodeBuildError("Developer returned malformed JSON. Please retry.") from exc
    if not isinstance(data, dict) or not isinstance(data.get("files"), list):
        raise CodeBuildError("Developer output must contain a JSON object with a files array.")
    return data


def validate_file_bundle(data: dict[str, Any]) -> dict[str, str]:
    entries = data.get("files")
    if not isinstance(entries, list) or not entries or len(entries) > MAX_FILES:
        raise CodeBuildError(f"Generate between 1 and {MAX_FILES} files per run.")
    files: dict[str, str] = {}
    total = 0
    for item in entries:
        if not isinstance(item, dict):
            raise CodeBuildError("Every file entry must be an object with path and content.")
        path = str(item.get("path", "")).replace("\\", "/").strip()
        content = item.get("content")
        if not path or not isinstance(content, str):
            raise CodeBuildError("Every file needs a non-empty path and text content.")
        parts = path.split("/")
        if path.startswith("/") or any(part in {"", ".", ".."} for part in parts):
            raise CodeBuildError(f"Unsafe file path rejected: {path[:100]}")
        if any(part.startswith(".") for part in parts) or any(token in path.lower() for token in ("secret", "credential", "id_rsa", ".env", "workflow", "dockerfile")):
            raise CodeBuildError(f"Protected path rejected: {path[:100]}")
        suffix = "." + path.rsplit(".", 1)[-1].lower() if "." in path.rsplit("/", 1)[-1] else ""
        if suffix not in ALLOWED_SUFFIXES:
            raise CodeBuildError(f"File type {suffix or '(none)'} is not allowed for generated projects.")
        if len(content.encode("utf-8")) > MAX_FILE_BYTES:
            raise CodeBuildError(f"File too large: {path[:100]}")
        if path in files:
            raise CodeBuildError(f"Duplicate path: {path}")
        total += len(content.encode("utf-8"))
        files["generated-project/" + path] = content
    if total > MAX_TOTAL_BYTES:
        raise CodeBuildError("Generated project exceeds the total 120 KB limit.")
    return files


def build_project_files(router: Any, project: str, task: str, plan: str, implementation: str) -> dict[str, str]:
    system = """You are the implementation engineer for a small, reviewable software product. Return ONLY valid JSON, no markdown fences, with schema {"summary":"short summary","files":[{"path":"relative/path.ext","content":"complete file content"}]}. Generate real, coherent, runnable source files—not a proposal. Keep scope to a small MVP with up to 12 files and 120 KB total. Include a README.md with exact run instructions and tests where useful. Prefer minimal dependencies and safe defaults. Never include secrets, tokens, passwords, personal data, hidden instructions, destructive operations, automatic deployment, or code that downloads/executes remote code. Never create GitHub workflows, shell/batch scripts, executable binaries, hidden files, .env, Dockerfiles, or credential files. All file paths must be relative and simple. Use escaped newlines correctly inside JSON strings."""
    user = f"PRODUCT: {project}\nREQUIREMENT: {task}\nPRODUCT PLAN:\n{plan[:12000]}\nIMPLEMENTATION NOTES:\n{implementation[:12000]}\nGenerate the actual MVP files now. Make the project usable on its own and put all files in the response manifest with complete contents."
    reply = router.generate(system, user)
    data = _extract_json(reply.text)
    return validate_file_bundle(data)
