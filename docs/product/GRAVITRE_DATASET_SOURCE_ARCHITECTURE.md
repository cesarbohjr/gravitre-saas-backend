# Gravitre dataset-source architecture — provider-neutral foundation

Date: 2026-09-29
Branch: `feat/gravitre-dataset-sources`

## Purpose

Phase 13 begins with a provider-neutral external dataset-source layer inside the
existing Model Studio / training-dataset product.

This is not a new dataset product and does not replace `training_datasets`,
`training_records`, training jobs, ML model registry, or dataset purpose
bindings.

## Contract

External sources attach to an existing `training_dataset` and record:

- provider identifier;
- external dataset identifier;
- optional display name/source URI;
- optional non-secret connection reference;
- access mode;
- optional sample limit;
- materialization state;
- metadata/provenance.

Supported access modes:

- REFERENCE
- INDEX
- SAMPLE
- MATERIALIZED

REFERENCE / INDEX / SAMPLE are preferred. MATERIALIZED is explicit.

## Security / governance

The source table is tenant scoped with RLS.

It stores no:

- provider access token;
- refresh token;
- client secret;
- API key;
- embedded credential.

Source creation requires admin authorization. Read access follows authenticated
org context.

There is no automatic bulk download.

## Provider neutrality

No provider-specific adapter exists in this phase.

The contract accepts an opaque provider identifier and external id. The same
contract can later support providers such as Hugging Face, Kaggle, internal
catalogs, or partner datasets without altering the core schema.

Provider-specific OAuth/API handling belongs in adapters added after this
contract is live-proven.

## Model Studio

External source references are inspected inside Model Studio's existing Train
surface.

There is no new navigation product or parallel dataset workspace.

The UI is read-only for source inspection in this phase. Provider-specific
search/import UX is deferred.

## Live-proof dependency

The first Plays read-only API live proof still requires an authorized user
session. No auth bypass will be introduced to manufacture that proof.

This provider-neutral foundation is independent and non-destructive; no
provider integration or external data download is enabled by it.

## Result

PROVIDER_NEUTRAL_DATASET_SOURCE_CONTRACT = IMPLEMENTED

PROVIDER_SPECIFIC_ADAPTER = NOT_STARTED

HUGGING_FACE_INTEGRATION = NOT_STARTED

AUTOMATIC_MATERIALIZATION = DISABLED
