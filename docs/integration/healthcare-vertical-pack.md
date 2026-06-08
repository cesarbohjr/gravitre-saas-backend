# Healthcare vertical pack (STA-113)

Industry pack for healthcare teams: FHIR read tools, clinical admin and patient services agent templates, and a prior authorization workflow.

## Prerequisites

- [HIPAA controls (STA-110)](./agent-hipaa-controls.md) — FHIR connectors are **PHI-capable**; enable HIPAA mode with accepted BAA before production PHI.

## Install

```http
POST /api/verticals/healthcare/install
Authorization: Bearer <admin-token>
```

Installs:

| Asset | Description |
|-------|-------------|
| FHIR Sandbox connector | HAPI FHIR R4 public sandbox (`phi_capable: true`) |
| Clinical Admin Agent | Prior auth and clinical documentation |
| Patient Services Agent | Scheduling and referral intake (CS) |
| Prior auth workflow | Referral → FHIR lookup → clinical review → checklist |

```http
GET /api/verticals/healthcare
```

Returns install status and stable resource IDs.

## FHIR tools

| Action | Description |
|--------|-------------|
| `fhir.patients.get` | Read patient by id |
| `fhir.patients.search` | Search patients by name, birthdate, identifier |
| `fhir.appointments.search` | List appointments for a patient |
| `fhir.prior_auth.checklist` | Generate prior authorization checklist |

Connectors use vendor `fhir` with optional `base_url` and bearer token for non-sandbox EHR endpoints.

## Workflow parameters

Execute the prior auth workflow with:

| Parameter | Example |
|-----------|---------|
| `patient_name` | `Smith` |
| `patient_birthdate` | `1970-01-01` |
| `patient_id` | FHIR patient id (after search) |
| `referral_reason` | `Cardiology referral` |
| `payer` | `Medicare` |

## Related

- STA-110 HIPAA BAA + PHI controls
- STA-112 EU AI Act transparency logs (autonomous clinical decisions)
