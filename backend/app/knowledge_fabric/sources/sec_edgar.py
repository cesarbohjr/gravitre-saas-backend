"""SEC EDGAR APIs — license type B (fair access; User-Agent required)."""
from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings, get_settings

COMPANY_TICKERS = "https://www.sec.gov/files/company_tickers.json"
# Apple CIK for a stable companyfacts sample
SAMPLE_CIK = "0000320193"
COMPANY_FACTS = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{SAMPLE_CIK}.json"


async def fetch_sec_edgar_documents(
    *,
    limit: int = 3,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    settings = settings or get_settings()
    ua = (
        getattr(settings, "sec_user_agent", None)
        or __import__("os").environ.get("SEC_USER_AGENT")
        or "GravitreKnowledgeFabric/1.0 (support@gravitre.ai)"
    )
    headers = {"User-Agent": ua, "Accept": "application/json"}
    docs: list[dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=45.0, headers=headers) as http:
        tickers_resp = await http.get(COMPANY_TICKERS)
        tickers_resp.raise_for_status()
        tickers = tickers_resp.json()
        sample_lines = []
        if isinstance(tickers, dict):
            for i, (_k, row) in enumerate(tickers.items()):
                if i >= min(limit, 5):
                    break
                if isinstance(row, dict):
                    sample_lines.append(
                        f"CIK={row.get('cik_str')} ticker={row.get('ticker')} title={row.get('title')}"
                    )
        docs.append(
            {
                "external_id": "sec-company-tickers-sample",
                "title": "SEC EDGAR company ticker directory (sample)",
                "content": (
                    "SEC EDGAR company_tickers.json provides CIK/ticker mappings used to resolve "
                    "corporate filings and XBRL company facts.\n\n" + "\n".join(sample_lines)
                ),
                "citation": "SEC EDGAR company_tickers.json — https://www.sec.gov/files/company_tickers.json",
                "jurisdiction": "US-federal",
                "topics": ["filings", "tickers"],
                "metadata": {"license_type": "B", "api": "sec.edgar"},
            }
        )

        facts_resp = await http.get(COMPANY_FACTS)
        if facts_resp.status_code == 200:
            facts = facts_resp.json()
            entity = facts.get("entityName") or "Apple Inc."
            us_gaap = (facts.get("facts") or {}).get("us-gaap") or {}
            keys = list(us_gaap.keys())[:8]
            lines = [f"Entity: {entity}", "Sample us-gaap concepts:"] + [f"- {k}" for k in keys]
            # Pull one numeric fact if present
            for concept in ("Assets", "NetIncomeLoss", "Revenues"):
                node = us_gaap.get(concept)
                if not isinstance(node, dict):
                    continue
                units = node.get("units") or {}
                usd = units.get("USD") or []
                if usd:
                    latest = usd[-1]
                    lines.append(
                        f"{concept}: {latest.get('val')} "
                        f"(fy={latest.get('fy')} form={latest.get('form')} filed={latest.get('filed')})"
                    )
                    break
            docs.append(
                {
                    "external_id": f"sec-companyfacts-{SAMPLE_CIK}",
                    "title": f"SEC XBRL company facts — {entity}",
                    "content": "\n".join(lines),
                    "citation": f"SEC companyfacts CIK{SAMPLE_CIK} — {COMPANY_FACTS}",
                    "jurisdiction": "US-federal",
                    "topics": ["xbrl", "corporate_disclosure"],
                    "metadata": {"license_type": "B", "cik": SAMPLE_CIK, "api": "sec.edgar"},
                }
            )

    return docs[:limit]
