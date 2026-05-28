"""BE-10: OpenAI embedding client. Single model per deployment; no query text logged."""
from openai import OpenAI

from app.config import Settings

# Per-request timeout (seconds) so a hung connection can't block ingestion/query.
EMBEDDING_REQUEST_TIMEOUT_S = 30.0


def get_embedding(text: str, settings: Settings) -> list[float]:
    """Return embedding vector for text. Raises on API/key failure."""
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY not configured")
    client = OpenAI(
        api_key=settings.openai_api_key,
        timeout=EMBEDDING_REQUEST_TIMEOUT_S,
        max_retries=2,
    )
    resp = client.embeddings.create(
        model=settings.embedding_model,
        input=text,
    )
    return resp.data[0].embedding
