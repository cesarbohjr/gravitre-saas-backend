"""BE-10: OpenAI embedding client. Single model per deployment; no query text logged."""
from openai import OpenAI

from app.config import Settings


def get_embedding(text: str, settings: Settings) -> list[float]:
    """Return embedding vector for text. Raises on API/key failure."""
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY not configured")
    client = OpenAI(api_key=settings.openai_api_key)
    resp = client.embeddings.create(
        model=settings.openai_embedding_model,
        input=text,
    )
    return resp.data[0].embedding
