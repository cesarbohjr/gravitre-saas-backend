# PR581 pinned source audit and Marketplace targets

Status: source census verified locally; package definitions remain review-only. No product-approved Agency Agents release list exists on this branch. No publication, installation, merge or deployment is performed.

Pinned upstream: `msitarzewski/agency-agents@b37b5bb33b78f2c1d6567d98e25ca818e3259219`. All 283 frontmatter profiles in all 18 declared divisions match the README inventory. Each profile records SHA-255 and MIT provenance. `strategy/` contains playbooks rather than a role division; generated integrations, examples and scripts are excluded.

Reproduce: `python scripts/audit-agency-agents.py /path/to/pinned-checkout --check`. The command verifies the revision, tracked-file cleanliness, license and complete declared-division census without executing upstream code. File verification is not a behavioral/security certification of upstream instructions; none of that text is imported into runtime prompts.

## Candidate destinations

These are review destinations, not approved functional substitutes. `map_marketplace_targets()` resolves every source role against existing repository seed assets and the four role manifests. It records exact function-overlap hints separately from division-level routing. Customer/tenant-installed and live published rows are not available to this offline comparison.

| Division | Profiles | Gravitre department | Existing pack candidate | Manifest candidate |
|---|---:|---|---|---|
| academic | 6 | Research | None | agency |
| design | 10 | Marketing | marketing-operations-pack | None |
| engineering | 66 | Engineering | None | engineering |
| finance | 5 | Finance | None | None |
| game-development | 21 | Engineering | None | engineering |
| gis | 13 | Research | None | agency |
| healthcare | 3 | Research | None | agency |
| marketing | 37 | Marketing | marketing-operations-pack | None |
| paid-media | 7 | Marketing | marketing-operations-pack | None |
| product | 6 | Marketing | marketing-operations-pack | None |
| project-management | 7 | Operations | msp-operations-pack | agency |
| research | 1 | Research | None | agency |
| sales | 9 | Sales | revenue-operations-pack | None |
| security | 12 | Security | None | security |
| spatial-computing | 6 | Engineering | None | engineering |
| specialized | 59 | Operations | None | agency |
| support | 6 | Support | support-operations-pack | None |
| testing | 9 | QA | None | qa |

No absent pack is silently created. Specialized, GIS, healthcare and other niche profiles still need individual target/connector/entitlement review. Function collisions such as SEO Specialist → `seo-analyst`, Content Creator → `content-writer`, and Pipeline Analyst → `revenue-operations-agent` are flagged for enrichment review, not automatic duplicate installation.

## Package implementation boundary

The 255 Marketplace previews now construct valid `AgentAssetConfig` payloads using the canonical seed/name/role/department/config shape and `ai_agent` category. No arbitrary upstream slug becomes a runtime persona. Capabilities and connector systems are empty: role descriptions confer no tool rights. Provenance and candidate mappings survive schema validation inside nested config. The normal seed service rejects these previews before any DB call. They remain disconnected from `list_catalog_assets()` and customer routes. No customer-visible price, claim or toggle is added.

An approved SKU list, reviewed bounded role guidance, connector prerequisites, entitlement/pricing decisions and live collision resolution are still required before publish/install/version/rollback acceptance can honestly be claimed. Shared routing/personality/dialogue/voice changes remain outside this catalog checkpoint and belong to PR587.

## Validation

Executed locally against the committed implementation files:
- Source audit `--check`: verified all 283 pinned profiles and MIT license/hash reproduction.
- `python -m pytest tests/marketplace/ -q`: **561 passed** (includes 19 Agency Agents contracts).
- Manifest/routing/seven-intelligence-envelope/tenant-isolation contracts: **19 passed**.
- Org-role/tool-permission/canvas-write-approval/fingerprint contracts: **31 passed**.
- Web `vitest run` in UTC: **311 files / 1,958 tests passed**. The first run under ambient Melbourne timezone had one recency-bucketing failure; unchanged tests passed under CI’s UTC timezone.
- Web ESLint, TypeScript and production build: completed successfully. No deployment command was run.
- Confidence-honesty and smoke-harness static checks: passed.

Full local backend regression is **BLOCKED**: automatic approval review rejected provider-facing agent-streaming execution because test-derived payloads might be sent to OpenAI using an API key without separately authorized external disclosure. The full regression was not completed and is not reported as passed. No safety gate or test assertion was weakened.

Main CI remains pending behind an older serialized run; use PR581’s checks for the exact latest SHA. Passing supporting workflows and local checks do not certify full CI. Vercel returned no deployments for the first checkpoint, and both project roots explicitly disable automatic deployment for this feature branch. PR581 stays open/draft; no merge or deployment.
