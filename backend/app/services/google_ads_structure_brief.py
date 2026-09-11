"""Parse a Google Ads campaign brief into structure.create args.

The chat schema extractor treated the apostrophe in "don't execute" as a
quoted title, so approval plans staged ``name="t execute anything…"`` instead
of the four named campaigns. This parser is shared by typed chat, spoken
chat, and native voice — same args, same campaign-by-campaign confirm copy.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.parameter_ledger import quoted_strings

_CAMPAIGN_SPLIT = re.compile(r"(?m)^\s*\d+[.)]\s+")
_CAMPAIGN_SECTION_START = re.compile(
    r"(?is)create\s+(?:four|4|\d+)\s+campaigns:?\s*"
)
_CAMPAIGN_SECTION_END = re.compile(
    r"(?im)^(?:account[- ]wide|before you create|set up\s+\")",
)
_NAME_WEIGHT = re.compile(
    r"^\s*(.+?)\s*[—–-]\s*(\d+(?:\.\d+)?)\s*%\s*budget",
    re.I | re.S,
)
_AD_GROUP_TYPED = re.compile(
    r'"([^"]{1,120})"\s*\(\s*([^:)]+?)\s*:\s*([^)]+?)\)',
)
_NEGATIVES = re.compile(
    r"negative keywords[^:\n]{0,80}:\s*(.+?)(?:\.|$)",
    re.I,
)
_CONVERSIONS_PAIR = re.compile(
    r"set up\s+(.+?)\s+as\s+two\s+separate",
    re.I | re.S,
)
_DAILY_BUDGET = re.compile(
    r"(?:"
    r"\$\s*(\d+(?:\.\d+)?)\s*(?:usd|dollars?)?(?:\s*(?:per|/)\s*day)?"
    r"|"
    r"(\d+(?:\.\d+)?)\s*(?:usd|dollars)\s*(?:per\s+day|daily|/day)"
    r"|"
    r"(?:daily budget|total daily budget)\s*(?:of|:)?\s*\$?\s*(\d+(?:\.\d+)?)"
    r")",
    re.I,
)
_NO_BROAD = re.compile(r"\bno broad match\b", re.I)


def parse_daily_budget_total(message: str) -> float | None:
    """Return a stated USD daily budget, or None. Never invent a dollar amount."""
    match = _DAILY_BUDGET.search(message or "")
    if not match:
        return None
    raw = next((g for g in match.groups() if g), None)
    if raw is None:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    if value <= 0:
        return None
    return value


def extract_google_ads_structure_args(message: str) -> dict[str, Any] | None:
    """Map a multi-campaign Ads brief onto googleads.structure.create params."""
    from app.services.chat_action_mapper import GOOGLE_ADS_STRUCTURE_INTENT

    text = (message or "").strip()
    if not text or not GOOGLE_ADS_STRUCTURE_INTENT.search(text):
        return None
    campaigns = _parse_campaigns(text)
    if not campaigns:
        return None
    args: dict[str, Any] = {
        "campaigns": campaigns,
        "status": "PAUSED",
    }
    negatives = _parse_negatives(text)
    if negatives:
        args["negative_keywords"] = negatives
    conversions = _parse_conversions(text)
    if conversions:
        args["conversion_actions"] = conversions
    budget = parse_daily_budget_total(text)
    if budget is not None:
        args["daily_budget_total"] = budget
    return args


def format_google_ads_structure_plan_details(args: dict[str, Any] | None) -> str:
    """User-visible campaign-by-campaign plan from staged structure.create args."""
    payload = args if isinstance(args, dict) else {}
    campaigns = payload.get("campaigns") or []
    if not isinstance(campaigns, list) or not campaigns:
        return ""
    lines = [
        "**Campaign-by-campaign plan** (created PAUSED; nothing spends until you enable it in Google Ads):",
        "",
    ]
    for idx, campaign in enumerate(campaigns, start=1):
        if not isinstance(campaign, dict):
            continue
        name = str(campaign.get("name") or f"Campaign {idx}").strip()
        weight = campaign.get("budget_weight")
        weight_bit = ""
        if isinstance(weight, (int, float)) and weight > 0:
            lines_pct = int(round(float(weight) * 100))
            weight_bit = f" — {lines_pct}% of daily budget"
        bidding = str(campaign.get("bidding_strategy") or "").replace("_", " ").title()
        bidding_bit = f" · {bidding}" if bidding else ""
        lines.append(f"{idx}. **{name}**{weight_bit}{bidding_bit}")
        for group in campaign.get("ad_groups") or []:
            if not isinstance(group, dict):
                continue
            ag_name = str(group.get("name") or "").strip()
            if not ag_name:
                continue
            kw_bits: list[str] = []
            for kw in group.get("keywords") or []:
                if isinstance(kw, dict) and kw.get("text"):
                    mt = str(kw.get("match_type") or "PHRASE").lower()
                    kw_bits.append(f"{kw['text']} ({mt})")
                elif isinstance(kw, str) and kw.strip():
                    kw_bits.append(kw.strip())
            extra = f" — {'; '.join(kw_bits[:12])}" if kw_bits else ""
            lines.append(f"   - Ad group **{ag_name}**{extra}")
    negatives = payload.get("negative_keywords") or []
    if isinstance(negatives, list) and negatives:
        lines.append("")
        lines.append("Account-wide negatives: " + ", ".join(str(x) for x in negatives))
    conversions = payload.get("conversion_actions") or []
    if isinstance(conversions, list) and conversions:
        names = [
            str(item.get("name")).strip()
            for item in conversions
            if isinstance(item, dict) and str(item.get("name") or "").strip()
        ]
        if names:
            lines.append("Conversion actions: " + "; ".join(names))
    lines.append("")
    if payload.get("daily_budget_total") is None:
        lines.append(
            "Total daily budget is not in the brief. Reply with a USD daily amount "
            "(include `$` and `/day`) before I can create this — I will not invent one."
        )
    else:
        lines.append(f"Total daily budget: ${payload['daily_budget_total']}")
    return "\n".join(lines)


def ads_structure_missing_daily_budget(args: dict[str, Any] | None) -> bool:
    payload = args if isinstance(args, dict) else {}
    campaigns = payload.get("campaigns")
    if not isinstance(campaigns, list) or not campaigns:
        return False
    return payload.get("daily_budget_total") is None


def _parse_campaigns(text: str) -> list[dict[str, Any]]:
    forbid_broad = bool(_NO_BROAD.search(text))
    body = text
    start = _CAMPAIGN_SECTION_START.search(text)
    if start:
        body = text[start.end() :]
    end = _CAMPAIGN_SECTION_END.search(body)
    if end:
        body = body[: end.start()]
    chunks = [part.strip() for part in _CAMPAIGN_SPLIT.split(body) if part.strip()]
    campaigns: list[dict[str, Any]] = []
    for chunk in chunks:
        parsed = _parse_one_campaign(chunk, forbid_broad=forbid_broad)
        if parsed:
            campaigns.append(parsed)
    return campaigns


def _parse_one_campaign(block: str, *, forbid_broad: bool) -> dict[str, Any] | None:
    named = _NAME_WEIGHT.search(block)
    if named:
        name = re.sub(r"\s+", " ", named.group(1)).strip(" .")
        weight = float(named.group(2)) / 100.0
    else:
        first_line = re.split(r"[.\n]", block, maxsplit=1)[0].strip()
        name = first_line[:80] if first_line else ""
        weight = None
    if not name or name.lower().startswith("t execute"):
        return None
    campaign: dict[str, Any] = {"name": name[:200]}
    if weight is not None and weight > 0:
        campaign["budget_weight"] = weight
    campaign["bidding_strategy"] = _bidding_strategy(block)
    ad_groups = _parse_ad_groups(block, forbid_broad=forbid_broad)
    if ad_groups:
        campaign["ad_groups"] = ad_groups
    return campaign


def _bidding_strategy(block: str) -> str:
    if re.search(r"target\s+cpa", block, re.I):
        return "TARGET_CPA"
    if re.search(r"maximize\s+conversion\s+value", block, re.I):
        return "MAXIMIZE_CONVERSION_VALUE"
    if re.search(r"maximize\s+conversions", block, re.I):
        return "MAXIMIZE_CONVERSIONS"
    return "MAXIMIZE_CONVERSIONS"


def _match_type(hint: str, forbid_broad: bool) -> str:
    lowered = (hint or "").lower()
    if "exact" in lowered and "phrase" not in lowered and "broad" not in lowered:
        return "EXACT"
    if "broad" in lowered and not forbid_broad:
        return "BROAD"
    return "PHRASE"


def _parse_ad_groups(block: str, *, forbid_broad: bool) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for match in _AD_GROUP_TYPED.finditer(block):
        name = match.group(1).strip()
        match_type = _match_type(match.group(2), forbid_broad)
        keywords = [
            {"text": part.strip(), "match_type": match_type}
            for part in match.group(3).split(",")
            if part.strip()
        ]
        if name:
            groups.append({"name": name, "keywords": keywords})
    if groups:
        return groups
    include = re.search(r"ad\s+groups?\s+include\s+(.+)", block, re.I | re.S)
    blob = include.group(1) if include else block
    for quote in quoted_strings(blob):
        if len(quote) < 3 or quote.lower().startswith("t execute"):
            continue
        groups.append(
            {
                "name": quote[:80],
                "keywords": [{"text": quote, "match_type": "PHRASE"}],
            }
        )
    return groups


def _parse_negatives(text: str) -> list[str]:
    match = _NEGATIVES.search(text)
    if not match:
        return []
    return [part.strip() for part in match.group(1).split(",") if part.strip()]


def _parse_conversions(text: str) -> list[dict[str, str]]:
    match = _CONVERSIONS_PAIR.search(text)
    if not match:
        return []
    names = quoted_strings(match.group(1))
    return [{"name": name} for name in names if name]
