from __future__ import annotations

import html
import os
import time
from typing import Any
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
from xml.etree import ElementTree


def _normalise_rows(rows: Any, limit: int) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows or []:
        title = str(row.get("title", "")).strip()
        url = str(row.get("href", row.get("url", row.get("link", "")))).strip()
        body = str(row.get("body", row.get("snippet", row.get("description", "")))).strip()
        if title and url.startswith(("https://", "http://")) and url not in seen:
            seen.add(url)
            results.append({"title": title[:300], "url": url[:1000], "snippet": body[:900]})
        if len(results) >= limit:
            break
    return results


def _bing_rss_search(query: str, limit: int) -> list[dict[str, str]]:
    """Fallback public search endpoint; uses only returned results, never fabricated URLs."""
    url = "https://www.bing.com/search?format=rss&q=" + quote_plus(query)
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; SIVA-IT-Solutions-Research/1.0)",
            "Accept": "application/rss+xml, application/xml, text/xml",
        },
    )
    with urlopen(request, timeout=12) as response:
        payload = response.read(1_500_000)
    root = ElementTree.fromstring(payload)
    rows: list[dict[str, str]] = []
    for item in root.findall(".//item")[:limit]:
        title = html.unescape((item.findtext("title") or "").strip())
        link = (item.findtext("link") or "").strip()
        snippet = html.unescape((item.findtext("description") or "").strip())
        if title and link.startswith(("https://", "http://")):
            rows.append({"title": title[:300], "url": link[:1000], "snippet": snippet[:900]})
    return rows


def search_market_evidence(query: str, limit: int = 6) -> list[dict[str, str]]:
    """Search live public web sources with a real fallback and transparent failure diagnostics."""
    max_results = max(1, min(limit, 8))
    failures: list[str] = []

    # First choice: DDGS package. Different versions expose the same text API.
    try:
        from ddgs import DDGS
        with DDGS(timeout=10) as ddgs:
            rows = ddgs.text(query, max_results=max_results)
        results = _normalise_rows(rows, max_results)
        if results:
            return results
        failures.append("DDGS returned zero usable results")
    except Exception as exc:
        failures.append(f"DDGS: {type(exc).__name__}: {str(exc)[:180]}")

    # Streamlit deployments can have a DDGS backend blocked or rate-limited; try Bing RSS.
    try:
        results = _bing_rss_search(query, max_results)
        if results:
            return results
        failures.append("Bing RSS returned zero usable results")
    except Exception as exc:
        failures.append(f"Bing RSS: {type(exc).__name__}: {str(exc)[:180]}")

    # Return a diagnostic record with no URL so the market gate cannot mistake it for evidence.
    return [{
        "title": "Live web research unavailable",
        "url": "",
        "snippet": "No public search provider returned verifiable results. " + " | ".join(failures)
        + ". Check outbound network access and the ddgs dependency in Streamlit Cloud; retry later.",
    }]


def build_research_context(query: str) -> str:
    searches = [
        query + " customer pain points alternatives reviews",
        query + " competitors pricing product gaps",
        query + " underserved users complaints workflow",
    ]
    gathered: list[dict[str, str]] = []
    seen: set[str] = set()
    errors: list[str] = []
    for term in searches:
        for item in search_market_evidence(term, 5):
            url = item.get("url", "").strip()
            if not url:
                if item.get("snippet"):
                    errors.append(item["snippet"])
                continue
            if url not in seen:
                seen.add(url)
                gathered.append(item)
        # Stop early when enough diverse sources have been collected.
        if len(gathered) >= 10:
            break

    lines = [
        "Public web research results (live search snippets are leads, not independently verified claims):",
        f"Distinct public URLs collected: {len(seen)}",
    ]
    for item in gathered[:15]:
        lines.append(f"- {item['title']}\n  URL: {item['url']}\n  Snippet: {item['snippet']}")
    if errors:
        lines.append("\nLIVE SEARCH DIAGNOSTICS:")
        for error in dict.fromkeys(errors):
            lines.append("- " + error)
    if not gathered:
        lines.append("No verifiable search results returned. Do not invent citations; label market observations as hypotheses.")
    return "\n".join(lines)
