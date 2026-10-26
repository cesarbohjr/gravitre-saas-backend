-- Native Prospecting Play: tenant-scoped records, source evidence and credit ledger.
-- Zero external writes; all tables enforce authenticated org membership.
create table if not exists public.prospect_companies (
 id uuid primary key default gen_random_uuid(),
 org_id uuid not null references public.organizations(id) on delete cascade,
 domain text not null,
 name text not null,
 country_code text not null default 'CA',
 industry text,
 fit_score integer not null default 0 check(fit_score between 0 and 100),
 status text not null default 'candidate' check(status in ('candidate','researched','qualified','rejected')),
 source_url text not null,
 source_license text not null,
 source_authorized boolean not null default false,
 first_seen_at timestamptz not null default now(),
 updated_at timestamptz not null default now(),
 unique(org_id,domain)
);
create table if not exists public.prospect_contacts (
 id uuid primary key default gen_random_uuid(),
 org_id uuid not null references public.organizations(id) on delete cascade,
 company_id uuid not null,
 full_name text,
 role_title text,
 identity_source_url text,
 email text,
 email_status text not null default 'unknown' check(email_status in ('unknown','valid','invalid','risky')),
 verification_provider text,
 verified_at timestamptz,
 consent_basis text,
 consent_source_url text,
 consent_reviewed_by uuid,
 consent_reviewed_at timestamptz,
 suppressed boolean not null default false,
 crm_status text not null default 'quarantine' check(crm_status in ('quarantine','review','eligible','exported')),
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now(),
 unique(org_id,company_id,email),
 foreign key (company_id) references public.prospect_companies(id) on delete cascade
);
create unique index if not exists prospect_companies_org_id_id_unique on public.prospect_companies(org_id,id);
create table if not exists public.prospect_evidence (
 id uuid primary key default gen_random_uuid(),
 org_id uuid not null references public.organizations(id) on delete cascade,
 company_id uuid,
 contact_id uuid,
 evidence_type text not null,
 source_url text not null,
 source_license text,
 payload_hash text not null,
 observed_at timestamptz not null default now(),
 foreign key (company_id) references public.prospect_companies(id) on delete cascade,
 foreign key (contact_id) references public.prospect_contacts(id) on delete cascade
);
create unique index if not exists prospect_contacts_org_id_id_unique on public.prospect_contacts(org_id,id);
create table if not exists public.prospect_provider_usage (
 id uuid primary key default gen_random_uuid(),
 org_id uuid not null references public.organizations(id) on delete cascade,
 provider text not null check(provider in ('hunter','emailable','apollo','snov','millionverifier')),
 operation text not null,
 billing_period date not null,
 request_id text not null,
 credits_reserved integer not null default 0 check(credits_reserved >= 0),
 credits_consumed integer not null default 0 check(credits_consumed >= 0),
 status text not null default 'reserved' check(status in ('reserved','charged','released','failed')),
 created_at timestamptz not null default now(),
 unique(org_id,provider,request_id)
);
create table if not exists public.prospect_suppressions (
 id uuid primary key default gen_random_uuid(),
 org_id uuid not null references public.organizations(id) on delete cascade,
 normalized_email text not null,
 reason text not null,
 created_at timestamptz not null default now(),
 unique(org_id,normalized_email)
);
-- Ensure composite tenant foreign keys are unique before creating referencing tables.
do $$ begin
  if not exists (select 1 from pg_constraint where conname='prospect_contacts_org_id_id_unique_constraint') then
    alter table public.prospect_contacts add constraint prospect_contacts_org_id_id_unique_constraint unique(org_id,id);
  end if;
end $$;
alter table public.prospect_contacts add constraint prospect_contact_company_same_org foreign key(org_id,company_id) references public.prospect_companies(org_id,id);
alter table public.prospect_evidence add constraint prospect_evidence_company_same_org foreign key(org_id,company_id) references public.prospect_companies(org_id,id);
alter table public.prospect_evidence add constraint prospect_evidence_contact_same_org foreign key(org_id,contact_id) references public.prospect_contacts(org_id,id);
-- Tenant members can read only; all mutation is server-side through scoped APIs.
do $$ declare t text; begin
 foreach t in array array['prospect_companies','prospect_contacts','prospect_evidence','prospect_provider_usage','prospect_suppressions'] loop
  execute format('alter table public.%I enable row level security', t);
  execute format('drop policy if exists %I on public.%I', t||'_org_member', t);
  execute format(
    'create policy %I on public.%I for select using (org_id in (select org_id from public.organization_members where user_id=auth.uid()))',
    t||'_org_member', t
  );
  execute format('revoke insert, update, delete on public.%I from anon, authenticated',t);
 end loop;
end $$;
-- Service-role writes must enforce org_id authorization and PendingAction separately.
