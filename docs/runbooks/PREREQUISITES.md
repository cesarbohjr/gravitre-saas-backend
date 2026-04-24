# Preview Prerequisites

## Runtime versions
- Python 3.11+ (`python --version`)
- Node.js 20+ (`node --version`)

## Package manager (pnpm)
- Install pnpm via Corepack:
  - `corepack enable`
  - `corepack prepare pnpm@latest --activate`
  - `pnpm --version`

## Docker (for local Supabase)
- Install Docker Desktop and ensure the daemon is running.

## Supabase CLI
- Install: `npm install -g supabase`
- Verify: `supabase --version`

## Optional: local Supabase
- From repo root: `cd supabase` then `supabase start`
