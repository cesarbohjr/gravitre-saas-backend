# Gravitre: shared AI development and production release instructions

Applies to Claude, Cursor, ChatGPT, and all agents modifying `cesarbohjr/gravitre-saas-backend`.

## Source of truth and access
- GitHub `main` is the authoritative source. Work only on a branch created from current `main`; publish a pull request.
- A GitHub connector with API write access is not the same as a Git terminal. If `git push` returns HTTP 403, check the credentials for *that process*. If DNS resolution fails, change execution environment; do not claim repository permissions are missing.
- Never claim an unpushed local commit is available to other agents. Provide a real GitHub branch/PR or a verified patch artifact.
- Do not bypass CI, protected-branch rules, or deployment checks. A successful commit or PR is not proof of a production release.

## Supabase production
- Production project: `smyeexlrqdpymwjmgzqu`. Verify the project ID before any operation; never redirect an AI agent to a different project by guesswork.
- Never run schema-changing SQL, `supabase db push`, migration repair, reset, or production backfills from an AI development session without explicit approval for the exact migration.
- Create migrations using the versioned files under `supabase/migrations/`; never edit previously applied migrations. Match local migration versions against the remote migration history before proposing a deployment.
- Validate SQL and migration history in an isolated disposable database or staging project; never use production as the test database.
- Check tenant isolation/RLS, role grants, policies, functions marked SECURITY DEFINER, dependency ordering, lock impact, and whether a change is destructive or needs a staged backfill.
- A single approved deployment actor should apply migrations, using protected credentials and a concurrency lock. Do not use multiple Claude/Cursor/ChatGPT sessions as parallel migration executors.
- Use an expand/migrate/contract rollout: first deploy backward-compatible schema, then compatible backend and frontend, then clean up old fields in a separate approved release.
- Never put Supabase access tokens, production DB passwords, or service-role keys in committed files, command output, PR comments, logs, or client environment variables. Store deployment secrets in protected GitHub environment secrets with reviewers.
- GitHub Actions migration deployment should remain **disabled until** staging tests, history reconciliation, a backup/recovery plan, protected `production` environment, and required secrets have been configured and verified. Don't invent an automatic production migration job as a shortcut.

## Release verification
- Existing `.github/workflows/ci.yml` runs web/backend checks. The existing Railway production workflow handles backend deployment; Vercel is GitHub-connected for the web.
- Before merge: get required checks green, review migrations and code changes, and resolve conflicts. Stop on failures; don't declare a false PASS.
- After merge: verify production web availability, backend `/health` reported commit, and applicable Railway/Vercel deployment status. Track each branch individually.
- A 403 means authentication/authorization *for that actor*; a DNS error means network reachability; a SQL error may be privileges, state drift, or invalid SQL. Diagnose by evidence instead of retrying writes.
- For any blocked step, report the exact branch, SHA, stage, and verified blocker. Do not say deployed unless actual production state confirms it.
