"""Named external dataset-provider adapters.

Adapters are read-only unless a later, separately approved materialization
slice explicitly says otherwise.
"""
from __future__ import annotations

from app.training.dataset_provider import DatasetProviderAdapter
from app.training.providers.huggingface import HuggingFaceDatasetAdapter


def get_dataset_provider_adapter(provider: str) -> DatasetProviderAdapter:
    key = str(provider or "").strip().lower().replace("-", "_")
    if key in {"huggingface", "hugging_face", "hf"}:
        # Public Dataset Viewer access only for this first slice. Private/gated
        # access requires a separately configured runtime credential path.
        return HuggingFaceDatasetAdapter()
    raise LookupError(f"unsupported dataset provider: {provider}")


__all__ = ["HuggingFaceDatasetAdapter", "get_dataset_provider_adapter"]
