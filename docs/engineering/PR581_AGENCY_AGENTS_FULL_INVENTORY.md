# PR #581 — Full Agency Agents division inventory and staged Marketplace mapping

**Status: inventory and review-only adapter implemented; packages not approved, published, installed or live-tested.** Upstream pinned at [b37b5bb](https://github.com/msitarzewski/agency-agents/commit/b37b5bb33b78f2c1d6567d98e25ca818e3259219).

## Coverage
The upstream README at the pinned revision yields **283 linked role entries across all 18 divisions**. This is a README-linked roster inventory, **not a filesystem audit of every upstream Markdown file**. Counts:

| Division | Entries |
|---|---:|
| Academic | 6 |
| Design | 10 |
| Engineering | 66 |
| Finance | 5 |
| Game Development | 21 |
| GIS | 13 |
| Healthcare | 3 |
| Marketing | 37 |
| Paid Media | 7 |
| Product | 6 |
| Project Management | 7 |
| Research | 1 |
| Sales | 9 |
| Security | 12 |
| Spatial Computing | 6 |
| Specialized | 59 |
| Support | 6 |
| Testing | 9 |

The 283 proposed classifications are **27 enrich-existing default capabilities** and **256 Marketplace candidates**. Neither category constitutes product approval. No role is given new execution rights; high-risk finance, security and healthcare divisions are marked for governance review.

## Artifacts
- `backend/app/marketplace/agency_agents_inventory.json`: source path, source URL pinned to immutable upstream revision, division, title, specialty, proposed disposition, governance flag, publication status, candidate Marketplace slug.
- `backend/app/marketplace/agency_agents_catalog.py`: read-only loader with fail-closed schema/provenance/duplicate checks, preview adapter using the **existing** `CatalogAsset` schema. Not connected to the production seed catalog or publication API.
- `backend/tests/marketplace/test_agency_agents_catalog.py`: division coverage, preview and rejection tests.

## Critical boundaries
PR #581 owns role/Marketplace packaging and catalog review. PR #587 owns One Brain, shared intelligence, personality, memory, dialogue and voice. Agency role text is untrusted configuration, never system-level policy or an IAM grant.

Existing Gravitre `marketplace_assets` remains the canonical install/entitlement/rollback mechanism. Do not create a parallel Marketplace or bypass existing tenant isolation. This inventory's collision hints are **not** a complete comparison with live Marketplace rows, installed operators or every existing seed asset; reconcile those before publication.

## Remaining blocking work
1. Audit actual upstream source files and license at pinned commit; verify each README link and frontmatter. Inventory any unlisted upstream files.
2. Compare normalized functions against the complete current Gravitre Marketplace, operators, department packs, installed assets and existing slugs. Resolve collisions and default shortlist with product approval.
3. Create reviewed package definitions with bounded role prompts, explicit connector prerequisites, pricing/entitlements and permission-safe workflows. Use existing install/upgrade/rollback and public listing flows.
4. Add tenant isolation, cross-tenant denial, connector readiness, entitlement, idempotent install, rollback and prompt-injection regressions. Run full PR CI and resolve all failures.
5. Remove or reconcile overlapping #581 intelligence/router changes with #587. **No merge until final branch CI and conflict review are green.**
6. Live testing remains last, after authorized deployment to main. No extra Railway evaluation service.

**Evidence distinction:** GitHub commits establish that catalog inventory and offline contracts exist, not that those tests have run or passed, nor that 256 packages are published.
