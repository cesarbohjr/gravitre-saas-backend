"""Platform knowledge fabric — shared expert packs, separate from org RAG."""

from app.knowledge_fabric.registry import PLATFORM_KNOWLEDGE_SOURCES, list_platform_packs

__all__ = ["PLATFORM_KNOWLEDGE_SOURCES", "list_platform_packs"]
