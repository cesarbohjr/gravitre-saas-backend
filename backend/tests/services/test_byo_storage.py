"""Bring-your-own file storage: gates (flag, entitlement, verified target), encrypted
credentials, upload routing, read resolution and the admin test endpoint."""
from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_org_context, require_admin
from app.config import Settings, get_settings
from app.connectors.crypto import decrypt_secret
from app.main import app
from app.rag.storage import upload_raw_rag_file
from app.services import byo_storage as byo
from app.services.chat_hosted_file_service import ChatHostedFileService
from tests.services.storage_fakes import FakeClient, FakeS3

ORG = "11111111-1111-4111-8111-111111111111"
OTHER = "33333333-3333-4333-8333-333333333333"
KEY = "ab" * 32
ACCESS_KEY = "AKIAEXAMPLEKEY1234"
SECRET = "very-secret-value-do-not-log"


def _settings(**overrides) -> Settings:
    s = Settings(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test",
        supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
        connector_secrets_encryption_key=KEY,
    )
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


ON = {"byo_storage_enabled": True}
BODY = {
    "endpointUrl": "https://8.8.8.8",
    "region": "us-east-1",
    "bucket": "acme-files",
    "pathPrefix": "/gravitre/prod/",
    "accessKeyId": ACCESS_KEY,
    "secretAccessKey": SECRET,
}


def _saved_client(status: str = "verified") -> FakeClient:
    client = FakeClient()
    byo.save_target(client, _settings(), ORG, "user-1", BODY)
    client.tables["org_storage_targets"][0]["status"] = status
    return client


@pytest.fixture
def s3(monkeypatch):
    fake = FakeS3()
    monkeypatch.setattr(byo, "s3_client", lambda _settings, _row: fake)
    return fake


@pytest.fixture
def entitled(monkeypatch):
    monkeypatch.setattr(byo, "org_entitled", lambda _s, _o: True)


# --------------------------------------------------------------------------- validation


def test_default_flag_is_off():
    assert _settings().byo_storage_enabled is False


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://s3.example.com",
        "https://127.0.0.1",
        "https://10.0.0.5",
        "https://169.254.169.254",
        "https://localhost",
        "https://minio.railway.internal",
        "https://user:pw@s3.example.com",
        "https://s3.example.com/bucket",
    ],
)
def test_endpoint_must_be_public_https(endpoint):
    with pytest.raises(byo.ByoStorageError):
        byo.validate_endpoint(endpoint)


def test_hostname_resolving_to_private_address_is_refused(monkeypatch):
    monkeypatch.setattr(byo.socket, "getaddrinfo", lambda *_a, **_k: [(0, 0, 0, "", ("10.1.2.3", 443))])
    with pytest.raises(byo.ByoStorageError):
        byo.validate_endpoint("https://s3.evil.example")
    monkeypatch.setattr(byo.socket, "getaddrinfo", lambda *_a, **_k: [(0, 0, 0, "", ("52.216.1.1", 443))])
    assert byo.validate_endpoint("https://s3.Example.com:9000") == "https://s3.example.com:9000"
    assert byo.validate_endpoint("") is None


def test_bucket_region_and_prefix_validation():
    with pytest.raises(byo.ByoStorageError):
        byo.validate_target_input({**BODY, "bucket": "Bad_Bucket"})
    with pytest.raises(byo.ByoStorageError):
        byo.validate_target_input({**BODY, "region": "US East"})
    with pytest.raises(byo.ByoStorageError):
        byo.validate_target_input({**BODY, "pathPrefix": "a/../b"})
    assert byo.validate_target_input(BODY)["path_prefix"] == "gravitre/prod"


# --------------------------------------------------------------------------- credentials


def test_credentials_are_encrypted_and_never_returned():
    client = FakeClient()
    view = byo.save_target(client, _settings(), ORG, "user-1", BODY)
    row = client.tables["org_storage_targets"][0]
    assert ACCESS_KEY not in str(row) and SECRET not in str(row)
    assert decrypt_secret(row["secret_access_key_enc"], KEY) == SECRET
    assert decrypt_secret(row["access_key_id_enc"], KEY) == ACCESS_KEY
    assert row["status"] == "untested"
    assert view["accessKeyHint"] == "1234"
    assert SECRET not in str(view) and ACCESS_KEY not in str(view)
    assert "secret_access_key_enc" not in view


def test_update_without_credentials_keeps_them_and_create_requires_them():
    client = _saved_client()
    before = dict(client.tables["org_storage_targets"][0])
    byo.save_target(client, _settings(), ORG, "user-2", {**BODY, "accessKeyId": "", "secretAccessKey": "", "bucket": "acme-two"})
    after = client.tables["org_storage_targets"][0]
    assert after["secret_access_key_enc"] == before["secret_access_key_enc"]
    assert after["bucket"] == "acme-two" and after["status"] == "untested"
    with pytest.raises(byo.ByoStorageError):
        byo.save_target(FakeClient(), _settings(), OTHER, "u", {**BODY, "accessKeyId": "", "secretAccessKey": ""})
    with pytest.raises(byo.ByoStorageError):
        byo.save_target(FakeClient(), _settings(), OTHER, "u", {**BODY, "secretAccessKey": ""})


def test_no_encryption_key_means_nothing_is_saved():
    client = FakeClient()
    with pytest.raises(byo.ByoStorageError):
        byo.save_target(client, _settings(connector_secrets_encryption_key=""), ORG, "u", BODY)
    assert client.tables.get("org_storage_targets", []) == []


# --------------------------------------------------------------------------- gates


def test_flag_off_means_no_target_and_no_reads():
    client = _saved_client()
    client.calls.clear()
    assert byo.active_target(client, _settings(), ORG) is None
    assert client.calls == []


def test_not_entitled_means_no_target(monkeypatch):
    monkeypatch.setattr(byo, "org_entitled", lambda _s, _o: False)
    assert byo.active_target(_saved_client(), _settings(**ON), ORG) is None


def test_untested_or_failed_target_is_not_used(entitled):
    assert byo.active_target(_saved_client("untested"), _settings(**ON), ORG) is None
    assert byo.active_target(_saved_client("failed"), _settings(**ON), ORG) is None
    assert byo.active_target(_saved_client("verified"), _settings(**ON), ORG)["bucket"] == "acme-files"


def test_entitlement_lookup_failure_is_not_entitled(monkeypatch):
    import app.middleware.entitlements as ent

    def boom(*_a):
        raise RuntimeError("billing down")

    monkeypatch.setattr(ent, "resolve_entitlements", boom)
    assert byo.org_entitled(_settings(), ORG) is False


# --------------------------------------------------------------------------- routing


def test_flag_off_upload_is_unchanged(s3):
    client = FakeClient()
    meta = byo.put_org_file(client, _settings(), org_id=ORG, logical_bucket="rag-uploads",
                            path=f"{ORG}/p/a.txt", data=b"hello", content_type="text/plain", purpose="rag_upload")
    assert meta == {"storage_bucket": "rag-uploads", "storage_path": f"{ORG}/p/a.txt", "storage_bytes": 5}
    assert client.uploads[0]["options"] == {"upsert": "true", "content-type": "text/plain"}
    assert "org_file_objects" not in client.tables
    assert s3.calls == []


def test_flag_on_entitled_verified_routes_to_own_bucket_and_records_location(s3, entitled):
    client = _saved_client()
    meta = upload_raw_rag_file(
        client, _settings(**ON), org_id=ORG, environment_name="production", source_id="src",
        job_id="job", filename="notes.txt", data=b"hello", content_type="text/plain",
    )
    key = f"gravitre/prod/rag-uploads/{ORG}/production/src/job/notes.txt"
    assert s3.calls == [("put", "acme-files", key)]
    assert client.uploads == []
    assert meta["storage_location"] == "byo" and meta["storage_path"] == f"{ORG}/production/src/job/notes.txt"
    record = client.tables["org_file_objects"][0]
    assert record["location"] == "byo" and record["object_key"] == key and record["bucket"] == "acme-files"


def test_flag_on_without_entitlement_stays_in_supabase_but_records(s3, monkeypatch):
    monkeypatch.setattr(byo, "org_entitled", lambda _s, _o: False)
    client = _saved_client()
    meta = byo.put_org_file(client, _settings(**ON), org_id=ORG, logical_bucket="chat-artifacts",
                            path=f"{ORG}/x.html", data=b"<p>", content_type="text/html", purpose="chat_artifact")
    assert s3.calls == [] and client.uploads[0]["bucket"] == "chat-artifacts"
    assert meta["storage_location"] == "supabase"
    assert client.tables["org_file_objects"][0]["location"] == "supabase"


def test_chat_hosted_file_gets_presigned_link_from_own_bucket(s3, entitled):
    client = _saved_client()
    out = ChatHostedFileService().persist_html_chart(
        client, _settings(**ON), org_id=ORG, title="Chart", preview_html="<p>x</p>", code="",
    )
    hosted = out["hostedFiles"][0]
    assert hosted["download_url"].startswith("https://s3.test/acme-files/gravitre/prod/chat-artifacts/")
    assert hosted["durable"] is True
    assert [c[0] for c in s3.calls] == ["put", "presign"]


# --------------------------------------------------------------------------- reads


def test_read_without_record_resolves_to_supabase():
    client = FakeClient()
    out = byo.resolve_download_url(client, _settings(), org_id=ORG, logical_bucket="rag-uploads", path=f"{ORG}/a.pdf")
    assert out["location"] == "supabase" and out["url"].startswith("https://supabase.test/rag-uploads/")


def test_read_resolves_from_own_bucket_even_after_flag_off(s3, entitled):
    client = _saved_client()
    byo.put_org_file(client, _settings(**ON), org_id=ORG, logical_bucket="rag-uploads",
                     path=f"{ORG}/a.pdf", data=b"%PDF", content_type="application/pdf", purpose="rag_upload")
    out = byo.resolve_download_url(client, _settings(), org_id=ORG, logical_bucket="rag-uploads", path=f"{ORG}/a.pdf")
    assert out["location"] == "byo"
    assert out["url"].startswith("https://s3.test/acme-files/gravitre/prod/rag-uploads/")


def test_read_from_removed_target_says_so(s3, entitled):
    client = _saved_client()
    byo.put_org_file(client, _settings(**ON), org_id=ORG, logical_bucket="rag-uploads",
                     path=f"{ORG}/a.pdf", data=b"%PDF", content_type=None, purpose="rag_upload")
    assert byo.delete_target(client, ORG) is True
    with pytest.raises(byo.ByoStorageUnavailableError):
        byo.resolve_download_url(client, _settings(), org_id=ORG, logical_bucket="rag-uploads", path=f"{ORG}/a.pdf")


def test_read_of_another_orgs_path_is_refused():
    with pytest.raises(byo.ByoStorageError):
        byo.resolve_download_url(FakeClient(), _settings(), org_id=ORG, logical_bucket="rag-uploads",
                                 path=f"{OTHER}/a.pdf")
    with pytest.raises(byo.ByoStorageError):
        byo.resolve_download_url(FakeClient(), _settings(), org_id=ORG, logical_bucket="rag-uploads",
                                 path=f"{ORG}/../{OTHER}/a.pdf")


# --------------------------------------------------------------------------- probe


def test_probe_puts_heads_and_deletes_then_verifies(s3):
    client = _saved_client("untested")
    out = byo.probe_target(client, _settings(), ORG)
    assert out["ok"] is True and out["steps"] == {"put": True, "head": True, "delete": True}
    assert [c[0] for c in s3.calls] == ["put", "head", "delete"]
    assert s3.calls[0][2].startswith("gravitre/prod/.gravitre-probe/")
    assert s3.objects == {}
    assert client.tables["org_storage_targets"][0]["status"] == "verified"


def test_probe_failure_marks_failed_without_leaking(monkeypatch):
    fake = FakeS3(fail_on="head")
    monkeypatch.setattr(byo, "s3_client", lambda _s, _r: fake)
    client = _saved_client("verified")
    out = byo.probe_target(client, _settings(), ORG)
    assert out["ok"] is False and out["steps"] == {"put": True, "head": False, "delete": False}
    assert out["error"] == "The storage service answered AccessDenied."
    assert "secret-should-not-leak" not in str(out)
    assert client.tables["org_storage_targets"][0]["status"] == "failed"


def test_real_client_is_built_with_decrypted_credentials(monkeypatch):
    built = {}

    import boto3

    monkeypatch.setattr(boto3, "client", lambda *a, **k: built.update(k) or "client")
    row = _saved_client().tables["org_storage_targets"][0]
    assert byo.s3_client(_settings(), row) == "client"
    assert built["aws_access_key_id"] == ACCESS_KEY and built["aws_secret_access_key"] == SECRET
    assert built["endpoint_url"] == "https://8.8.8.8" and built["region_name"] == "us-east-1"


# --------------------------------------------------------------------------- API


@pytest.fixture
def api(monkeypatch):
    client = FakeClient()
    import app.routers.storage_settings as routes

    monkeypatch.setattr(routes, "shared_service_client", lambda *_a, **_k: client)
    monkeypatch.setattr(routes, "write_audit_event", lambda *a, **k: client.calls.append(("audit", k)))
    yield TestClient(app), client
    app.dependency_overrides.clear()


def _auth(settings: Settings) -> None:
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1", "email": "u@example.com"}
    app.dependency_overrides[get_org_context] = lambda: ORG
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[require_admin] = lambda: ({"user_id": "user-1"}, ORG)


def test_api_not_entitled_is_unavailable_and_refuses_writes(api, monkeypatch):
    http, client = api
    monkeypatch.setattr(byo, "org_entitled", lambda _s, _o: False)
    _auth(_settings(**ON))
    body = http.get("/api/settings/storage/byo").json()
    assert body["available"] is False and body["entitled"] is False and body["target"] is None
    assert "stay in Gravitre's database" in body["scope"]
    assert http.put("/api/settings/storage/byo", json=BODY).status_code == 403
    assert http.post("/api/settings/storage/byo/test").status_code == 403
    assert client.tables.get("org_storage_targets", []) == []


def test_api_flag_off_refuses_writes_even_when_entitled(api, entitled):
    http, _client = api
    _auth(_settings())
    assert http.get("/api/settings/storage/byo").json()["available"] is False
    res = http.put("/api/settings/storage/byo", json=BODY)
    assert res.status_code == 403


def test_api_save_test_and_remove(api, entitled, s3, caplog):
    http, client = api
    _auth(_settings(**ON))
    caplog.set_level(logging.DEBUG)
    res = http.put("/api/settings/storage/byo", json=BODY)
    assert res.status_code == 200, res.text
    assert SECRET not in res.text and ACCESS_KEY not in res.text
    assert res.json()["target"]["status"] == "untested"
    tested = http.post("/api/settings/storage/byo/test")
    assert tested.status_code == 200 and tested.json()["ok"] is True
    assert tested.json()["target"]["status"] == "verified"
    got = http.get("/api/settings/storage/byo").json()
    assert got["available"] is True and got["target"]["bucket"] == "acme-files"
    audits = [c[1] for c in client.calls if c[0] == "audit"]
    assert [a["action"] for a in audits] == ["storage.byo_target.saved", "storage.byo_target.tested"]
    assert SECRET not in str(audits) and ACCESS_KEY not in str(audits)
    assert http.delete("/api/settings/storage/byo").json() == {"removed": True}
    assert SECRET not in caplog.text and ACCESS_KEY not in caplog.text


def test_api_validation_error_is_a_400(api, entitled):
    http, _client = api
    _auth(_settings(**ON))
    res = http.put("/api/settings/storage/byo", json={**BODY, "endpointUrl": "http://insecure.example.com"})
    assert res.status_code == 400


def test_api_download_url_only_for_known_buckets_and_own_paths(api):
    http, _client = api
    _auth(_settings())
    ok = http.get("/api/settings/storage/files/download-url", params={"bucket": "rag-uploads", "path": f"{ORG}/a.pdf"})
    assert ok.status_code == 200 and ok.json()["location"] == "supabase"
    assert http.get("/api/settings/storage/files/download-url",
                    params={"bucket": "audit-archive", "path": f"{ORG}/a"}).status_code == 404
    assert http.get("/api/settings/storage/files/download-url",
                    params={"bucket": "rag-uploads", "path": f"{OTHER}/a.pdf"}).status_code == 404
