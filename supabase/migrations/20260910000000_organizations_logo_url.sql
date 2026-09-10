-- organizations.logo_url
--
-- The column was never defined by any migration, yet shipped code both writes it
-- (apps/web/app/api/settings/organization/logo/route.ts) and read it
-- (backend/app/services/org_membership.py). The write returned a PostgREST 42703 on
-- every logo upload, and the read failed the whole select, which is why the org
-- switcher rendered the literal string "Organization" instead of an org name.
--
-- Adding the column repairs the existing upload feature. It carries no default and
-- no backfill: an org without a logo reports absence rather than a stand-in.
--
-- The other three columns reported alongside this one (agent_memory_promotion_audit
-- .status/.created_at, org_query_clusters.query_count) are deliberately NOT added.
-- Those names do not exist anywhere, local or remote: the real columns are
-- status_at_decision, decided_at and member_query_count, and the readers were fixed
-- to use them. Adding the misspelled duplicates would have shadowed the populated
-- columns with permanently-null ones and turned a loud error into silent bad data.

ALTER TABLE public.organizations
  ADD COLUMN IF NOT EXISTS logo_url text;
