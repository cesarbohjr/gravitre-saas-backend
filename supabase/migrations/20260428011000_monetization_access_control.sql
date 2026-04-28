-- Monetization + access control foundation:
-- - subscriptions
-- - usage_records
-- - departments
-- - department_members
-- - optional addon catalog

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS public.subscriptions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  stripe_customer_id text,
  stripe_subscription_id text,
  tier text NOT NULL DEFAULT 'free' CHECK (tier IN ('free', 'node', 'control', 'command')),
  status text NOT NULL DEFAULT 'trialing' CHECK (status IN ('active', 'past_due', 'canceled', 'trialing', 'inactive')),
  current_period_start timestamptz,
  current_period_end timestamptz,
  seat_count integer NOT NULL DEFAULT 1 CHECK (seat_count >= 0),
  lite_seats integer NOT NULL DEFAULT 0 CHECK (lite_seats >= 0),
  meson_addons jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id),
  UNIQUE (stripe_subscription_id)
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_org_id ON public.subscriptions(org_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON public.subscriptions(status);

CREATE TABLE IF NOT EXISTS public.usage_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  metric_type text NOT NULL CHECK (metric_type IN ('workflow_runs', 'ai_tokens', 'outputs', 'api_calls')),
  quantity integer NOT NULL DEFAULT 0 CHECK (quantity >= 0),
  recorded_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_usage_records_org_time ON public.usage_records(org_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_usage_records_metric ON public.usage_records(metric_type);

CREATE TABLE IF NOT EXISTS public.departments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  name text NOT NULL,
  lite_seat_allocation integer NOT NULL DEFAULT 0 CHECK (lite_seat_allocation >= 0),
  department_admin_id uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, name)
);

CREATE INDEX IF NOT EXISTS idx_departments_org_id ON public.departments(org_id);

CREATE TABLE IF NOT EXISTS public.department_members (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  department_id uuid NOT NULL REFERENCES public.departments(id) ON DELETE CASCADE,
  user_id uuid NOT NULL,
  role text NOT NULL DEFAULT 'viewer' CHECK (role IN ('admin', 'viewer')),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (department_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_department_members_department_id ON public.department_members(department_id);
CREATE INDEX IF NOT EXISTS idx_department_members_user_id ON public.department_members(user_id);

CREATE TABLE IF NOT EXISTS public.meson_addon_catalog (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code text NOT NULL UNIQUE,
  name text NOT NULL,
  description text NOT NULL DEFAULT '',
  monthly_price_usd numeric(10,2) NOT NULL DEFAULT 0,
  stripe_price_id text,
  created_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO public.meson_addon_catalog (code, name, description, monthly_price_usd)
VALUES
  ('advanced_analytics', 'Advanced Analytics', 'Predictive insights and anomaly detection', 99),
  ('custom_model_training', 'Custom Model Training', 'Fine-tune models on organization data', 299),
  ('voice_interface', 'Voice Interface', 'Voice commands for Operator', 49),
  ('multi_language', 'Multi-language', 'Process in 20+ languages', 79),
  ('compliance_pack', 'Compliance Pack', 'HIPAA and SOC2 audit trail bundle', 199)
ON CONFLICT (code) DO NOTHING;

