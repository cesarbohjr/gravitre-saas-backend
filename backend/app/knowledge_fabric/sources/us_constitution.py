"""U.S. Constitution excerpts — license type A (U.S. government / public domain)."""
from __future__ import annotations

from typing import Any

_ARTICLES = [
    {
        "id": "article-i-commerce",
        "title": "U.S. Constitution — Article I, Section 8 (Commerce / Laws)",
        "text": (
            "The Congress shall have Power To lay and collect Taxes, Duties, Imposts and Excises, "
            "to pay the Debts and provide for the common Defence and general Welfare of the United "
            "States; but all Duties, Imposts and Excises shall be uniform throughout the United "
            "States; … To regulate Commerce with foreign Nations, and among the several States, "
            "and with the Indian Tribes; … To make all Laws which shall be necessary and proper "
            "for carrying into Execution the foregoing Powers, and all other Powers vested by this "
            "Constitution in the Government of the United States, or in any Department or Officer thereof."
        ),
    },
    {
        "id": "amendment-xiv",
        "title": "U.S. Constitution — 14th Amendment, Section 1",
        "text": (
            "All persons born or naturalized in the United States, and subject to the jurisdiction "
            "thereof, are citizens of the United States and of the State wherein they reside. No "
            "State shall make or enforce any law which shall abridge the privileges or immunities "
            "of citizens of the United States; nor shall any State deprive any person of life, "
            "liberty, or property, without due process of law; nor deny to any person within its "
            "jurisdiction the equal protection of the laws."
        ),
    },
    {
        "id": "amendment-x",
        "title": "U.S. Constitution — 10th Amendment",
        "text": (
            "The powers not delegated to the United States by the Constitution, nor prohibited by "
            "it to the States, are reserved to the States respectively, or to the people."
        ),
    },
]


async def fetch_constitution_documents(*, limit: int = 3) -> list[dict[str, Any]]:
    docs = []
    for art in _ARTICLES[:limit]:
        docs.append(
            {
                "external_id": f"us-constitution-{art['id']}",
                "title": art["title"],
                "content": (
                    f"{art['text']}\n\nSource: U.S. National Archives — Constitution of the United States "
                    "(https://www.archives.gov/founding-docs/constitution-transcript)."
                ),
                "citation": "U.S. Constitution — https://www.archives.gov/founding-docs/constitution-transcript",
                "jurisdiction": "US-federal",
                "topics": ["constitution", "federal_law"],
                "effective_at": "1789-03-04T00:00:00Z",
                "metadata": {"license_type": "A"},
            }
        )
    return docs
