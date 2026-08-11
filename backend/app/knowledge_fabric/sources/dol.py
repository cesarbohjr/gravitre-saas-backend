"""U.S. Department of Labor public developer / employment materials — license type B/A mix.

Uses DOL's public FLSA overview content that is U.S. government material.
O*NET Web Services remain held until ONET credentials are provisioned.
"""
from __future__ import annotations

from typing import Any

_FLSA = (
    "The Fair Labor Standards Act (FLSA) establishes minimum wage, overtime pay, "
    "recordkeeping, and youth employment standards affecting employees in the private "
    "sector and in Federal, State, and local governments. Covered nonexempt workers are "
    "entitled to a minimum wage. Overtime pay at a rate of not less than one and one-half "
    "times the regular rate of pay is required after 40 hours of work in a workweek. "
    "The FLSA does not require severance pay, sick leave, or holidays. "
    "Source: U.S. Department of Labor, Wage and Hour Division — "
    "https://www.dol.gov/agencies/whd/flsa"
)

_FMLA = (
    "The Family and Medical Leave Act (FMLA) provides certain employees with up to 12 weeks "
    "of unpaid, job-protected leave per year for qualifying family and medical reasons. "
    "It also requires that group health benefits be maintained during the leave. "
    "Eligible employees generally must have worked for a covered employer for at least "
    "12 months, have at least 1,250 hours of service, and work at a location with 50 or "
    "more employees within 75 miles. "
    "Source: U.S. Department of Labor — https://www.dol.gov/agencies/whd/fmla"
)


async def fetch_dol_documents(*, limit: int = 3) -> list[dict[str, Any]]:
    docs = [
        {
            "external_id": "dol-flsa-overview",
            "title": "DOL — Fair Labor Standards Act overview",
            "content": _FLSA,
            "citation": "U.S. DOL WHD FLSA — https://www.dol.gov/agencies/whd/flsa",
            "jurisdiction": "US-federal",
            "topics": ["labor", "wage_hour", "flsa"],
            "metadata": {"license_type": "A", "note": "U.S. government public material"},
        },
        {
            "external_id": "dol-fmla-overview",
            "title": "DOL — Family and Medical Leave Act overview",
            "content": _FMLA,
            "citation": "U.S. DOL WHD FMLA — https://www.dol.gov/agencies/whd/fmla",
            "jurisdiction": "US-federal",
            "topics": ["labor", "fmla", "leave"],
            "metadata": {"license_type": "A", "note": "U.S. government public material"},
        },
    ]
    return docs[:limit]
