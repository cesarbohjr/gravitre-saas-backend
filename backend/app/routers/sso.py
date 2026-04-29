from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from onelogin.saml2.auth import OneLogin_Saml2_Auth
from onelogin.saml2.settings import OneLogin_Saml2_Settings
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context
from app.config import Settings, get_settings
from app.middleware.entitlements import require_feature

router = APIRouter(prefix="/api/auth/sso", tags=["sso"])


def _is_missing_table_error(error: Exception | None) -> bool:
    if error is None:
        return False
    return "does not exist" in str(error).lower()


def _assert_org_admin(client, org_id: str, user_id: str) -> None:
    membership = (
        client.table("organization_members")
        .select("role")
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if membership.error:
        raise HTTPException(status_code=500, detail=str(membership.error))
    if not membership.data:
        raise HTTPException(status_code=403, detail="Not a member of this organization")
    role = str(membership.data[0].get("role") or "").strip().lower()
    if role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Admin role required")


def _normalize_cert(certificate: str | None) -> str:
    if not certificate:
        return ""
    cert = certificate.strip()
    if "BEGIN CERTIFICATE" in cert:
        cert = (
            cert.replace("-----BEGIN CERTIFICATE-----", "")
            .replace("-----END CERTIFICATE-----", "")
            .replace("\r", "")
            .replace("\n", "")
            .strip()
        )
    return cert


def _external_base_url(settings: Settings, request: Request | None = None) -> str:
    configured = (settings.public_app_url or "").strip().rstrip("/")
    if configured:
        return configured
    if request is None:
        return "http://localhost:3000"

    proto = request.headers.get("x-forwarded-proto") or request.url.scheme or "http"
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return f"{proto}://{host}".rstrip("/")


def _saml_settings_data(config: dict[str, Any], settings: Settings, request: Request | None = None) -> dict[str, Any]:
    base_url = _external_base_url(settings, request)
    acs_url = f"{base_url}/api/auth/sso/callback"
    metadata_url = f"{base_url}/api/auth/sso/metadata"
    cert = _normalize_cert(config.get("saml_certificate"))

    idp_block: dict[str, Any] = {
        "entityId": config["saml_entity_id"],
        "singleSignOnService": {
            "url": config["saml_sso_url"],
            "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
        },
        "x509cert": cert,
    }
    if config.get("saml_slo_url"):
        idp_block["singleLogoutService"] = {
            "url": config["saml_slo_url"],
            "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
        }

    return {
        "strict": True,
        "debug": False,
        "sp": {
            "entityId": metadata_url,
            "assertionConsumerService": {
                "url": acs_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
            },
            "singleLogoutService": {
                "url": acs_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "NameIDFormat": config.get("saml_name_id_format")
            or "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
            "x509cert": "",
            "privateKey": "",
        },
        "idp": idp_block,
        "security": {
            "authnRequestsSigned": False,
            "wantAssertionsSigned": True,
            "wantMessagesSigned": True,
            "wantNameIdEncrypted": False,
            "wantAssertionsEncrypted": False,
        },
    }


def _build_saml_request_data(request: Request, form_data: dict[str, Any] | None = None) -> dict[str, Any]:
    port = request.url.port or (443 if request.url.scheme == "https" else 80)
    get_data = {k: v for k, v in request.query_params.items()}
    post_data = form_data or {}
    return {
        "https": "on" if request.url.scheme == "https" else "off",
        "http_host": request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.hostname,
        "server_port": str(port),
        "script_name": request.url.path,
        "get_data": get_data,
        "post_data": post_data,
    }


class SSOConfigurationCreate(BaseModel):
    provider_type: str = Field(..., pattern="^(saml|oidc)$")
    saml_entity_id: str | None = None
    saml_sso_url: str | None = None
    saml_slo_url: str | None = None
    saml_certificate: str | None = None
    oidc_issuer: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None
    oidc_authorization_endpoint: str | None = None
    oidc_token_endpoint: str | None = None
    oidc_userinfo_endpoint: str | None = None
    auto_provision_users: bool = True
    default_role: str = "member"
    allowed_domains: list[str] | None = None
    attribute_mapping: dict[str, str] | None = None


class SSOConfigurationResponse(BaseModel):
    id: str
    org_id: str
    provider_type: str
    is_enabled: bool
    saml_entity_id: str | None
    saml_sso_url: str | None
    oidc_issuer: str | None
    oidc_client_id: str | None
    auto_provision_users: bool
    default_role: str
    allowed_domains: list[str] | None
    created_at: str


class SSOInitResponse(BaseModel):
    redirect_url: str
    state: str


@router.get("/config")
async def get_sso_config(
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    _feature: Annotated[dict[str, Any], Depends(require_feature("sso_saml"))],
) -> SSOConfigurationResponse | None:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    result = client.table("sso_configurations").select("*").eq("org_id", org_id).limit(1).execute()
    if _is_missing_table_error(result.error):
        return None
    if result.error:
        raise HTTPException(status_code=500, detail=str(result.error))
    if not result.data:
        return None
    config = result.data[0]
    return SSOConfigurationResponse(
        id=str(config["id"]),
        org_id=str(config["org_id"]),
        provider_type=config["provider_type"],
        is_enabled=bool(config.get("is_enabled") or False),
        saml_entity_id=config.get("saml_entity_id"),
        saml_sso_url=config.get("saml_sso_url"),
        oidc_issuer=config.get("oidc_issuer"),
        oidc_client_id=config.get("oidc_client_id"),
        auto_provision_users=bool(config.get("auto_provision_users", True)),
        default_role=config.get("default_role") or "member",
        allowed_domains=config.get("allowed_domains"),
        created_at=config["created_at"],
    )


@router.post("/config")
async def create_or_update_sso_config(
    data: SSOConfigurationCreate,
    org_id: Annotated[str | None, Depends(get_org_context)],
    user: Annotated[dict[str, Any], Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
    _feature: Annotated[dict[str, Any], Depends(require_feature("sso_saml"))],
) -> SSOConfigurationResponse:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    _assert_org_admin(client, org_id, user["user_id"])

    if data.provider_type == "saml":
        if not data.saml_entity_id or not data.saml_sso_url or not data.saml_certificate:
            raise HTTPException(status_code=400, detail="SAML requires entity_id, sso_url, and certificate")
    else:
        if not data.oidc_issuer or not data.oidc_client_id or not data.oidc_client_secret:
            raise HTTPException(status_code=400, detail="OIDC requires issuer, client_id, and client_secret")

    config_data = {
        "org_id": org_id,
        "provider_type": data.provider_type,
        "saml_entity_id": data.saml_entity_id,
        "saml_sso_url": data.saml_sso_url,
        "saml_slo_url": data.saml_slo_url,
        "saml_certificate": data.saml_certificate,
        "oidc_issuer": data.oidc_issuer,
        "oidc_client_id": data.oidc_client_id,
        "oidc_client_secret": data.oidc_client_secret,
        "oidc_authorization_endpoint": data.oidc_authorization_endpoint,
        "oidc_token_endpoint": data.oidc_token_endpoint,
        "oidc_userinfo_endpoint": data.oidc_userinfo_endpoint,
        "auto_provision_users": data.auto_provision_users,
        "default_role": data.default_role,
        "allowed_domains": data.allowed_domains,
        "attribute_mapping": data.attribute_mapping
        or {"email": "email", "first_name": "firstName", "last_name": "lastName", "groups": "groups"},
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    owner_lookup = (
        client.table("users")
        .select("id")
        .eq("org_id", org_id)
        .eq("auth_user_id", user["user_id"])
        .limit(1)
        .execute()
    )
    if not owner_lookup.error and owner_lookup.data:
        config_data["created_by"] = owner_lookup.data[0].get("id")

    result = client.table("sso_configurations").upsert(config_data, on_conflict="org_id").execute()
    if _is_missing_table_error(result.error):
        raise HTTPException(status_code=500, detail="SSO tables are missing. Run migrations first.")
    if result.error:
        raise HTTPException(status_code=500, detail=str(result.error))
    config = result.data[0]
    return SSOConfigurationResponse(
        id=str(config["id"]),
        org_id=str(config["org_id"]),
        provider_type=config["provider_type"],
        is_enabled=bool(config.get("is_enabled") or False),
        saml_entity_id=config.get("saml_entity_id"),
        saml_sso_url=config.get("saml_sso_url"),
        oidc_issuer=config.get("oidc_issuer"),
        oidc_client_id=config.get("oidc_client_id"),
        auto_provision_users=bool(config.get("auto_provision_users", True)),
        default_role=config.get("default_role") or "member",
        allowed_domains=config.get("allowed_domains"),
        created_at=config["created_at"],
    )


@router.post("/config/enable")
async def enable_sso(
    org_id: Annotated[str | None, Depends(get_org_context)],
    user: Annotated[dict[str, Any], Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
    _feature: Annotated[dict[str, Any], Depends(require_feature("sso_saml"))],
) -> dict[str, bool]:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    _assert_org_admin(client, org_id, user["user_id"])
    result = (
        client.table("sso_configurations")
        .update({"is_enabled": True, "updated_at": datetime.now(timezone.utc).isoformat()})
        .eq("org_id", org_id)
        .execute()
    )
    if _is_missing_table_error(result.error):
        raise HTTPException(status_code=500, detail="SSO tables are missing. Run migrations first.")
    if result.error:
        raise HTTPException(status_code=500, detail=str(result.error))
    if not result.data:
        raise HTTPException(status_code=404, detail="SSO not configured")
    return {"enabled": True}


@router.post("/config/disable")
async def disable_sso(
    org_id: Annotated[str | None, Depends(get_org_context)],
    user: Annotated[dict[str, Any], Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
    _feature: Annotated[dict[str, Any], Depends(require_feature("sso_saml"))],
) -> dict[str, bool]:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    _assert_org_admin(client, org_id, user["user_id"])
    result = (
        client.table("sso_configurations")
        .update({"is_enabled": False, "updated_at": datetime.now(timezone.utc).isoformat()})
        .eq("org_id", org_id)
        .execute()
    )
    if _is_missing_table_error(result.error):
        raise HTTPException(status_code=500, detail="SSO tables are missing. Run migrations first.")
    if result.error:
        raise HTTPException(status_code=500, detail=str(result.error))
    return {"enabled": False}


@router.delete("/config")
async def delete_sso_config(
    org_id: Annotated[str | None, Depends(get_org_context)],
    user: Annotated[dict[str, Any], Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
    _feature: Annotated[dict[str, Any], Depends(require_feature("sso_saml"))],
) -> dict[str, str]:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    _assert_org_admin(client, org_id, user["user_id"])
    result = client.table("sso_configurations").delete().eq("org_id", org_id).execute()
    if _is_missing_table_error(result.error):
        raise HTTPException(status_code=500, detail="SSO tables are missing. Run migrations first.")
    if result.error:
        raise HTTPException(status_code=500, detail=str(result.error))
    return {"status": "deleted"}


@router.get("/metadata")
async def saml_metadata(
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    request: Request,
    _feature: Annotated[dict[str, Any], Depends(require_feature("sso_saml"))],
) -> Response:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    result = client.table("sso_configurations").select("*").eq("org_id", org_id).limit(1).execute()
    if result.error or not result.data:
        raise HTTPException(status_code=404, detail="SSO configuration not found")
    config = result.data[0]
    if config.get("provider_type") != "saml":
        raise HTTPException(status_code=400, detail="SAML configuration is not active for this organization")
    settings_data = _saml_settings_data(config, settings, request)
    saml_settings = OneLogin_Saml2_Settings(settings_data, None, True)
    metadata_xml = saml_settings.get_sp_metadata()
    errors = saml_settings.validate_metadata(metadata_xml)
    if errors:
        raise HTTPException(status_code=500, detail=f"Invalid SP metadata: {', '.join(errors)}")
    return Response(content=metadata_xml, media_type="application/samlmetadata+xml")


@router.post("/init")
async def init_sso(
    request: Request,
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SSOInitResponse:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    result = (
        client.table("sso_configurations")
        .select("*")
        .eq("org_id", org_id)
        .eq("is_enabled", True)
        .limit(1)
        .execute()
    )
    if _is_missing_table_error(result.error):
        raise HTTPException(status_code=404, detail="SSO not configured or disabled")
    if result.error:
        raise HTTPException(status_code=500, detail=str(result.error))
    if not result.data:
        raise HTTPException(status_code=404, detail="SSO not configured or disabled")
    config = result.data[0]

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(16) if config["provider_type"] == "oidc" else None
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    session_insert = (
        client.table("sso_sessions")
        .insert(
            {
                "org_id": org_id,
                "state": state,
                "nonce": nonce,
                "relay_state": str(request.headers.get("referer", "/")),
                "expires_at": expires_at.isoformat(),
            }
        )
        .execute()
    )
    if _is_missing_table_error(session_insert.error):
        raise HTTPException(status_code=500, detail="SSO tables are missing. Run migrations first.")
    if session_insert.error:
        raise HTTPException(status_code=500, detail=str(session_insert.error))

    if config["provider_type"] == "saml":
        redirect_url = _build_saml_authn_request(request, config, state, settings)
    else:
        redirect_url = _build_oidc_auth_url(config, state, nonce or "", settings)
    return SSOInitResponse(redirect_url=redirect_url, state=state)


@router.api_route("/callback", methods=["GET", "POST"])
async def sso_callback(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> RedirectResponse:
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)

    form_payload: dict[str, Any] = {}
    if request.method.upper() == "POST":
        form_payload = {k: v for k, v in (await request.form()).items()}

    state = (
        request.query_params.get("state")
        or request.query_params.get("RelayState")
        or str(form_payload.get("RelayState") or "")
    )
    if not state:
        raise HTTPException(status_code=400, detail="Missing state parameter")

    session_result = client.table("sso_sessions").select("*").eq("state", state).limit(1).execute()
    if session_result.error:
        raise HTTPException(status_code=500, detail=str(session_result.error))
    if not session_result.data:
        raise HTTPException(status_code=400, detail="Invalid or expired session")
    session = session_result.data[0]

    expires_at = datetime.fromisoformat(str(session["expires_at"]).replace("Z", "+00:00"))
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Session expired")

    config_result = (
        client.table("sso_configurations").select("*").eq("org_id", session["org_id"]).limit(1).execute()
    )
    if config_result.error:
        raise HTTPException(status_code=500, detail=str(config_result.error))
    if not config_result.data:
        raise HTTPException(status_code=400, detail="SSO configuration not found")
    config = config_result.data[0]

    if config["provider_type"] == "saml":
        user_info = await _process_saml_response(request, form_payload, config, settings)
    else:
        code = request.query_params.get("code")
        if not code:
            raise HTTPException(status_code=400, detail="Missing authorization code")
        user_info = await _process_oidc_callback(code, config, session.get("nonce"), settings)

    await _provision_user(client, user_info, config, str(session["org_id"]))
    client.table("sso_sessions").delete().eq("id", session["id"]).execute()
    return RedirectResponse(url=session.get("relay_state") or "/", status_code=302)


def _build_saml_authn_request(request: Request, config: dict[str, Any], state: str, settings: Settings) -> str:
    request_data = _build_saml_request_data(request)
    saml_settings = _saml_settings_data(config, settings, request)
    auth = OneLogin_Saml2_Auth(request_data, old_settings=saml_settings)
    callback_url = f"{_external_base_url(settings, request)}/api/auth/sso/callback?state={state}"
    return auth.login(return_to=callback_url)


def _build_oidc_auth_url(config: dict[str, Any], state: str, nonce: str, settings: Settings) -> str:
    app_base = _external_base_url(settings)
    redirect_uri = f"{app_base}/api/auth/sso/callback"
    params = {
        "client_id": config["oidc_client_id"],
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": config.get("oidc_scopes") or "openid email profile",
        "state": state,
        "nonce": nonce,
    }
    auth_endpoint = config.get("oidc_authorization_endpoint") or f"{config['oidc_issuer'].rstrip('/')}/authorize"
    from urllib.parse import urlencode
    return f"{auth_endpoint}?{urlencode(params)}"


async def _process_saml_response(
    request: Request,
    form_payload: dict[str, Any],
    config: dict[str, Any],
    settings: Settings,
) -> dict[str, Any]:
    request_data = _build_saml_request_data(request, form_payload)
    saml_settings = _saml_settings_data(config, settings, request)
    auth = OneLogin_Saml2_Auth(request_data, old_settings=saml_settings)
    auth.process_response()

    errors = auth.get_errors()
    if errors:
        raise HTTPException(status_code=400, detail=f"Invalid SAML response: {', '.join(errors)}")
    if not auth.is_authenticated():
        raise HTTPException(status_code=401, detail="SAML authentication failed")

    attributes = auth.get_attributes() or {}
    flat_attributes: dict[str, Any] = {}
    for key, values in attributes.items():
        if isinstance(values, list):
            flat_attributes[key] = values[0] if values else ""
        else:
            flat_attributes[key] = values

    name_id = auth.get_nameid()
    if name_id:
        flat_attributes.setdefault("email", name_id)
        flat_attributes.setdefault("name_id", name_id)
    flat_attributes.setdefault("firstName", "")
    flat_attributes.setdefault("lastName", "")
    return flat_attributes


async def _process_oidc_callback(
    code: str,
    config: dict[str, Any],
    nonce: str | None,
    settings: Settings,
) -> dict[str, Any]:
    app_base = _external_base_url(settings)
    redirect_uri = f"{app_base}/api/auth/sso/callback"
    token_endpoint = config.get("oidc_token_endpoint") or f"{config['oidc_issuer'].rstrip('/')}/token"
    userinfo_endpoint = config.get("oidc_userinfo_endpoint") or f"{config['oidc_issuer'].rstrip('/')}/userinfo"

    async with httpx.AsyncClient(timeout=20) as http:
        token_response = await http.post(
            token_endpoint,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": config["oidc_client_id"],
                "client_secret": config["oidc_client_secret"],
            },
        )
        if token_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to exchange code for tokens")
        tokens = token_response.json()
        access_token = tokens.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="OIDC provider returned no access token")
        userinfo_response = await http.get(
            userinfo_endpoint,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if userinfo_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get user info")
        user_info = userinfo_response.json()
        if nonce and tokens.get("nonce") and tokens.get("nonce") != nonce:
            raise HTTPException(status_code=400, detail="Invalid OIDC nonce")
        return user_info


async def _provision_user(client, user_info: dict[str, Any], config: dict[str, Any], org_id: str) -> dict[str, Any]:
    mapping = config.get("attribute_mapping") or {}
    email = user_info.get(mapping.get("email", "email"))
    if not email:
        raise HTTPException(status_code=400, detail="Email not found in SSO response")

    allowed_domains = config.get("allowed_domains")
    if allowed_domains:
        domain = email.split("@")[1] if "@" in email else ""
        if domain not in allowed_domains:
            raise HTTPException(status_code=403, detail="Email domain not allowed")

    first_name = user_info.get(mapping.get("first_name", "given_name"), "")
    last_name = user_info.get(mapping.get("last_name", "family_name"), "")
    full_name = f"{first_name} {last_name}".strip()

    existing = client.table("users").select("*").eq("org_id", org_id).eq("email", email).limit(1).execute()
    if existing.error:
        raise HTTPException(status_code=500, detail=str(existing.error))
    if existing.data:
        user = existing.data[0]
        update_payload = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if full_name:
            update_payload["full_name"] = full_name
        update_result = client.table("users").update(update_payload).eq("id", user["id"]).execute()
        if update_result.error:
            raise HTTPException(status_code=500, detail=str(update_result.error))
        return user

    if not config.get("auto_provision_users", True):
        raise HTTPException(status_code=403, detail="User not found and auto-provisioning is disabled")

    auth_created = client.auth.admin.create_user(
        {"email": email, "email_confirm": True, "user_metadata": {"name": full_name} if full_name else {}}
    )
    auth_user = getattr(auth_created, "user", None)
    auth_user_id = getattr(auth_user, "id", None)
    if not auth_user_id:
        raise HTTPException(status_code=500, detail="Failed to provision auth user")

    create_user_result = (
        client.table("users")
        .insert(
            {
                "org_id": org_id,
                "auth_user_id": auth_user_id,
                "email": email,
                "full_name": full_name or None,
                "role": config.get("default_role", "member"),
            }
        )
        .execute()
    )
    if create_user_result.error:
        raise HTTPException(status_code=500, detail=str(create_user_result.error))

    member_result = (
        client.table("organization_members")
        .upsert(
            {"org_id": org_id, "user_id": auth_user_id, "role": config.get("default_role", "member")},
            on_conflict="org_id,user_id",
        )
        .execute()
    )
    if member_result.error:
        raise HTTPException(status_code=500, detail=str(member_result.error))
    return create_user_result.data[0]
