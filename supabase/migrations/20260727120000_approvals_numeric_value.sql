-- Approvals numeric_value: structured threshold input for v11 decision-pattern detection.

ALTER TABLE public.approvals
  ADD COLUMN IF NOT EXISTS numeric_value FLOAT,
  ADD COLUMN IF NOT EXISTS numeric_value_currency TEXT DEFAULT 'USD',
  ADD COLUMN IF NOT EXISTS numeric_value_label TEXT;
