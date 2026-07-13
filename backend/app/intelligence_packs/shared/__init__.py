"""Shared intelligence-pack infrastructure (Phase 1 + 1.5).

Phase 1.5 shared surfaces (point-to test):
- durable_cache.cache_get / cache_set
- normalize.normalize_source_result
- provenance.write_external_entity_with_provenance
- signals.register_signal / evaluate_pack_signals
"""
from app.intelligence_packs.shared.pipeline import ensure_plumbing_registered

ensure_plumbing_registered()
