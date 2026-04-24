# Secrets Rotation Plan

## Risk identified
- A single long-lived encryption key is a single point of compromise.
- No safe process exists to rotate `CONNECTOR_SECRETS_ENCRYPTION_KEY`.

## Current state
- One Fernet key used for both encrypt and decrypt.
- No key identifiers stored with secrets.

## Recommended fix
- Introduce dual-key decrypt support (primary + secondary).
- Store a `key_id` with each encrypted secret (future schema change).
- Provide a safe rotation runbook with staged re-encryption.

## Implementation details
- Design only (no crypto changes yet).
- Proposed env:
  - `CONNECTOR_SECRETS_PRIMARY_KEY`
  - `CONNECTOR_SECRETS_SECONDARY_KEY` (decrypt-only)
- Rotation steps (outline):
  1. Add secondary key (old key) and promote new primary.
  2. Re-encrypt secrets with new primary.
  3. Remove secondary after verification.

## Future scaling notes
- Move to KMS-backed envelope encryption.
- Add per-secret key IDs and automated rotation jobs.
