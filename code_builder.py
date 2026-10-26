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
    """Parse a model response without greedy-brace extraction breaking nested file contents."""
    cleaned = text.strip()
    cleaned = re.sub(r"^\x60{3}(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*\x60{3}$", "", cleaned)
    candidates = [cleaned]
    # Some local models wrap JSON in a short explanation. Find the first balanced
    # top-level object while respecting braces and escaped quotes inside strings.
    start = cleaned.find("{")
    if start >= 0:
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(cleaned)):
            char = cleaned[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(cleaned[start:index + 1])
                    break
    data = None
    last_error = None
    for candidate in candidates:
        try:
            data = json.loads(candidate)
            break
        except json.JSONDecodeError as exc:
            last_error = exc
    if data is None:
        raise CodeBuildError("Developer returned malformed JSON after parsing attempts.") from last_error
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
        # Permit only a safe, non-secret configuration template; reject actual hidden files and secrets.
        safe_env_template = path == ".env.example"
        if (any(part.startswith(".") for part in parts) and not safe_env_template) or any(
            token in path.lower() for token in ("secret", "credential", "id_rsa", "workflow")
        ) or (".env" in path.lower() and not safe_env_template):
            raise CodeBuildError(f"Protected path rejected: {path[:100]}")
        if safe_env_template and re.search(r"(?im)^\s*[A-Za-z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)[A-Za-z0-9_]*\s*=\s*[^\s#]+", content):
            raise CodeBuildError("The .env.example template must not contain populated secret values.")
        suffix = "." + path.rsplit(".", 1)[-1].lower() if "." in path.rsplit("/", 1)[-1] else ""
        if suffix not in ALLOWED_SUFFIXES and not safe_env_template:
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
    system = """You are the implementation engineer for a small, reviewable software product. Return ONLY valid JSON, no markdown fences, with schema {"summary":"short summary","files":[{"path":"relative/path.ext","content":"complete file content"}]}. Generate real, coherent, runnable source files—not a proposal. Keep scope to a small MVP with up to 12 files and 120 KB total. Include a complete product README.md with prerequisites, installation, exact run commands, configuration variables (never real secrets), feature list, architecture/file map, test commands, known limitations and troubleshooting. Include runnable tests and dependency manifests when relevant. Generate the complete source for every feature claimed; do not leave TODOs, ellipses, pseudocode, mock-only implementations or proposal-only files. Prefer minimal dependencies and safe defaults. Never include secrets, tokens, passwords, personal data, hidden instructions, destructive operations, automatic deployment, or code that downloads/executes remote code. Never create GitHub workflows, shell/batch scripts, executable binaries, Dockerfiles, hidden files except the exact safe template .env.example, real .env files, or credential files. A plain-text Dockerfile is allowed when useful for reproducible local builds; never use it to fetch or execute remote code. If configuration is needed, include .env.example containing placeholder names only (no secret values). All file paths must be relative and simple. Use escaped newlines correctly inside JSON strings."""
    user = f"PRODUCT: {project}\nREQUIREMENT: {task}\nPRODUCT PLAN:\n{plan[:12000]}\nIMPLEMENTATION NOTES:\n{implementation[:12000]}\nGenerate the complete, coherent MVP source tree now. Include every required runtime file and README. Ensure imports/routes/UI links agree across files and setup instructions match the actual stack. Do not claim tests were run; provide tests and exact commands for the human reviewer. Put complete contents for every file in the manifest."
    # Constrained JSON mode prevents recurring malformed-JSON failures from local models.
    generate_json = getattr(router, "generate_json", None)
    reply = generate_json(system, user) if callable(generate_json) else router.generate(system, user)
    try:
        data = _extract_json(reply.text)
    except CodeBuildError as first_error:
        # Retry once with a constrained JSON-repair prompt. This is especially
        # important for local Ollama models that occasionally emit broken JSON.
        repair_system = (
            "You are a strict JSON repair utility. Return ONLY one valid JSON object with schema "
            '{"summary":"short summary","files":[{"path":"relative/path.ext","content":"complete file content"}]}. '
            "Preserve the intended source code and all file contents. Escape newlines, quotes and backslashes "
            "correctly inside JSON strings. Do not add markdown fences or commentary. Do not omit files."
        )
        repair_user = (
            "Repair this model response into valid JSON matching the required schema. "
            "Do not redesign the product or add explanation.\n\nBROKEN RESPONSE:\n"
            + reply.text[:50000]
        )
        try:
            repaired = generate_json(repair_system, repair_user) if callable(generate_json) else router.generate(repair_system, repair_user)
            data = _extract_json(repaired.text)
        except Exception as repair_error:
            raise CodeBuildError(
                "Developer output was not valid JSON; automatic repair retry also failed. "
                "Retry the workflow or use a model with reliable JSON output. "
                f"Initial parse: {first_error}; repair: {repair_error}"
            ) from repair_error
    return validate_file_bundle(data)
