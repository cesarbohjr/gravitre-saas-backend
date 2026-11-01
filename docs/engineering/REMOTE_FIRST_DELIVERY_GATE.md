# Remote-first engineering delivery gate

Applies to all Gravitre implementation work, including the Unified Agent Capability Manifest recovery.

## Before editing
1. Create a feature branch from the current remote `main` and verify the branch exists on GitHub.
2. Open a draft PR as soon as the first meaningful checkpoint is pushed.
3. Never rely on a temporary development workspace as the only copy of a change.

## During implementation
- Commit and push at each coherent checkpoint, before long test runs and before session termination.
- Verify the pushed SHA against the remote branch head; local commit success is not delivery.
- Do not commit credentials, tokens, customer records, or generated secrets.
- Keep unverified or incomplete work in a draft PR, not on production-linked `main`.

## Required delivery evidence
- Remote branch and commit SHA verified in GitHub.
- PR URL recorded, with changes and test evidence attached.
- Required backend, frontend, IAM, tenant-isolation, and security checks green for affected surfaces.
- PR review and branch protections satisfied before merge.
- Deployment and production smoke evidence recorded separately from CI.
- If any check is unavailable, explicitly mark the gate blocked; never report it as complete.

## Recovery protocol
When a local workspace or commit is missing, first search remote branches, PRs, and commits. Reconstruct only missing changes on a new remote branch. Compare against the current `main` and re-run tests; previous local test counts are historical evidence, not validation of the rebuilt implementation.

## Current workstream
Rebuild the Unified Agent Capability Manifest; wire agent selection, prompts, and capability profiles; preserve tenant IAM and approvals; add distinct Engineering, QA, and Security roles and pinned Agency Agents enrichment. Additional frameworks remain a separate follow-on milestone. Phase 1 live intelligence certification remains independently blocked until provider access and fixtures are restored.
