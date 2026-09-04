-- PSTN voice sessions: Twilio Media Streams bridged to CognitiveTurnKernel.

CREATE TABLE IF NOT EXISTS public.voice_pstn_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  agent_id text,
  work_object_id uuid REFERENCES public.work_objects(id) ON DELETE SET NULL,
  contact_id text,
  contact_phone text NOT NULL,
  from_phone text,
  direction text NOT NULL DEFAULT 'outbound' CHECK (direction IN ('inbound', 'outbound')),
  objective text,
  status text NOT NULL DEFAULT 'pending' CHECK (
    status IN (
      'pending',
      'ringing',
      'answered',
      'in_progress',
      'voicemail',
      'completed',
      'failed',
      'cancelled'
    )
  ),
  twilio_call_sid text,
  twilio_stream_sid text,
  conversation_id text,
  policy jsonb NOT NULL DEFAULT '{}'::jsonb,
  transcript jsonb NOT NULL DEFAULT '[]'::jsonb,
  tool_calls jsonb NOT NULL DEFAULT '[]'::jsonb,
  approval_events jsonb NOT NULL DEFAULT '[]'::jsonb,
  outcome jsonb NOT NULL DEFAULT '{}'::jsonb,
  recording_url text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  started_at timestamptz,
  answered_at timestamptz,
  ended_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_voice_pstn_sessions_org_created
  ON public.voice_pstn_sessions (org_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_voice_pstn_sessions_call_sid
  ON public.voice_pstn_sessions (twilio_call_sid)
  WHERE twilio_call_sid IS NOT NULL;

ALTER TABLE public.voice_pstn_sessions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "voice_pstn_sessions_org" ON public.voice_pstn_sessions;
CREATE POLICY "voice_pstn_sessions_org"
  ON public.voice_pstn_sessions FOR ALL
  USING (
    org_id = (
      SELECT org_id
      FROM public.organization_members
      WHERE user_id = auth.uid()
      LIMIT 1
    )
  );
