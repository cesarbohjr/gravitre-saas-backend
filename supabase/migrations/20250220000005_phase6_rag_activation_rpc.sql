-- Phase 6: Atomic RAG document activation via RPC

CREATE OR REPLACE FUNCTION public.activate_rag_document_version(
  p_org_id uuid,
  p_new_doc_id uuid,
  p_source_id uuid,
  p_external_id text
)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
  v_active_count int;
BEGIN
  -- Lock all matching rows to ensure atomic swap
  PERFORM 1
  FROM public.rag_documents
  WHERE org_id = p_org_id
    AND source_id = p_source_id
    AND external_id = p_external_id
  FOR UPDATE;

  -- Deactivate previous active versions
  UPDATE public.rag_documents
     SET is_active = false,
         archived_at = now()
   WHERE org_id = p_org_id
     AND source_id = p_source_id
     AND external_id = p_external_id
     AND id <> p_new_doc_id;

  -- Activate the new version
  UPDATE public.rag_documents
     SET is_active = true,
         archived_at = null
   WHERE id = p_new_doc_id
     AND org_id = p_org_id
     AND source_id = p_source_id
     AND external_id = p_external_id;

  -- Ensure exactly one active remains
  SELECT COUNT(*)
    INTO v_active_count
  FROM public.rag_documents
  WHERE org_id = p_org_id
    AND source_id = p_source_id
    AND external_id = p_external_id
    AND is_active = true;

  IF v_active_count <> 1 THEN
    RAISE EXCEPTION 'Expected exactly one active document version';
  END IF;
END;
$$;
