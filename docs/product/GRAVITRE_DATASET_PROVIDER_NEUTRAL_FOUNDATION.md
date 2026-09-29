# Gravitre external dataset sources — provider-neutral foundation

Date: 2026-09-29
Branch: `feat/gravitre-dataset-providers`

## Scope

This phase starts the external dataset-provider architecture only after the
Play/Outcome foundation reached production merge.

It does **not** integrate a named external provider.

## Architecture

External sources extend existing `training_datasets`.

They do not create a second dataset product.

Canonical chain:

EXTERNAL SOURCE REFERENCE
→ EXISTING TRAINING DATASET
→ PURPOSE BINDING
→ AGENT / MODEL / DEPARTMENT / EVALUATION / PLAY / WORKFLOW

## Access modes

The provider-neutral source contract supports:

- REFERENCE — keep the source remote and use identity/provenance only.
- SAMPLE — fetch only a bounded sample when a future adapter is available.
- INDEX — maintain retrieval/index metadata without full materialization.
- MATERIALIZE — copy content into Gravitre only when explicitly required.

Reference/index should remain preferred over full materialization.

## Storage

`training_dataset_sources` contains:

- tenant/org id;
- existing dataset id;
- provider slug;
- provider resource locator;
- optional revision;
- access mode;
- status;
- license/provenance metadata;
- non-secret source metadata.

Credentials and tokens are explicitly forbidden from this table.

## API foundation

Existing Training API gains:

- `GET /api/training/datasets/{dataset_id}/sources`
- `POST /api/training/datasets/{dataset_id}/sources`

Registration is metadata-only.

It does not:

- call a provider;
- download a dataset;
- materialize records;
- create an index;
- start a training job.

The POST response explicitly returns:

- `providerNeutral: true`
- `credentialsStored: false`
- `fetchStarted: false`

## Provider implementation gate

A named provider adapter remains blocked until:

1. production backend deploy of the Play APIs is complete;
2. live read-only Play route proof is attempted;
3. if authentication is unavailable, status is recorded exactly as
   `BLOCKED: NO AUTHORIZED SESSION`;
4. provider adapter tests demonstrate bounded sample/reference behavior before
   any materialization path.

## Result

PROVIDER_NEUTRAL_DATASET_SOURCE_CONTRACT = IMPLEMENTED FOUNDATION

NAMED_PROVIDER_ADAPTER = NOT STARTED

AUTOMATIC_MATERIALIZATION = NO
