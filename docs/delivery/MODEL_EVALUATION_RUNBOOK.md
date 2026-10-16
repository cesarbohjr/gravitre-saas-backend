# Workflow model comparison

This harness extends the existing ModelRouter, catalog and model_calls contract.
It runs synthetic structured planning tasks without executing tools. The initial
five cases cover ticket triage/extraction, external-send approval, revoked
context, and the distinction between provider acceptance and verified completion.
They are a starting corpus, not full connector or business-workflow acceptance.

## Validate without spending or database access

From the repository root with backend dependencies installed:

```sh
python scripts/evaluate_llm_workflows.py --models gpt-5.4-mini claude-haiku-5-5
```

The default prints only the run manifest. It never calls a provider or database.
Unknown/retired catalog models, duplicate models and batches beyond 200 requests
are refused. The corpus is synthetic; do not replace it with customer content.

## Explicit provider evaluation

Use backend service credentials and a dedicated test organization. The router's
existing policy, rate and budget checks apply; this does not replace them with
an evaluation-only provider bypass. Example (substitute the real test org UUID):

```sh
python scripts/evaluate_llm_workflows.py --models gpt-5.4-mini claude-haiku-5-5 --repetitions 4 --org-id TEST_ORG_UUID --run
```

`--run` performs paid model requests and records model_calls. It does not invoke
connector tools, create assistant customer usage charges, or change routing.
Output includes dataset/catalog hashes, model-call ids, actual model identity,
quality outcomes, tokens, cost and latency; prompts/responses are omitted.
No live model evaluation was run from this development environment.

## Interpret evidence

- A fallback response fails the requested model's evaluation, even when correct.
- Missing model-call identity or provider usage cannot count as a quality pass.
- Exact JSON scoring preserves scalar types and rejects duplicate keys; it does
  not substitute lexical matching for semantic quality on general prose tasks.
- Provider failures remain in the denominator. Unknown cost makes total cost and
  cost per success unknown, rather than understating workflow economics.
- Latency percentiles use the existing minimums: P50 needs 5 samples, P95 needs
  20 and P99 needs 100. Repeated cases are not independent workflow evidence.

All reports keep `routing_approved=false`. Routing promotion still requires
representative task coverage, reviewed quality thresholds, security invariants,
measured complete costs and live workflow acceptance. No benchmark result is
ingested as customer feedback or a business outcome in company learning.
