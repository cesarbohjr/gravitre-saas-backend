"""Organization-level bounded contributions and durable privacy expenditure."""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
from pathlib import Path
from typing import Any

import numpy as np



def runtime_settings():
    # Deliberately independent of main API Settings, which requires database
    # service credentials. Flower processes must never receive those keys.
    from types import SimpleNamespace
    names = ('federated_audit_public_key','federated_audit_manifest',
             'federated_node_registry_file','federated_consent_service_url',
             'federated_consent_service_secret')
    return SimpleNamespace(**{name:os.environ.get(name.upper(),'') for name in names})


def data_root() -> Path:
    root = Path(os.environ.get("FEDERATED_RUNTIME_DATA_DIR", "/data"))
    if not root.is_absolute():
        raise ValueError("Durable absolute runtime data directory required")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root


def feature_schema_digest() -> str:
    from app.ml.learning_to_rank import FEATURE_NAMES
    return hashlib.sha256(json.dumps([*FEATURE_NAMES, "intercept"], separators=(",", ":")).encode()).hexdigest()


def current_permission(org_id: str, settings: Any, audit_digest: str) -> None:
    # This credential can read approval booleans only. No registry/database/
    # artifact credentials are supplied to the aggregation runtime or nodes.
    import httpx
    from urllib.parse import urlparse, quote
    url = settings.federated_consent_service_url
    secret = settings.federated_consent_service_secret
    parsed = urlparse(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or len(secret) < 32:
        raise ValueError('Configured HTTPS consent-only service required')
    with httpx.Client(timeout=15,follow_redirects=False) as client:
        response = client.get(url.rstrip('/')+'/'+quote(org_id,safe=''),headers={'Authorization':'Bearer '+secret})
        response.raise_for_status()
        record = response.json()
    if (record.get('org_id') != org_id or record.get('audit_digest') != audit_digest
            or record.get('approved') is not True or record.get('ranker_approved') is not True):
        raise ValueError('Current tenant permissions for this audited program required')


def reserve_privacy_release(org_id: str, round_id: str, profile: dict[str, Any], audit_digest: str) -> None:
    if not re.fullmatch(r"[a-f0-9]{64}", round_id):
        raise ValueError("Immutable federation round identity required")
    # One database per tenant process/volume, scoped again by tenant/program.
    # Reserve before releasing anything, and retain failed-round expenditure.
    with sqlite3.connect(data_root()/"privacy.sqlite", timeout=30) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE IF NOT EXISTS releases (org TEXT, program TEXT, round TEXT, audit TEXT, noise REAL, PRIMARY KEY(org, program, round))")
        db.execute("BEGIN IMMEDIATE")
        history = db.execute("SELECT round,audit,noise FROM releases WHERE org=? AND program=?", (org_id, profile["program_id"])).fetchall()
        if any(row[0] == round_id for row in history):
            raise ValueError("Tenant contribution already reserved; do not release a second independent sample")
        if any(row[1] != audit_digest for row in history) or len(history) >= profile["max_rounds"]:
            raise ValueError("Privacy program changed or release count exhausted")
        from opacus.accountants import RDPAccountant
        accountant = RDPAccountant()
        for noise in [*[row[2] for row in history], profile["noise_multiplier"]]:
            accountant.step(noise_multiplier=noise, sample_rate=1.0)
        if accountant.get_epsilon(delta=profile["delta"]) > profile["max_epsilon"]:
            raise ValueError("Composed tenant privacy budget exhausted")
        db.execute("INSERT INTO releases VALUES (?,?,?,?,?)", (org_id,profile["program_id"],round_id,audit_digest,profile["noise_multiplier"]))


def private_contribution(vector: np.ndarray, profile: dict[str, Any]) -> np.ndarray:
    """Clip one whole organization's vector, then add independent Gaussian noise.

    Replace-one adjacency has sensitivity 2*C, not C. The Google DP sampler
    supplies noise; no deterministic seed or hand-written Gaussian sampler.
    Flower's subsequent quantization/clipping is post-processing of this output.
    """
    from pydp.distributions import GaussianDistribution
    vector = np.asarray(vector, dtype=np.float64)
    if vector.shape != (5,) or not np.isfinite(vector).all():
        raise ValueError("Five finite canonical retrieval parameters required")
    norm = math.hypot(*vector.tolist())
    clipped = vector * min(1.0, profile["clipping_norm"]/norm) if norm else vector.copy()
    sigma = 2 * profile["clipping_norm"] * profile["noise_multiplier"]
    sampler = GaussianDistribution(sigma)
    if not np.isclose(sampler.stddev, sigma):
        raise ValueError("Noise backend does not match the audited standard deviation")
    result = clipped + np.asarray([sampler.sample() for _ in range(5)])
    if not np.isfinite(result).all():
        raise ValueError("Noise backend returned nonfinite parameters")
    return result
