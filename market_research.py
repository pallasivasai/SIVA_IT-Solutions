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


def collect_market_research(query: str, limit: int = 5) -> dict[str, Any]:
    """Collect live public web evidence for Scout; this is not tied to ResearchGate."""
    clean_query = " ".join((query or "").split())[:1200]
    searches = [
        clean_query + " customer complaints problems unmet needs reviews",
        clean_query + " existing tools competitors pricing limitations",
        clean_query + " Reddit forum discussions workflow pain points alternatives",
        clean_query + " market trends underserved customers",
    ]
    gathered: list[dict[str, str]] = []
    seen: set[str] = set()
    diagnostics: list[str] = []
    for term in searches:
        for item in search_market_evidence(term, limit):
            url = item.get("url", "").strip()
            if not url:
                if item.get("snippet"):
                    diagnostics.append(item["snippet"])
                continue
            if url not in seen:
                seen.add(url)
                gathered.append(item)
        if len(gathered) >= 12:
            break
    lines = [
        "LIVE PUBLIC WEB RESEARCH — no ResearchGate dependency.",
        "Search uses public web search (DDGS with Bing RSS fallback); the configured AI model analyses the returned evidence.",
        f"User goal/query: {clean_query}",
        f"Distinct public URLs collected: {len(gathered)}",
        "Scout must identify customer pain, competitor alternatives and weaknesses, underserved users, and evidence-backed gaps. Separate evidence from hypotheses.",
    ]
    for item in gathered[:20]:
        lines.append(f"- {item['title']}\n  URL: {item['url']}\n  Snippet: {item['snippet']}")
    if diagnostics:
        lines.append("\nSEARCH DIAGNOSTICS:")
        lines.extend("- " + d for d in dict.fromkeys(diagnostics))
    if not gathered:
        lines.append("No verifiable public results returned. Do not invent sources or claim research completed.")
    return {"query": clean_query, "results": gathered[:20],
            "source_urls": [item["url"] for item in gathered[:20]],
            "diagnostics": list(dict.fromkeys(diagnostics)), "context": "\n".join(lines)}


def build_research_context(query: str) -> str:
    """Compatibility wrapper for existing workflows."""
    return str(collect_market_research(query)["context"])
