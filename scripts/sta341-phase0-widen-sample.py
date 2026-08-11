"""STA-341 Phase 0 — widen Serper vs Tavily quality sample (15–20 fresh live queries).

Runs BOTH providers in parallel on the same query set. Does not meter usage_records.
Requires TAVILY_API_KEY + SERPER_API_KEY (prefer: railway run with both set).
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

SERPER_URL = "https://google.serper.dev/search"
TAVILY_URL = "https://api.tavily.com/search"

# Fresh representative set — not the historical n=2 recovered hashes.
QUERIES: list[tuple[str, str]] = [
    ("factual", "What is the current US federal funds rate target range?"),
    ("factual", "What is the capital of New Zealand?"),
    ("factual", "How many bits are in an IPv6 address?"),
    ("current_event", "Latest US CPI inflation reading year over year"),
    ("current_event", "Who won the most recent Super Bowl?"),
    ("current_event", "Current OpenAI CEO name"),
    ("entity", "What does Stripe do as a company?"),
    ("entity", "Headquarters city of Salesforce"),
    ("entity", "Who founded Notion productivity software?"),
    ("entity", "What is HubSpot known for?"),
    ("comparison", "PostgreSQL vs MySQL primary differences for OLTP"),
    ("comparison", "React vs Vue which is more popular in 2026 enterprise apps"),
    ("comparison", "AWS vs Azure market share cloud computing"),
    ("lookup", "NIST Cybersecurity Framework 2.0 Govern function summary"),
    ("lookup", "CAN-SPAM Act main requirements for commercial email"),
    ("lookup", "SBA definition of a small business size standard overview"),
    ("time_sensitive", "Today's date UTC and day of week"),
    ("time_sensitive", "Next US federal holiday after today"),
]


def _load_env() -> None:
    try:
        from dotenv import dotenv_values
    except ImportError:
        return
    for path in (ROOT / "backend" / ".env.operator.local", ROOT / "backend" / ".env"):
        if not path.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                vals = dotenv_values(path, encoding=enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            continue
        for k, v in vals.items():
            if v and k not in os.environ:
                os.environ[k] = v


def _domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:  # noqa: BLE001
        return ""


async def search_serper(client: httpx.AsyncClient, query: str, api_key: str, num: int = 5) -> dict:
    t0 = time.perf_counter()
    try:
        resp = await client.post(
            SERPER_URL,
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query, "num": num},
        )
        latency_ms = int((time.perf_counter() - t0) * 1000)
        if resp.status_code >= 400:
            return {
                "provider": "serper",
                "ok": False,
                "error": f"http_{resp.status_code}",
                "latency_ms": latency_ms,
                "results": [],
            }
        data = resp.json()
        results = [
            {
                "title": str(item.get("title") or ""),
                "url": str(item.get("link") or ""),
                "snippet": str(item.get("snippet") or "")[:320],
            }
            for item in (data.get("organic") or [])[:num]
        ]
        return {
            "provider": "serper",
            "ok": True,
            "error": None,
            "latency_ms": latency_ms,
            "results": results,
            "answer_box": bool(data.get("answerBox") or data.get("knowledgeGraph")),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "provider": "serper",
            "ok": False,
            "error": str(exc)[:200],
            "latency_ms": int((time.perf_counter() - t0) * 1000),
            "results": [],
        }


async def search_tavily(client: httpx.AsyncClient, query: str, api_key: str, num: int = 5) -> dict:
    t0 = time.perf_counter()
    try:
        resp = await client.post(
            TAVILY_URL,
            json={
                "api_key": api_key,
                "query": query,
                "max_results": num,
                "include_answer": False,
            },
        )
        latency_ms = int((time.perf_counter() - t0) * 1000)
        if resp.status_code >= 400:
            return {
                "provider": "tavily",
                "ok": False,
                "error": f"http_{resp.status_code}",
                "latency_ms": latency_ms,
                "results": [],
            }
        data = resp.json()
        results = [
            {
                "title": str(item.get("title") or ""),
                "url": str(item.get("url") or ""),
                "snippet": str(item.get("content") or "")[:320],
            }
            for item in (data.get("results") or [])[:num]
        ]
        return {
            "provider": "tavily",
            "ok": True,
            "error": None,
            "latency_ms": latency_ms,
            "results": results,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "provider": "tavily",
            "ok": False,
            "error": str(exc)[:200],
            "latency_ms": int((time.perf_counter() - t0) * 1000),
            "results": [],
        }


def _compare(serper: dict, tavily: dict) -> dict:
    s_urls = [r["url"] for r in serper.get("results") or [] if r.get("url")]
    t_urls = [r["url"] for r in tavily.get("results") or [] if r.get("url")]
    s_dom = {_domain(u) for u in s_urls if _domain(u)}
    t_dom = {_domain(u) for u in t_urls if _domain(u)}
    overlap_domains = sorted(s_dom & t_dom)
    overlap_urls = sorted(set(s_urls) & set(t_urls))

    # Heuristic red flags: empty results, hard error, or zero domain overlap with both having results
    flags: list[str] = []
    if not serper.get("ok"):
        flags.append("serper_error")
    if not tavily.get("ok"):
        flags.append("tavily_error")
    if serper.get("ok") and not s_urls:
        flags.append("serper_empty")
    if tavily.get("ok") and not t_urls:
        flags.append("tavily_empty")
    if s_urls and t_urls and not overlap_domains:
        flags.append("no_domain_overlap")

    # Lightweight factual sanity: look for shared distinctive tokens in top snippets
    s_text = " ".join((r.get("snippet") or "") + " " + (r.get("title") or "") for r in (serper.get("results") or [])[:3]).lower()
    t_text = " ".join((r.get("snippet") or "") + " " + (r.get("title") or "") for r in (tavily.get("results") or [])[:3]).lower()
    # Extract year-like / rate-like tokens for soft agreement signal
    s_nums = set(re.findall(r"\b\d{1,4}(?:\.\d+)?%?\b", s_text))
    t_nums = set(re.findall(r"\b\d{1,4}(?:\.\d+)?%?\b", t_text))
    num_overlap = sorted(s_nums & t_nums)

    serper_worse = "serper_error" in flags or "serper_empty" in flags
    tavily_worse = "tavily_error" in flags or "tavily_empty" in flags
    material_divergence = "no_domain_overlap" in flags and not num_overlap

    quality_hold = (not serper_worse) and (not material_divergence or bool(overlap_domains or num_overlap))
    # If both OK with some overlap OR both OK with results, hold; fail only if Serper clearly worse/empty/error
    if serper.get("ok") and s_urls and tavily.get("ok") and t_urls:
        quality_hold = True
        if material_divergence:
            quality_hold = False
            flags.append("material_divergence_review")

    return {
        "overlap_domains": overlap_domains,
        "overlap_domain_count": len(overlap_domains),
        "overlap_urls": overlap_urls[:5],
        "num_token_overlap": num_overlap[:12],
        "flags": flags,
        "serper_result_count": len(s_urls),
        "tavily_result_count": len(t_urls),
        "serper_worse": serper_worse,
        "tavily_worse": tavily_worse,
        "quality_hold": quality_hold,
        "serper_top": [{"title": r.get("title"), "url": r.get("url"), "snippet": (r.get("snippet") or "")[:160]} for r in (serper.get("results") or [])[:3]],
        "tavily_top": [{"title": r.get("title"), "url": r.get("url"), "snippet": (r.get("snippet") or "")[:160]} for r in (tavily.get("results") or [])[:3]],
        "serper_latency_ms": serper.get("latency_ms"),
        "tavily_latency_ms": tavily.get("latency_ms"),
    }


async def main() -> int:
    _load_env()
    serper_key = (os.environ.get("SERPER_API_KEY") or "").strip()
    tavily_key = (os.environ.get("TAVILY_API_KEY") or "").strip()
    report: dict = {
        "record": "sta341_phase0_widen_sample",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "n_queries": len(QUERIES),
        "serper_configured": bool(serper_key),
        "tavily_configured": bool(tavily_key),
        "queries": [],
    }
    if not serper_key or not tavily_key:
        report["verdict"] = "NO_GO — missing API keys"
        report["error"] = {
            "serper": "missing SERPER_API_KEY" if not serper_key else "ok",
            "tavily": "missing TAVILY_API_KEY" if not tavily_key else "ok",
        }
        out = ROOT / "docs/delivery/sta341-phase0-widen-sample.json"
        out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2

    async with httpx.AsyncClient(timeout=30.0) as client:
        for kind, query in QUERIES:
            s_task = search_serper(client, query, serper_key)
            t_task = search_tavily(client, query, tavily_key)
            serper_res, tavily_res = await asyncio.gather(s_task, t_task)
            cmp = _compare(serper_res, tavily_res)
            report["queries"].append(
                {
                    "category": kind,
                    "query": query,
                    "comparison": cmp,
                    "serper_error": serper_res.get("error"),
                    "tavily_error": tavily_res.get("error"),
                }
            )
            print(
                f"[{kind}] hold={cmp['quality_hold']} overlap={cmp['overlap_domain_count']} "
                f"flags={cmp['flags']} :: {query[:70]}"
            )

    holds = [q for q in report["queries"] if q["comparison"]["quality_hold"]]
    fails = [q for q in report["queries"] if not q["comparison"]["quality_hold"]]
    serper_worse = [q for q in report["queries"] if q["comparison"]["serper_worse"]]
    avg_s = sum(q["comparison"]["serper_latency_ms"] or 0 for q in report["queries"]) / max(len(report["queries"]), 1)
    avg_t = sum(q["comparison"]["tavily_latency_ms"] or 0 for q in report["queries"]) / max(len(report["queries"]), 1)

    # Go if Serper is not materially worse on any query and hold rate >= 90%
    go = len(serper_worse) == 0 and (len(holds) / max(len(report["queries"]), 1)) >= 0.9
    report["summary"] = {
        "hold_count": len(holds),
        "fail_count": len(fails),
        "serper_worse_count": len(serper_worse),
        "hold_rate": round(len(holds) / max(len(report["queries"]), 1), 3),
        "avg_serper_latency_ms": round(avg_s),
        "avg_tavily_latency_ms": round(avg_t),
        "fail_queries": [{"query": q["query"], "flags": q["comparison"]["flags"]} for q in fails],
    }
    report["verdict"] = (
        "GO — Serper quality holds on widened sample; proceed to Phase 1"
        if go
        else "NO_GO — Serper quality does not hold; keep Tavily sole primary"
    )
    report["go"] = go
    report["finished_at"] = datetime.now(timezone.utc).isoformat()

    out = ROOT / "docs/delivery/sta341-phase0-widen-sample.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    md = ROOT / "docs/delivery/sta341-phase0-widen-sample.md"
    lines = [
        "# STA-341 Phase 0 — Widened Serper vs Tavily sample",
        "",
        f"**Ran:** {report['started_at']}",
        f"**N:** {report['n_queries']}",
        f"**Verdict:** {report['verdict']}",
        "",
        "## Summary",
        "",
        f"- Hold rate: {report['summary']['hold_rate']} ({report['summary']['hold_count']}/{report['n_queries']})",
        f"- Serper worse/empty/error: {report['summary']['serper_worse_count']}",
        f"- Avg latency Serper/Tavily: {report['summary']['avg_serper_latency_ms']}ms / {report['summary']['avg_tavily_latency_ms']}ms",
        "",
        "## Per-query",
        "",
        "| Category | Hold | Domain overlap | Flags | Query |",
        "| -- | -- | -- | -- | -- |",
    ]
    for q in report["queries"]:
        c = q["comparison"]
        lines.append(
            f"| {q['category']} | {'YES' if c['quality_hold'] else 'NO'} | {c['overlap_domain_count']} | "
            f"{', '.join(c['flags']) or '—'} | {q['query'][:80]} |"
        )
    if fails:
        lines += ["", "## Failures / review", ""]
        for q in fails:
            lines.append(f"- **{q['query']}** — flags={q['comparison']['flags']}")
            lines.append(f"  - Serper top: {q['comparison']['serper_top']}")
            lines.append(f"  - Tavily top: {q['comparison']['tavily_top']}")
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": report["verdict"], "summary": report["summary"]}, indent=2))
    print("wrote", out)
    return 0 if go else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
