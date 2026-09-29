"""Named external dataset-provider adapters.

Adapters are read-only unless a later, separately approved materialization
slice explicitly says otherwise.
"""

from app.training.providers.huggingface import HuggingFaceDatasetAdapter

__all__ = ["HuggingFaceDatasetAdapter"]
