# Gravitre Plays / Outcomes — Dataset and Model Studio audit

Date: 2026-09-29

## Classification

Dataset support is **EXISTING but training-centric**.

Current canonical storage/API:

- `training_datasets`
- `training_records`
- `training_jobs`
- `/api/training/datasets`
- `/api/training/jobs`
- `backend/app/routers/training.py`

Current Model Studio consumes those same APIs through `trainingApi`; it does
not own a separate dataset backend.

ML model registry is also existing:

- `/api/ml/models`
- `backend/app/routers/ml_models.py`
- `backend/app/ml/*`

## What exists today

Training datasets currently have three explicit types:

- `examples`
- `documents`
- `feedback`

Records store input / expected output plus metadata. Document import and message
feedback import both materialize into `training_records`.

Model Studio's Train segment reads `trainingApi.listDatasets()`. Training
jobs and ML model registry are live backend concepts rather than UI fixtures.

## Gap against the master program

The existing dataset model does **not** express the broader provider-neutral
dataset-source contract needed for:

- REFERENCE / BENCHMARK;
- RUNTIME RETRIEVAL;
- RAG;
- EVALUATION;
- TESTING;
- FINE-TUNING;
- TRAINING;
- SYNTHETIC;
- AGENT BENCHMARKING.

There is also no external dataset provider abstraction discovered for remote
reference/index/sample/materialize semantics.

Therefore:

- `training_datasets` must not be renamed into a generic provider abstraction;
- Hugging Face must not be wired directly into Model Studio as a special-case
  source;
- provider-neutral dataset-source architecture remains a later slice;
- external dataset-provider implementation does not block the first Plays.

## Current decision

For the first Play program:

DATASET_PROVIDER_REQUIRED = NO

The first Plays must use connected operational systems and canonical
knowledge/evidence. They do not require a new dataset provider.

Dataset architecture may later wrap or reference existing training datasets,
but must preserve the distinction between a training dataset and an external
reference/runtime source.

## Result

DATASET_MODEL_STUDIO_AUDIT = COMPLETE

No schema change was required for this audit.
