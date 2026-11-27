-- Additive journal only. No agent updates on schema installation.
-- Deliberately no service-role or client execution grant: DBA-operated
-- maintenance only, after independent release authorization. No runtime RPC.
CREATE TABLE IF NOT EXISTS public.voice3_preference_batches (
    org_id uuid NOT NULL,
    batch_id uuid NOT NULL,
    source_sha text NOT NULL CHECK (source_sha ~ '^[0-9a-f]{40}$'),
    manifest jsonb NOT NULL,
    state text NOT NULL CHECK (state IN ('applied','rolled_back')),
    applied_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    rolled_back_at timestamptz,
    PRIMARY KEY (org_id,batch_id)
);
CREATE TABLE IF NOT EXISTS public.voice3_preference_entries (
    org_id uuid NOT NULL,
    batch_id uuid NOT NULL,
    agent_id uuid NOT NULL,
    before_profile jsonb NOT NULL,
    after_profile jsonb NOT NULL,
    applied_row_version text NOT NULL,
    PRIMARY KEY (org_id,batch_id,agent_id),
    FOREIGN KEY (org_id,batch_id) REFERENCES public.voice3_preference_batches(org_id,batch_id)
);
ALTER TABLE public.voice3_preference_batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.voice3_preference_entries ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.voice3_preference_batches,public.voice3_preference_entries FROM PUBLIC,anon,authenticated,service_role;

-- An explicit manifest of per-agent, previously reviewed before/after images.
-- Only the voice_id field may change; other preference fields stay byte-for-byte
-- equivalent as JSONB. Caller must resolve key-only/implicit defaults separately.
CREATE OR REPLACE FUNCTION public.voice3_apply_preferences(
    p_org uuid,p_batch uuid,p_sha text,p_manifest jsonb
) RETURNS integer LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE
    prior public.voice3_preference_batches%ROWTYPE;
    item jsonb;
    aid uuid;
    old_profile jsonb;
    new_profile jsonb;
    current_profile jsonb;
    version_now text;
    n integer := 0;
BEGIN
    IF p_org IS NULL OR p_batch IS NULL OR p_sha IS NULL OR p_sha !~ '^[0-9a-f]{40}$'
       OR jsonb_typeof(p_manifest) IS DISTINCT FROM 'array' THEN
        RAISE EXCEPTION 'invalid migration request';
    END IF;
    IF jsonb_array_length(p_manifest) NOT BETWEEN 1 AND 500 THEN RAISE EXCEPTION 'invalid batch size'; END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended('voice3:'||p_org::text,0));
    SELECT * INTO prior FROM public.voice3_preference_batches WHERE org_id=p_org AND batch_id=p_batch;
    IF FOUND THEN
        IF prior.source_sha IS DISTINCT FROM p_sha OR prior.manifest IS DISTINCT FROM p_manifest
           OR prior.state <> 'applied' THEN RAISE EXCEPTION 'batch replay conflict'; END IF;
        RETURN 0;
    END IF;
    -- Prevent a concurrent custom-voice registration during classification.
    -- Short bounded maintenance transaction; lock is intentionally conservative.
    LOCK TABLE public.agent_custom_voices IN SHARE MODE;
    INSERT INTO public.voice3_preference_batches(org_id,batch_id,source_sha,manifest,state)
        VALUES(p_org,p_batch,p_sha,p_manifest,'applied');
    FOR item IN SELECT value FROM jsonb_array_elements(p_manifest) ORDER BY value->>'agent_id' LOOP
        aid := (item->>'agent_id')::uuid;
        old_profile := item->'before';
        new_profile := item->'after';
        IF aid IS NULL OR jsonb_typeof(old_profile) IS DISTINCT FROM 'object'
           OR jsonb_typeof(new_profile) IS DISTINCT FROM 'object'
           OR old_profile->>'voice_source' IS DISTINCT FROM 'preset_library'
           OR (old_profile ? 'source' AND old_profile->>'source' IS DISTINCT FROM 'preset_library')
           OR (old_profile->>'voice_id') IS NULL OR old_profile->>'voice_id' !~ '^[A-Za-z0-9]{16,64}$'
           OR (new_profile->>'voice_id') IS NULL OR new_profile->>'voice_id' !~ '^[A-Za-z0-9]{16,64}$'
           OR old_profile->>'voice_id'=new_profile->>'voice_id'
           OR (old_profile-'voice_id') IS DISTINCT FROM (new_profile-'voice_id') THEN
            RAISE EXCEPTION 'unsupported or unsafe preference change';
        END IF;
        SELECT voice_profile INTO current_profile FROM public.agents WHERE id=aid AND org_id=p_org FOR UPDATE;
        IF NOT FOUND OR current_profile IS DISTINCT FROM old_profile THEN RAISE EXCEPTION 'agent missing or preference conflict'; END IF;
        IF EXISTS(SELECT 1 FROM public.agent_custom_voices WHERE org_id=p_org AND
            elevenlabs_voice_id IN (old_profile->>'voice_id',new_profile->>'voice_id')) THEN
            RAISE EXCEPTION 'custom voice protected';
        END IF;
        UPDATE public.agents SET voice_profile=new_profile WHERE id=aid AND org_id=p_org
            RETURNING xmin::text INTO version_now;
        INSERT INTO public.voice3_preference_entries VALUES(p_org,p_batch,aid,old_profile,new_profile,version_now);
        n := n+1;
    END LOOP;
    RETURN n;
END $$;

CREATE OR REPLACE FUNCTION public.voice3_rollback_preferences(p_org uuid,p_batch uuid)
RETURNS integer LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE
    prior public.voice3_preference_batches%ROWTYPE;
    entry public.voice3_preference_entries%ROWTYPE;
    actual jsonb;
    row_version text;
    n integer := 0;
BEGIN
    IF p_org IS NULL OR p_batch IS NULL THEN RAISE EXCEPTION 'invalid rollback request'; END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended('voice3:'||p_org::text,0));
    SELECT * INTO prior FROM public.voice3_preference_batches WHERE org_id=p_org AND batch_id=p_batch FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'batch not found'; END IF;
    IF prior.state='rolled_back' THEN RETURN 0; END IF;
    FOR entry IN SELECT * FROM public.voice3_preference_entries WHERE org_id=p_org AND batch_id=p_batch ORDER BY agent_id LOOP
        SELECT voice_profile,xmin::text INTO actual,row_version FROM public.agents
            WHERE id=entry.agent_id AND org_id=p_org FOR UPDATE;
        -- Reject even an intervening edit that restores the same JSON value.
        -- xmin is a conservative short-window concurrency fence, not a permanent
        -- version identifier across dump/restore or transaction ID wraparound.
        IF NOT FOUND OR actual IS DISTINCT FROM entry.after_profile OR row_version IS DISTINCT FROM entry.applied_row_version
            THEN RAISE EXCEPTION 'rollback conflict: agent changed since migration'; END IF;
        UPDATE public.agents SET voice_profile=entry.before_profile WHERE id=entry.agent_id AND org_id=p_org;
        n := n+1;
    END LOOP;
    IF n <> jsonb_array_length(prior.manifest) THEN RAISE EXCEPTION 'incomplete rollback journal'; END IF;
    UPDATE public.voice3_preference_batches SET state='rolled_back',rolled_back_at=clock_timestamp()
        WHERE org_id=p_org AND batch_id=p_batch;
    RETURN n;
END $$;
REVOKE ALL ON FUNCTION public.voice3_apply_preferences(uuid,uuid,text,jsonb) FROM PUBLIC,anon,authenticated,service_role;
REVOKE ALL ON FUNCTION public.voice3_rollback_preferences(uuid,uuid) FROM PUBLIC,anon,authenticated,service_role;
