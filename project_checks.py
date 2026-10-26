from __future__ import annotations

import ast
import json
from pathlib import PurePosixPath
from typing import Mapping


def inspect_generated_files(files: Mapping[str, str]) -> dict[str, object]:
    """Run non-executing syntax and risk checks over AI-generated text files."""
    checks: list[dict[str, str]] = []
    if not files:
        return {"passed": False, "checks": [{"status": "FAIL", "detail": "No generated files to inspect."}]}

    paths = list(files)
    readme_present = any(PurePosixPath(p).name.lower() == "readme.md" for p in paths)
    checks.append({"status": "PASS" if readme_present else "WARN", "detail": "README with run instructions present." if readme_present else "README.md is missing."})

    for path, source in files.items():
        if path.endswith(".py"):
            try:
                ast.parse(source, filename=path)
                checks.append({"status": "PASS", "detail": f"Python syntax parses: {path}"})
            except SyntaxError as exc:
                checks.append({"status": "FAIL", "detail": f"Python syntax error in {path}:{exc.lineno}: {exc.msg}"})
        elif path.endswith(".json"):
            try:
                json.loads(source)
                checks.append({"status": "PASS", "detail": f"Valid JSON: {path}"})
            except json.JSONDecodeError as exc:
                checks.append({"status": "FAIL", "detail": f"Invalid JSON in {path}:{exc.lineno}: {exc.msg}"})

        lowered = source.lower()
        risky_patterns = (
            ("eval(", "dynamic eval"),
            ("exec(", "dynamic exec"),
            ("os.system(", "shell execution"),
            ("subprocess.", "subprocess execution"),
            ("pickle.loads(", "unsafe pickle deserialization"),
        )
        for needle, label in risky_patterns:
            if needle in lowered:
                checks.append({"status": "WARN", "detail": f"Review {label} usage in {path}."})
        if "-----begin private key-----" in lowered or "ghp_" in source or "sk-" in source:
            checks.append({"status": "FAIL", "detail": f"Possible hard-coded credential in {path}; remove before review."})

    failures = sum(item["status"] == "FAIL" for item in checks)
    warnings = sum(item["status"] == "WARN" for item in checks)
    return {"passed": failures == 0, "failures": failures, "warnings": warnings, "checks": checks}
