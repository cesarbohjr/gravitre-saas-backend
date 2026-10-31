# DSPy guidance optimization

Implemented offline tooling, not an application dependency or a second runtime.
The user's full-engineering instruction supersedes the roadmap's earlier
package-install/planning restriction. Both PRs stay open/draft; no merge or deploy.

## Compile, evaluate, review, promote, roll back

Use Python 3.12 in a separate virtual environment:

```
python -m venv /tmp/gravitre-guidance-venv
/tmp/gravitre-guidance-venv/bin/pip install --require-hashes -r scripts/guidance_optimization/requirements.lock
/tmp/gravitre-guidance-venv/bin/python scripts/guidance_optimization/optimize.py compile --output /tmp/candidates.json
/tmp/gravitre-guidance-venv/bin/python scripts/guidance_optimization/optimize.py evaluate --model openai/MODEL --judge-model openai/JUDGE --output /tmp/evaluation.json
```

MODEL/JUDGE are operator-selected real provider models, not defaults. Evaluation
reads the provider's standard credential environment only when explicitly run;
no keys are available in compilation CI. It uses only committed synthetic data,
never tenant conversations or feedback as training examples. Real evaluation
requires configured provider credentials; no fabricated quality PASS is supplied.

DSPy 3.2.1 (MIT) `LabeledFewShot.compile` really selects 2/4/6 training examples.
It needs no teacher or model calls to compile. Validation alone selects a
candidate; the sealed holdout is evaluated afterward once for that candidate and
the unchanged native baseline, through the same generation and judge models,
for paired text/voice-register requests. This is text generation in a spoken
register, not STT/TTS/physical voice acceptance. Full native safety/behavior
instructions remain present. This does not optimize weights or invent answers.

The real DSPy/LiteLLM/OpenAI HTTP stack is also exercised against a local fixture:
80 local requests / 40 scored rows, with no external provider. Its evidence mode
is `transport_fixture` and is explicitly ineligible for promotion even when the
controlled candidate scores higher. This verifies the implemented generation,
selection, holdout and verdict paths without inventing measured quality.

The original 26-case/520-pair baseline and separate three-turn dataset remain
unchanged. The new fixed corpus has six training, three validation and four
holdout cases. Its immutable SHA is enforced. Responses and provider error bodies
are not written to reports; hashes, model provenance, bounded verdicts, split,
category and latency are retained. Cost is unknown, not zero. Timeouts and one
provider retry bound each request; malformed judges/errors cannot promote.

A candidate is eligible only with complete unique case/channel coverage, matching
corpus/artifact provenance, no security violations, no case-level regressions and
strict holdout gain. Fixture/compile-only evidence cannot promote. A named reviewer
must inspect the evidence and extract the exact selected candidate from the
compilation output, then run:

```
python scripts/guidance_optimization/optimize.py promote --candidate /tmp/selected.json --report /tmp/evaluation.json --reviewer REVIEWER --expected native-v1
python scripts/guidance_optimization/optimize.py rollback --reviewer REVIEWER --expected dspy-VERSIONHASH
```

These commands edit source-controlled artifacts only. They do not activate a
running service. Review and CI are still required. The release writes an exclusive
lock and checks the expected active version before atomically changing the
manifest. Unknown, tampered or missing artifacts fail back to native guidance.
The shared `conversational_behavior_section` serves both classical and unified
text/voice prompts; an agent/user cannot supply a path or select an optimizer.
The committed active version remains **native-v1**, since provider quality has
not been measured. This preserves the working baseline rather than promoting an
unevaluated candidate.

## Explicit dependency findings and containment

The full isolated lock is hash-pinned and audited, separately from application
requirements. DSPy is MIT. LiteLLM, diskcache and filelock licenses/metadata were
inspected from the installed distributions. DSPy/LiteLLM are not imported by the
application, and their OpenAI dependency does not enter its provider graph.

The initial complete audit found 15 entries (14 distinct advisories):
`diskcache==5.6.3`: PYSEC-2026-2447; `filelock==3.32.7`:
CVE-2026-112907/908/909/910/911/912/913/915/935/936/938/939/940.
Diskcache has no listed fixed release. Filelock advisories list 4.2.1 as the
complete fix, but the current LiteLLM package requires filelock<4. Installing an
incompatible version or omitting dependencies from the audit is not the remedy.

The tool creates an empty mode-0700 private cache root before SDK import, overrides
all accepted cache directories, disables DSPy disk/memory caches and uses
`cache=False` for provider calls. It also replaces diskcache's deserialization
entrypoint and filelock's synchronous/asynchronous acquire methods with explicit
runtime denials. No caller/example/model-controlled local path is accepted.
The real SDK verification executes both denials and the actual compilation with
outbound sockets forbidden and credentials removed. No shared/untrusted cache is
opened, no pickle fetch or filelock acquisition can be used by this tooling.
These findings are **contained for this narrow offline tool, not patched upstream
or a clean SCA result**. Application adoption/general SDK use is not approved.

`audit.py` records the entire unfiltered audit and fails on every advisory outside
those exact package/version/ID combinations. This is a new explicit reachability
triage, justified by the enforced guards; the existing application dependency
audit and all existing regression thresholds are unchanged. Moving versions or
expanding SDK capabilities requires revisiting this decision. CI uploads the full
audit alongside actual-SDK compilation evidence. Do not describe it as zero known
vulnerabilities.
