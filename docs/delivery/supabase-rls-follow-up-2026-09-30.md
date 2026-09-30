# Supabase RLS follow-up (not voice acceptance)

Recorded: 2026-09-30  
Project: `smyeexlrqdpymwjmgzqu` (active healthy production)

## Finding

`pg_class.relrowsecurity` is **false** on:

- `public.agent_custom_voices`
- `public.billing_topup_events`

`audit_logs` and `audit_events` are RLS-enabled on the same project.

## Disposition

- **Not changed.** Enabling RLS without named policies can break access.
- **Not a voice physical-acceptance blocker** unless a Talk turn produces
  evidence that these tables are on the live output path.
- Separate security workstream. Do not fold into voice, Plays, or Lighthouse.

## Required owner choice (later)

1. Leave RLS off
2. Enable RLS with specified policies
3. Enable deny-all until policies exist (can break access)
