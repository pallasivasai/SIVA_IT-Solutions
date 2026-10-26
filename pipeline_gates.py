from __future__ import annotations

import re
from typing import Any, Mapping
from urllib.parse import urlparse


_URL_RE = re.compile(r"https?://[^\s)\]>]+", re.IGNORECASE)


def evaluate_market_gate(research_context: str) -> dict[str, Any]:
    """Require multiple real-looking public source URLs before product planning."""
    urls = set()
    for candidate in _URL_RE.findall(research_context or ""):
        url = candidate.rstrip(".,;:")
        parsed = urlparse(url)
        if parsed.scheme in {"http", "https"} and parsed.netloc and "." in parsed.netloc:
            urls.add(url)
    passed = len(urls) >= 2 and "live web research unavailable" not in (research_context or "").lower()
    return {
        "passed": passed,
        "source_count": len(urls),
        "sources": sorted(urls),
        "reason": "Sufficient source URLs collected." if passed else
            "Research gate blocked: need at least two distinct public source URLs. Retry live research; do not invent evidence.",
    }


def evaluate_release_gate(files: Mapping[str, str], static_checks: Mapping[str, Any],
                          qa_report: str, security_report: str) -> dict[str, Any]:
    """Fail closed: seller/release may proceed only with files, clean deterministic checks,
    and explicit PASS markers from both independent review roles."""
    qa_pass = bool(re.search(r"(?im)^\s*RELEASE_GATE\s*:\s*PASS\s*$", qa_report or ""))
    security_pass = bool(re.search(r"(?im)^\s*RELEASE_GATE\s*:\s*PASS\s*$", security_report or ""))
    checks_pass = bool(static_checks.get("passed")) and int(static_checks.get("failures", 0) or 0) == 0
    files_present = bool(files)
    reasons = []
    if not files_present:
        reasons.append("No generated product source files.")
    if not checks_pass:
        reasons.append("Deterministic source checks failed or did not pass.")
    if not qa_pass:
        reasons.append("QA did not explicitly return RELEASE_GATE: PASS.")
    if not security_pass:
        reasons.append("Security did not explicitly return RELEASE_GATE: PASS.")
    return {
        "passed": files_present and checks_pass and qa_pass and security_pass,
        "qa_pass": qa_pass,
        "security_pass": security_pass,
        "static_checks_pass": checks_pass,
        "reasons": reasons,
        "status": "PASS" if not reasons else "BLOCKED",
    }
