-- SA-00: Enable required extensions
-- pgvector required for Phase 1 RAG (BE-10) embeddings
CREATE EXTENSION IF NOT EXISTS vector;
