# PR #605 merge readiness follow-up — 2026-11-07 UTC

## Main synchronization

The incoming main tip is `2e78e03a58e29e03019687b03ad90fd6ad420e84` (#609).
A real three-way merge into `d0e1e81f492aceba6e201675485bcb6b3fb56114` is conflict-free.
The three incoming paths are Plays page.tsx, dashboard.css and automate-v1.css.
Keep both histories, all billing safety fixes and incoming provider-logo changes.
The resulting head needs fresh full CI, specialized gates and isolated billing.
Previous-head certification cannot certify the resulting merge commit.

## Dependency findings and decision boundary

The full web audit reports 120 findings: 46 high, 64 moderate, 10 low, zero critical.
Backend and SDK-worker pip audits passed. CI intentionally fails on critical web
findings; reporting highs is not a clean bill of health. No threshold or exclusions
were changed. The machine-readable companion `pr605-high-dependency-triage.json`
records **all 46** high advisories, vulnerable/patched versions, exact paths and
static reachability dispositions.

| Dependency family | Current reachability evidence | Disposition |
| --- | --- | --- |
| ESLint, shadcn/MCP, Express/body-parser, fast-uri, globbing, Vite, Hono, ip-address | All reported chains begin with devDependencies; CLI/server facilities are not exposed as application routes | Development/build maintenance debt; never run scaffolding/MCP servers on production credentials |
| PostCSS, nanoid, browserslist, source-map-js | Build/configuration processing; repository CSS and source-map inputs; no direct application runtime parser imports | Build-input trust boundary, not a demonstrated remote production endpoint |
| js-yaml via gray-matter | `apps/web/lib/docs/load-docs.ts` reads repository `content/docs/public` files | Trusted repository document boundary; do not extend to uploads without patching |
| sharp via Next | `apps/web/next.config.mjs` sets `images.unoptimized: true`; no direct sharp imports | Image optimization/decoding path disabled; re-evaluate before enabling it |
| follow-redirects via Nango/axios | Nango is dynamically imported by browser managed connector auth; no application Node/cross-realm sensitiveHeaders caller found | Advisory-specific prerequisites not identified; retain finding |
| Zod via app and AI SDK | Only direct application schema is scalar route-intent model output; no array/set/map schema; SDK internal schemas not fully traced | No exposed direct collection-validation path found; independent review remains required for SDK transitive use |

This completes the requested reachability inventory, not vulnerability remediation
or independent security approval. No exploit was run against production. The
reviewer must consider the documented SDK uncertainty; do not call the app
vulnerability-free or silently waive findings. Patched versions and primary
advisory links are retained in the JSON inventory for targeted follow-up.

## Deployment control readback

Railway production backend remains deployment `78fb8af7-2c90-4a4f-9a34-180398ad20fb`,
SUCCESS, 1/1 online, with repository/root intact and no source branch trigger.
Redis remains `55511e94-d758-42bb-8791-ea8c4ffc16c4`, SUCCESS, 1/1 online.
No staged work, volumes, paid feature or tracing change was introduced.
Both Vercel projects retain Deployment Sources override for **Production**, Git
unchecked; previews remain outside the rule. `Railway backend production` remains
manually disabled. Four alternate deployment workflows are manual-dispatch only:
auth-config-sync, milestone2-latency-ab, unified-turn-phase2-live and phase4-cutover.
Do not dispatch them during the hold.

The hold is on automatic Git deployment. CLI, REST API, v0, hooks and marketplace
sources remain allowed by the original narrow Vercel rule; authorized manual
operators can bypass it. This is not a universal deployment freeze. Vercel A's
observed #609 production deployment `dpl_9UPDqCidmuCKYjLjXSGVuYxmFz9S` was
created via **Claude.ai**, confirmed by Vercel event
`uev_2WekNAajPBuJJ3MnkH6qRh6k` at 2026-11-07T03:03:26 UTC. The
`via` app identity is `Claude.ai`, and the target is production on SHA `2e78e03`
(the event is not evidence of an automatic Git-provider deployment). Alias event
`uev_f3il03rk8IggNrGUhimighI1` confirms assignment of the current production
aliases. The historical baseline change is thus reconciled to an external app
deployment path. Do not undo/redeploy it or revoke access without authorization.
Restoration after separate production approval remains the original PR comment
6691107339: re-enable original Railway source branch autodeploy, re-check Git in
each Production rule (or remove only the temporary rule), then enable the GitHub
Railway workflow. Restore only deliberately, after final approved release SHA.

## Human review and production boundary

One independent approval, stale dismissal, last-push approval, resolved threads,
strict five required checks and admin enforcement remain required. No bypasses,
force pushes or deletion. The PR author cannot approve their own PR. Creating a
review or access grant on their behalf is not an independent review.
Production deployment, migrations, telemetry, data reconciliation and Tranche 27
P27-01–08 acceptance remain **NOT RUN / NOT AUTHORIZED** in this work.
