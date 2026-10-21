"""Actual local media and provider boundaries; never contact real providers."""
import base64
import hashlib
import io
import json
import wave
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from PIL import Image

from app.ml.media_inputs import image_part, decode_media
from app.ml.multimodal_models import MultimodalRouter
from app.ml.generative_models import DiffusionModelConnector
from app.ml.domain_llm import DomainSpecificLLMRouter
from app.ml.training_consent import training_disclosure, consent_is_approved


def png(size=(32, 32)):
    buffer = io.BytesIO()
    Image.new('RGB', size, 'blue').save(buffer, format='PNG')
    return buffer.getvalue()


def test_image_decoding_strips_metadata_and_never_fetches_urls():
    part = image_part(png())
    with Image.open(io.BytesIO(base64.b64decode(part['image_url']['url'].split(',', 1)[1]))) as image:
        assert image.format == 'JPEG' and image.size == (32, 32) and not image.getexif()
    with pytest.raises(Exception): image_part(b'https://private.example/secret')
    with pytest.raises(ValueError, match='container'): decode_media(b'#EXTM3U\nfile:///etc/passwd', 'audio/mp4')


def test_local_audio_decode_produces_bounded_mono_wav():
    import shutil
    if not shutil.which('ffprobe') or not shutil.which('ffmpeg'): pytest.skip('Local decoder unavailable')
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as audio:
        audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(16000)
        audio.writeframes(b'\0\0' * 16000)
    parts, data, scope = decode_media(buffer.getvalue(), 'audio/wav')
    assert not parts and scope == 'audio_transcript'
    with wave.open(io.BytesIO(data)) as audio:
        assert audio.getnchannels() == 1 and audio.getframerate() == 16000


@pytest.mark.asyncio
async def test_multimodal_denies_before_decoding_without_permission():
    with patch('app.ml.training_consent.training_is_approved', AsyncMock(return_value=False)), patch('app.ml.media_inputs.decode_media') as decode:
        result = await MultimodalRouter().predict_structured(org_id='org', settings=MagicMock())
    assert result['status'] == 'dormant'
    decode.assert_not_called()


@pytest.mark.asyncio
async def test_real_image_uses_existing_router_with_authoritative_org():
    router = MagicMock()
    router.complete = AsyncMock(return_value=SimpleNamespace(content='Blue square', model_call_id='trace', model='vision'))
    with patch('app.ml.training_consent.training_is_approved', AsyncMock(return_value=True)), patch(
        'app.ml.provider_execution.processing_policy', return_value={'model': 'vision'}), patch(
        'app.ml.provider_execution.reserve_provider_budget') as reserve, patch(
        'app.core.redis_client.get_sync_redis', return_value=MagicMock()), patch('app.services.model_router.ModelRouter', return_value=router):
        result = await MultimodalRouter().predict_structured(org_id='org', settings=MagicMock(), prompt='Describe',
            media={'base64': base64.b64encode(png()).decode(), 'mime_type': 'image/png'})
    assert result['predictions'] == ['Blue square'] and result['model_call_id'] == 'trace'
    assert router.complete.call_args.kwargs['org_id'] == 'org'
    assert router.complete.call_args.kwargs['image_parts'][0]['type'] == 'image_url'
    reserve.assert_called_once()


@pytest.mark.asyncio
async def test_uncertain_generation_does_not_redispatch():
    prompt, actor, model = 'a square', 'actor', 'gpt-image-test'
    fingerprint = hashlib.sha256((actor+'\0'+prompt+'\0'+model).encode()).hexdigest()
    redis = MagicMock(); redis.set.return_value = False
    redis.get.return_value = json.dumps({'state': 'started', 'fingerprint': fingerprint})
    with patch('app.ml.provider_execution.require_permission', AsyncMock()), patch(
        'app.ml.provider_execution.processing_policy', return_value={'model': model}), patch(
        'app.core.redis_client.get_sync_redis', return_value=redis), patch('openai.AsyncOpenAI') as provider:
        result = await DiffusionModelConnector().generate(org_id='org', actor_id=actor, prompt=prompt,
            operation_id=str(uuid4()), settings=MagicMock())
    assert result['status'] == 'outcome_uncertain'
    provider.assert_not_called()
    assert (await DiffusionModelConnector().predict_structured())['reason'] == 'governed_generation_tool_required'


@pytest.mark.asyncio
async def test_generation_requires_private_storage_and_independent_readback():
    provider = MagicMock()
    provider.images.generate = AsyncMock(return_value=SimpleNamespace(data=[SimpleNamespace(b64_json=base64.b64encode(png((1024, 1024))).decode())]))
    provider.close = AsyncMock()
    redis = MagicMock(); redis.set.return_value = True
    client = MagicMock(); client.storage.get_bucket.return_value = {'public': False}
    stored = {}
    def write(*a, **kwargs): stored['data'] = kwargs['data']
    with patch('app.ml.provider_execution.require_permission', AsyncMock()), patch(
        'app.ml.provider_execution.processing_policy', return_value={'model': 'gpt-image-test'}), patch(
        'app.ml.provider_execution.reserve_provider_budget'), patch('app.core.redis_client.get_sync_redis', return_value=redis), patch(
        'app.workflows.repository.get_supabase_client', return_value=client), patch('openai.AsyncOpenAI', return_value=provider), patch(
        'app.services.ai_guardrails.moderate_input', AsyncMock()), patch('app.services.byo_storage.put_org_file', side_effect=write), patch(
        'app.services.byo_storage.read_org_file', side_effect=lambda *a, **k: stored['data']), patch(
        'app.services.byo_storage.resolve_download_url', return_value={'url': 'https://private.example/signed'}):
        result = await DiffusionModelConnector().generate(org_id='org', actor_id='actor', prompt='square', operation_id=str(uuid4()),
            settings=SimpleNamespace(chat_artifacts_bucket='chat-artifacts', openai_api_key='fake'))
    assert result['artifact_verified'] and result['storage_path'].startswith('org/generated-images/')
    provider.images.generate.assert_awaited_once(); provider.close.assert_awaited_once()


def test_domain_contract_and_provider_purpose_are_explicit():
    model = DomainSpecificLLMRouter()
    with pytest.raises(ValueError): model.save()
    model.load(json.dumps({'schema': 1, 'fine_tuned_model_id': 'ft:base:org:model', 'department': 'support',
        'target_definition': 'routing', 'base_model': 'base', 'labels': ['a', 'b']}).encode())
    restored = DomainSpecificLLMRouter(); restored.load(model.save())
    assert restored.department == 'support' and restored.labels == ['a', 'b']
    assert training_disclosure('multimodal_router')['processing_kind'] == 'inference'
    assert training_disclosure('diffusion_model')['processing_kind'] == 'generation'
    federation = training_disclosure('federated_learning')
    assert federation['sharing_scope'] == 'cross_tenant_private_updates'
    assert not consent_is_approved({'federated_learning': {'state': 'approved', 'scope_digest': federation['scope_digest'],
        'sharing_scope': 'organization_only'}}, 'federated_learning')


def test_short_video_decodes_at_least_one_bounded_sample(tmp_path):
    import shutil
    import subprocess
    if not shutil.which('ffmpeg'): pytest.skip('Local decoder unavailable')
    source = tmp_path/'clip.mp4'
    subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i','color=c=blue:s=128x128:d=1',
                    '-c:v','mpeg4',str(source)], check=True, capture_output=True, timeout=15)
    frames, audio, scope = decode_media(source.read_bytes(), 'video/mp4')
    assert 1 <= len(frames) <= 6 and audio is None and scope == 'sampled_video_frames_and_transcript'


def test_paid_generation_is_a_write_and_requires_actual_authority():
    from app.services.catalog_write_authority import invoke_action_requires_write_approval
    from app.services.generated_image_tool import execute_generate_image
    from app.services.tool_types import ToolContext
    from app.services.write_authority import WriteAuthorityError, write_authority
    assert invoke_action_requires_write_approval('assistant.generate_image')
    ctx = ToolContext(settings=MagicMock(), client=MagicMock(), org_id='org', actor_id='actor', turn_id='turn')
    with patch('app.ml.generative_models.DiffusionModelConnector.generate', AsyncMock()) as generate:
        with pytest.raises(WriteAuthorityError): execute_generate_image(ctx, {'prompt':'square'})
        with write_authority('policy','autonomous'):
            with pytest.raises(WriteAuthorityError): execute_generate_image(ctx, {'prompt':'square'})
        generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_native_router_preserves_image_blocks_and_disables_text_cache(mock_settings):
    from app.services.model_router import ModelRouter, TaskType
    from app.config import MODEL_TIERS
    router = ModelRouter(mock_settings)
    router._openai = AsyncMock()
    router._openai.chat.completions.create = AsyncMock(return_value=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='Blue square'))]))
    with patch.object(router, '_log_model_call', AsyncMock()), patch.object(router, '_assert_model_policy'), patch.object(
        router, '_enforce_rate_and_budget'), patch('app.services.model_router.get_supabase_client', return_value=MagicMock()), patch(
        'app.services.model_router.load_org_model_policy', return_value={'mode':'open'}):
        result = await router.complete(TaskType.CONTENT_GENERATION, 'Describe', org_id='org', image_parts=[image_part(png())], use_cache=True)
    assert result.content == 'Blue square' and result.model == MODEL_TIERS['vision']['openai']
    content = router._openai.chat.completions.create.call_args.kwargs['messages'][-1]['content']
    assert content[0]['type'] == 'text' and content[1]['type'] == 'image_url'
    assert not router._cache


def test_implemented_platform_tools_are_discoverable_without_a_fake_oauth_connector():
    from app.services.tool_registry import ToolRegistry
    registry = ToolRegistry()
    tools = registry.get_tools_for_agent(['platform'], [])
    names = {tool['function']['name'] for tool in tools}
    assert {'platform_generate_image', 'assistant_analyze_media'} <= names
    assert 'platform_generate_image' not in {tool['function']['name'] for tool in registry.get_tools_for_agent(['slack'], [])}


def test_private_object_stream_refuses_actual_bytes_above_metadata_bound():
    from app.services.byo_storage import read_org_file, ByoStorageError
    client = MagicMock()
    client.storage.from_.return_value.list.return_value = [{'name':'file.png','metadata':{'size':2}}]
    response = MagicMock()
    response.iter_bytes.return_value = [b'12', b'345']
    transport = MagicMock()
    transport.stream.return_value.__enter__.return_value = response
    with patch('httpx.Client') as factory:
        factory.return_value.__enter__.return_value = transport
        with pytest.raises(ByoStorageError, match='exceeds'):
            read_org_file(client, SimpleNamespace(byo_storage_enabled=False, supabase_url='https://test.supabase.co',
                          supabase_service_role_key='fake'), org_id='org', logical_bucket='private', path='org/file.png', max_bytes=4)
    assert transport.stream.call_args.kwargs['headers']['Authorization'] == 'Bearer fake'
    with pytest.raises(ByoStorageError, match='File not found'):
        read_org_file(client, MagicMock(), org_id='org', logical_bucket='private', path='foreign/file.png', max_bytes=4)


def test_reviewed_provider_cost_cap_is_durable_and_idempotent_across_redis_restarts():
    from app.ml.provider_execution import reserve_provider_budget
    database = {'settings': {}}
    class LedgerQuery:
        def __init__(self): self.value = None
        def select(self, *a): return self
        def eq(self, *a): return self
        def limit(self, *a): return self
        def update(self, value): self.value = value; return self
        def execute(self):
            if self.value is not None: database.update(self.value)
            return SimpleNamespace(data=[database.copy()])
    client = SimpleNamespace(table=lambda name: LedgerQuery())
    policy = {'max_request_usd':.25, 'monthly_limit_usd':.5}
    with patch('app.ml.provider_execution.get_supabase_client', return_value=client):
        reserve_provider_budget(MagicMock(), 'org', 'image', policy, 'operation-1', MagicMock())
        reserve_provider_budget(MagicMock(), 'org', 'image', policy, 'operation-1', MagicMock())
        reserve_provider_budget(MagicMock(), 'org', 'image', policy, 'operation-2', MagicMock())
        with pytest.raises(ValueError, match='budget exhausted'):
            reserve_provider_budget(MagicMock(), 'org', 'image', policy, 'operation-3', MagicMock())
    import datetime
    period = database['settings']['advanced_provider_cost_reservations'][datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m')]
    assert len(period['image']) == 2 and sum(period['image'].values()) == 500000


def test_generated_image_completion_mapper_requires_actual_private_artifact_proof():
    from app.services.connector_output_mappers.generic import summarize_write_action
    assert 'unconfirmed' in summarize_write_action(action='assistant.generate_image',result_data={'status':'ok'})
    result = {'status':'ok','artifact_verified':True,'sha256':'a'*64,'storage_path':'org/generated-images/image.png','hostedFiles':[{'id':'image'}]}
    assert 'verified the stored file' in summarize_write_action(action='assistant.generate_image',result_data=result)


def test_raster_allowlist_rejects_tiff_and_reencoding_removes_embedded_private_metadata():
    from PIL.PngImagePlugin import PngInfo
    buffer = io.BytesIO()
    Image.new('RGB',(16,16),'blue').save(buffer,format='TIFF')
    with pytest.raises(ValueError,match='container'):
        image_part(buffer.getvalue())
    metadata = PngInfo()
    metadata.add_text('Comment','private-marker-that-must-not-leave')
    buffer = io.BytesIO()
    Image.new('RGB',(16,16),'blue').save(buffer,format='PNG',pnginfo=metadata)
    from app.ml.media_inputs import reencode_image
    encoded = reencode_image(buffer.getvalue(),output_format='png')
    assert b'private-marker-that-must-not-leave' not in encoded
    with Image.open(io.BytesIO(encoded)) as image:
        assert not image.info.get('Comment') and image.size == (16,16)


def test_native_image_action_canonical_alias_preserves_scope_and_write_authority():
    from app.connectors.action_catalog.registry import get_action_spec, catalog_scopes_by_tool
    from app.services.catalog_write_authority import invoke_action_requires_write_approval
    original = get_action_spec('assistant.generate_image')
    assert get_action_spec('assistant.images.generate') is original
    assert original.destructive and original.requires_approval
    assert catalog_scopes_by_tool()[original.id] == ['platform:artifacts:write']
    assert invoke_action_requires_write_approval('assistant.images.generate')
