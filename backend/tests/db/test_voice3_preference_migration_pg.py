"""Exercise unchanged migration SQL on a throwaway PostgreSQL cluster."""
import json
import pytest
from tests.db.pg_harness import MIGRATIONS,pg_cluster,requires_pg

pytestmark=requires_pg
ORG="11111111-1111-4111-8111-111111111111"
OTHER="22222222-2222-4222-8222-222222222222"
A="33333333-3333-4333-8333-333333333333"
B="44444444-4444-4444-8444-444444444444"
BATCH="55555555-5555-4555-8555-555555555555"
OLD="A"*20
NEW="B"*20
SHA="a"*40
PROFILE={"voice_source":"preset_library","voice_id":OLD,"voice_key":"sarah","tts_model":"eleven_flash_v2_5","unknown":{"keep":True},"language":"en"}

def literal(obj):
    return "'"+json.dumps(obj).replace("'","''")+"'::jsonb"

def plan(agent=A,profile=None):
    before=PROFILE if profile is None else profile
    return {"agent_id":agent,"before":before,"after":{**before,"voice_id":NEW}}

def apply(pg,items,org=ORG,check=True):
    return pg.psql(f"SELECT public.voice3_apply_preferences('{org}','{BATCH}','{SHA}',{literal(items)});",check=check)

def rollback(pg,check=True):
    return pg.psql(f"SELECT public.voice3_rollback_preferences('{ORG}','{BATCH}');",check=check)

def profile(pg,agent=A):
    return json.loads(pg.value(f"SELECT voice_profile FROM public.agents WHERE id='{agent}'"))

@pytest.fixture(scope="module")
def pg():
    bootstrap="""
    CREATE ROLE anon NOLOGIN;
    CREATE ROLE authenticated NOLOGIN;
    CREATE ROLE service_role NOLOGIN BYPASSRLS;
    CREATE TABLE public.agents(id uuid PRIMARY KEY,org_id uuid NOT NULL,voice_profile jsonb NOT NULL);
    CREATE TABLE public.agent_custom_voices(org_id uuid NOT NULL,elevenlabs_voice_id text NOT NULL);
    """
    with pg_cluster(bootstrap,(MIGRATIONS/"20261127010000_voice3_preference_journal.sql").read_text()) as server:
        yield server

@pytest.fixture(autouse=True)
def seed(pg):
    pg.psql(f"TRUNCATE public.voice3_preference_entries,public.voice3_preference_batches,public.agents,public.agent_custom_voices; INSERT INTO public.agents VALUES ('{A}','{ORG}',{literal(PROFILE)}),('{B}','{OTHER}',{literal(PROFILE)});")

def test_apply_replay_and_exact_rollback(pg):
    assert apply(pg,[plan()]).stdout.strip()=="1"
    assert profile(pg)==plan()["after"]
    assert profile(pg,B)==PROFILE
    assert apply(pg,[plan()]).stdout.strip()=="0"
    assert pg.value("SELECT count(*) FROM public.voice3_preference_entries")=="1"
    assert rollback(pg).stdout.strip()=="1"
    assert profile(pg)==PROFILE
    assert rollback(pg).stdout.strip()=="0"
    assert apply(pg,[plan()],check=False).returncode!=0

def test_cross_tenant_conflict_rolls_back_entire_batch(pg):
    assert apply(pg,[plan(),plan(B)],check=False).returncode!=0
    assert profile(pg)==PROFILE
    assert pg.value("SELECT count(*) FROM public.voice3_preference_batches")=="0"

@pytest.mark.parametrize("kind",["custom_source","custom_registry","stale","duplicate","changed_model"])
def test_unsafe_batch_refused(pg,kind):
    items=[plan()]
    if kind=="custom_source":
        custom={**PROFILE,"voice_source":"custom_voice_v3"}
        pg.psql(f"UPDATE public.agents SET voice_profile={literal(custom)} WHERE id='{A}'")
        items=[plan(profile=custom)]
    elif kind=="custom_registry":
        pg.psql(f"INSERT INTO public.agent_custom_voices VALUES ('{ORG}','{OLD}')")
    elif kind=="stale":
        pg.psql(f"UPDATE public.agents SET voice_profile=voice_profile||'{{\"extra\":1}}' WHERE id='{A}'")
    elif kind=="duplicate":
        items*=2
    else:
        items[0]["after"]["tts_model"]="eleven_v3"
    before=profile(pg)
    assert apply(pg,items,check=False).returncode!=0
    assert profile(pg)==before
    assert pg.value("SELECT count(*) FROM public.voice3_preference_entries")=="0"

def test_rollback_refuses_newer_user_edit(pg):
    apply(pg,[plan()])
    pg.psql(f"UPDATE public.agents SET voice_profile=voice_profile||'{{\"extra\":1}}' WHERE id='{A}'")
    changed=profile(pg)
    assert rollback(pg,check=False).returncode!=0
    assert profile(pg)==changed
    assert pg.value("SELECT state FROM public.voice3_preference_batches")=="applied"

@pytest.mark.parametrize("role",["anon","authenticated","service_role"])
def test_no_runtime_role_can_execute_or_read_journal(pg,role):
    assert pg.psql(f"SET ROLE {role}; SELECT * FROM public.voice3_preference_entries;",check=False).returncode!=0
    assert pg.psql(f"SET ROLE {role}; SELECT public.voice3_rollback_preferences('{ORG}','{BATCH}');",check=False).returncode!=0
