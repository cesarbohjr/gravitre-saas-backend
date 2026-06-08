"""FHIR read tools + prior-auth checklist builder (STA-113)."""
from __future__ import annotations

from typing import Any

from app.connectors.fhir import (
    FhirAPIError,
    get_patient,
    search_appointments,
    search_patients,
    resolve_fhir_session,
)
from app.connectors.rate_limit import enforce_rate_limit
from app.services.tool_types import (
    NormalizedResult,
    ToolAuthExpiredError,
    ToolContext,
    ToolRateLimitedError,
    ToolValidationError,
)

PRIOR_AUTH_CHECKLIST_ITEMS = [
    "Verify patient demographics and insurance on file",
    "Confirm referring provider NPI and specialty",
    "Collect clinical indication and ICD-10 codes",
    "Attach recent visit notes and diagnostic results",
    "Document conservative therapy attempts when required",
    "Submit authorization to payer portal or clearinghouse",
    "Track authorization number and effective dates",
]


def _handle_error(exc: FhirAPIError) -> Exception:
    if exc.status_code == 429:
        return ToolRateLimitedError(str(exc))
    if exc.status_code in {401, 403}:
        return ToolAuthExpiredError(str(exc))
    return ToolValidationError(str(exc))


def _session(ctx: ToolContext, params: dict[str, Any]) -> tuple[str, str, str | None]:
    if ctx.settings.disable_connectors:
        raise ToolValidationError("Connectors are disabled")
    connector_id = params.get("connector_id") or ctx.connector_id
    try:
        cid, base_url, token = resolve_fhir_session(
            ctx.client,
            ctx.org_id,
            str(connector_id) if connector_id else None,
            ctx.settings,
            environment_name=ctx.environment_name,
        )
    except FhirAPIError as exc:
        raise _handle_error(exc) from exc
    enforce_rate_limit(ctx.client, ctx.org_id, "fhir", "fhir", cid)
    return cid, base_url, token


def _first_patient_id(bundle: dict[str, Any]) -> str | None:
    for entry in bundle.get("entry") or []:
        resource = entry.get("resource") if isinstance(entry, dict) else None
        if isinstance(resource, dict) and resource.get("resourceType") == "Patient":
            pid = resource.get("id")
            if pid:
                return str(pid)
    return None


def _exec_fhir_patients_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, base_url, token = _session(ctx, params)
    patient_id = params.get("patient_id") or params.get("patientId")
    if not patient_id:
        raise ToolValidationError("fhir.patients.get requires patient_id")
    try:
        data = get_patient(base_url, str(patient_id), token=token)
    except FhirAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="fhir.patients.get", connector_id=cid, data={"patient": data})


def _exec_fhir_patients_search(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, base_url, token = _session(ctx, params)
    try:
        data = search_patients(
            base_url,
            token=token,
            name=params.get("name"),
            birthdate=params.get("birthdate") or params.get("birthDate"),
            identifier=params.get("identifier"),
            count=int(params.get("count") or 10),
        )
    except FhirAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="fhir.patients.search", connector_id=cid, data={"bundle": data})


def _exec_fhir_appointments_search(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, base_url, token = _session(ctx, params)
    patient_id = params.get("patient_id") or params.get("patientId")
    if not patient_id:
        raise ToolValidationError("fhir.appointments.search requires patient_id")
    try:
        data = search_appointments(
            base_url,
            token=token,
            patient_id=str(patient_id),
            date=params.get("date"),
            status=params.get("status"),
            count=int(params.get("count") or 10),
        )
    except FhirAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="fhir.appointments.search",
        connector_id=cid,
        data={"bundle": data},
    )


def _exec_fhir_prior_auth_checklist(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, _, _ = _session(ctx, params)
    referral_reason = str(params.get("referral_reason") or params.get("referralReason") or "Specialist referral")
    payer = str(params.get("payer") or "Primary payer")
    patient_id = params.get("patient_id") or params.get("patientId")
    checklist = [
        {
            "id": f"item-{idx + 1}",
            "title": item,
            "completed": False,
            "required": True,
        }
        for idx, item in enumerate(PRIOR_AUTH_CHECKLIST_ITEMS)
    ]
    return NormalizedResult(
        success=True,
        action="fhir.prior_auth.checklist",
        connector_id=cid,
        data={
            "referralReason": referral_reason,
            "payer": payer,
            "patientId": patient_id,
            "checklist": checklist,
            "status": "draft",
            "hipaaNote": "Enable HIPAA mode before running against production PHI systems.",
        },
    )


FHIR_TOOL_EXECUTORS: dict[str, Any] = {
    "fhir.patients.get": _exec_fhir_patients_get,
    "fhir.patients.search": _exec_fhir_patients_search,
    "fhir.appointments.search": _exec_fhir_appointments_search,
    "fhir.prior_auth.checklist": _exec_fhir_prior_auth_checklist,
}
