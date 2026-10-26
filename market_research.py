from __future__ import annotations

from typing import Any


def search_market_evidence(query: str, limit: int = 6) -> list[dict[str, str]]:
    """Retrieve a small set of public web search results; failures are explicit, not fabricated."""
    try:
        from ddgs import DDGS
        rows = DDGS().text(query, max_results=max(1, min(limit, 8)))
        results = []
        for row in rows or []:
            title = str(row.get("title", "")).strip()
            url = str(row.get("href", row.get("url", ""))).strip()
            body = str(row.get("body", "")).strip()
            if title and url.startswith(("https://", "http://")):
                results.append({"title": title[:300], "url": url[:1000], "snippet": body[:900]})
        return results
    except Exception as exc:
        return [{"title": "Live web research unavailable", "url": "", "snippet": f"Search could not run ({type(exc).__name__}). Treat AI market claims as hypotheses and retry when network/dependency access is available."}]


def build_research_context(query: str) -> str:
    searches = [
        (query + " customer pain points alternatives reviews"),
        (query + " competitors pricing product gaps"),
        (query + " underserved users complaints workflow"),
    ]
    gathered: list[dict[str, str]] = []
    seen: set[str] = set()
    for term in searches:
        for item in search_market_evidence(term, 5):
            url = item.get("url", "")
            key = url or item.get("snippet", "")
            if key and key not in seen:
                seen.add(key)
                gathered.append(item)
    if not gathered:
        return "No verifiable search results returned. Do not invent citations; label market observations as hypotheses."
    lines = ["Public web research results (snippets are evidence leads, not independently verified facts):"]
    for item in gathered[:12]:
        lines.append(f"- {item['title']}\n  URL: {item['url'] or 'unavailable'}\n  Snippet: {item['snippet']}")
    return "\n".join(lines)
