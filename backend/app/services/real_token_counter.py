"""Real (not char/4-estimated) token counting for context-size audits.

Voice-latency Phase 0 (2026-09-05): every existing token-count field in this
codebase is either (a) a real provider-reported total (`usage.prompt_tokens`
— exact, but only a single number for the whole request, no per-source
breakdown) or (b) a `len(text)//4` heuristic (`estimate_tokens` in
conversation_context_service.py, model_router.py, rag/embedding.py —
adequate for cost estimation, not for an honest "what is actually driving the
p99 tail" audit). This module adds a third option: a real, offline tokenizer
(tiktoken, no API calls) so a per-source breakdown (system prompt / memory /
knowledge / tools / history) can be reported as real counts, cross-checked
against the real provider total rather than presented as independently
"real" with no ground truth.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# gpt-4o family (what MODEL_TIERS resolves voice/unified-turn calls to today)
# uses o200k_base; cl100k_base (gpt-3.5/gpt-4) is the safe fallback encoding
# tiktoken ships offline for any model name it doesn't recognize.
_DEFAULT_ENCODING_NAME = "o200k_base"


@lru_cache(maxsize=4)
def _get_encoding(encoding_name: str) -> Any | None:
    try:
        import tiktoken
    except Exception as exc:  # noqa: BLE001 — tiktoken not installed/importable
        logger.debug("real_token_counter_tiktoken_unavailable error=%s", exc)
        return None
    try:
        return tiktoken.get_encoding(encoding_name)
    except Exception as exc:  # noqa: BLE001
        logger.debug("real_token_counter_encoding_load_failed name=%s error=%s", encoding_name, exc)
        return None


def count_real_tokens(text: str, *, model: str | None = None) -> int:
    """Real tiktoken count for `text`. Falls back to the existing len//4
    heuristic (never raises) only if tiktoken itself is unavailable — the
    fallback is clearly a different code path, not silently blended in, so
    callers can tell which number they got via `real_token_counting_available()`.
    """
    if not text:
        return 0
    encoding_name = _DEFAULT_ENCODING_NAME
    if model:
        try:
            import tiktoken

            encoding_name = tiktoken.encoding_for_model(model).name
        except Exception:  # noqa: BLE001
            encoding_name = _DEFAULT_ENCODING_NAME
    enc = _get_encoding(encoding_name)
    if enc is None:
        return max(1, len(text) // 4)
    try:
        return len(enc.encode(text, disallowed_special=()))
    except Exception as exc:  # noqa: BLE001
        logger.debug("real_token_counter_encode_failed error=%s", exc)
        return max(1, len(text) // 4)


def real_token_counting_available() -> bool:
    return _get_encoding(_DEFAULT_ENCODING_NAME) is not None
