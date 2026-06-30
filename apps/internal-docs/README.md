# Gravitre internal docs (private)

Password-protected Next.js site for engineering documentation in `docs/internal/`.

## Local development

```powershell
cd apps/internal-docs
pnpm install
$env:INTERNAL_DOCS_PASSWORD = "your-dev-password"
pnpm dev
```

Open http://localhost:3001 — browser prompts for Basic auth (any username, password = `INTERNAL_DOCS_PASSWORD`).

## Deploy

Deploy as a separate Vercel project (or Railway service):

1. Root directory: `apps/internal-docs`
2. Set `INTERNAL_DOCS_PASSWORD` (or replace middleware with SSO later)
3. Disable indexing — layout sets `robots: noindex`

Do not deploy from the public `apps/web` project.
