-- Phase 5: link goals, work objects, agent jobs and business entities by
-- foreign key instead of keyword guesses, and let AI-proposed work live in
-- work_objects as status 'proposed'.
--
-- Additive and idempotent: nullable columns, ON DELETE SET NULL, a status
-- check widened by one value. Nothing writes these columns until the backend
-- flags are on.
--
-- Preflight (read only):
--   SELECT status, count(*) FROM public.work_objects GROUP BY 1;
--   SELECT count(*) FROM public.agent_jobs;
-- Rollback:
--   ALTER TABLE public.agent_jobs DROP COLUMN IF EXISTS goal_id, DROP COLUMN IF EXISTS work_object_id;
--   ALTER TABLE public.work_objects DROP COLUMN IF EXISTS goal_id, DROP COLUMN IF EXISTS business_entity_id;
--   (then restore work_objects_status_check without 'proposed', after moving proposed rows to 'archived')

ALTER TABLE public.work_objects
  ADD COLUMN IF NOT EXISTS goal_id uuid REFERENCES public.goals(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS business_entity_id uuid REFERENCES public.org_business_entities(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_work_objects_goal
  ON public.work_objects (org_id, goal_id) WHERE goal_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_work_objects_business_entity
  ON public.work_objects (org_id, business_entity_id) WHERE business_entity_id IS NOT NULL;

ALTER TABLE public.work_objects DROP CONSTRAINT IF EXISTS work_objects_status_check;
ALTER TABLE public.work_objects
  ADD CONSTRAINT work_objects_status_check CHECK (
    status IN (
      'proposed',
      'identified',
      'planned',
      'in_progress',
      'awaiting_approval',
      'blocked',
      'completed',
      'failed',
      'archived'
    )
  ) NOT VALID;
ALTER TABLE public.work_objects VALIDATE CONSTRAINT work_objects_status_check;

ALTER TABLE public.agent_jobs
  ADD COLUMN IF NOT EXISTS goal_id uuid REFERENCES public.goals(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS work_object_id uuid REFERENCES public.work_objects(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_agent_jobs_goal
  ON public.agent_jobs (org_id, goal_id) WHERE goal_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_agent_jobs_work_object
  ON public.agent_jobs (work_object_id) WHERE work_object_id IS NOT NULL;

-- A goal, entity or work object linked to a row must belong to the row's org.
CREATE OR REPLACE FUNCTION public.enforce_work_object_links_same_org()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
  IF NEW.goal_id IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM public.goals g WHERE g.id = NEW.goal_id AND g.org_id = NEW.org_id
  ) THEN
    RAISE EXCEPTION 'goal % is not in org %', NEW.goal_id, NEW.org_id USING ERRCODE = '23503';
  END IF;
  IF NEW.business_entity_id IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM public.org_business_entities e WHERE e.id = NEW.business_entity_id AND e.org_id = NEW.org_id
  ) THEN
    RAISE EXCEPTION 'business entity % is not in org %', NEW.business_entity_id, NEW.org_id USING ERRCODE = '23503';
  END IF;
  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.enforce_agent_job_links_same_org()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
  IF NEW.goal_id IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM public.goals g WHERE g.id = NEW.goal_id AND g.org_id = NEW.org_id
  ) THEN
    RAISE EXCEPTION 'goal % is not in org %', NEW.goal_id, NEW.org_id USING ERRCODE = '23503';
  END IF;
  IF NEW.work_object_id IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM public.work_objects w WHERE w.id = NEW.work_object_id AND w.org_id = NEW.org_id
  ) THEN
    RAISE EXCEPTION 'work object % is not in org %', NEW.work_object_id, NEW.org_id USING ERRCODE = '23503';
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS work_objects_links_same_org ON public.work_objects;
CREATE TRIGGER work_objects_links_same_org
  BEFORE INSERT OR UPDATE OF goal_id, business_entity_id, org_id ON public.work_objects
  FOR EACH ROW EXECUTE FUNCTION public.enforce_work_object_links_same_org();

DROP TRIGGER IF EXISTS agent_jobs_links_same_org ON public.agent_jobs;
CREATE TRIGGER agent_jobs_links_same_org
  BEFORE INSERT OR UPDATE OF goal_id, work_object_id, org_id ON public.agent_jobs
  FOR EACH ROW EXECUTE FUNCTION public.enforce_agent_job_links_same_org();
