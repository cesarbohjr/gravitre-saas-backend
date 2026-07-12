-- Allow intelligence_pack (and knowledge_pack install ledger) for Part D P5 / STA-310.
-- Prod today rejects both marketplace_assets.asset_type=intelligence_pack and
-- marketplace_installs.installed_entity_type in {knowledge_pack, intelligence_pack}.

ALTER TABLE public.marketplace_assets
  DROP CONSTRAINT IF EXISTS marketplace_assets_asset_type_check;

ALTER TABLE public.marketplace_assets
  ADD CONSTRAINT marketplace_assets_asset_type_check
  CHECK (asset_type IN (
    'ai_agent',
    'workflow',
    'knowledge_pack',
    'department_pack',
    'connector_config',
    'intelligence_pack'
  ));

ALTER TABLE public.marketplace_installs
  DROP CONSTRAINT IF EXISTS marketplace_installs_installed_entity_type_check;

ALTER TABLE public.marketplace_installs
  ADD CONSTRAINT marketplace_installs_installed_entity_type_check
  CHECK (installed_entity_type IN (
    'operator',
    'agent',
    'workflow',
    'rag_source',
    'connector',
    'department_pack',
    'knowledge_pack',
    'intelligence_pack'
  ));
