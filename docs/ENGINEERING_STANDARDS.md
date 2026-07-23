# Engineering standards (standing)

These rules outlive any single ticket or chat thread. They were proven across
the 2026 AI / marketplace / Memory / ReAct hardening waves. Follow them for
every “done” claim and every governance-adjacent change.

## 1. Evidence-linked PASS

A “done” claim requires **production evidence** — a live HTTP/trace/audit id,
deployed SHA, or equivalent log artifact — not local pytest or code review alone.

Code review and unit tests are necessary; they are not sufficient.

## 2. One layer ≠ done

A fix at one layer (backend, UI, or API) is **not done** until confirmed at
**every layer the user actually experiences**.

Examples that failed this bar and had to be reopened:

- Backend install path green while HTTP marketplace route still 500 / UUID mismatch
- Suggest-only UI shipped while signal wiring still selected nonexistent columns
- DB live PASS while the deployed Railway revision had not picked up the fix

## 3. Dual paths need dual verification

When two code paths can reach the same outcome (e.g. ReAct tool loop vs governed
chat / `execute_plan`), assume **both need independent verification** until
proven to share the same underlying write gate and audit trail.

Do not mark a write-path fix done after smoking only one entrypoint.

## 4. Schema-gate ≠ authorization

An engineering or schema gate passing is **not authorization** for a
governance-sensitive decision (especially PII / third-party ML purpose).

Those require an **explicitly named owner** and a written option choice,
separate from the engineering approval chain.

Canonical example: ADR 001 schema-gate met-in-code did **not** authorize Memory
embeddings. Memory Phase 1 waited for [STA-312](https://linear.app/staqbot/issue/STA-312)
sole-owner sign-off and **Option B** (opaque tokens, opt-in default off, no raw PII).
See `docs/decisions/001-defer-ml-disambiguation-until-schema-stable.md` and
`docs/delivery/memory-phase1-data-handling-design.md`.

## 5. Class-level before close

When a bug is found, check whether it is an isolated case or a
**structural / class-level** issue before considering it closed.

Examples:

- One vendor’s synthetic agent id crash → audit all vendors sharing the pattern
- One connector’s NL-mapper misroute → check the shared mapper, not only that vendor
- One path bypassing approval → inventory every path that can reach the same write

---

## Related capability caveat (Memory Phase 1)

Option B Memory embeddings match **previously indexed normalized mentions via
exact HMAC opaque tokens** — e.g. indexed `"sarah"` matches query `"sarah"`.

They do **not** fuzzy-resolve `"Sarah"` ↔ `"Sarah Smith"`. Fuzzy / alias
expansion remains local rule-based resolution and `org_entity_resolution_records`.

Do not document or demo Memory Phase 1 as fuzzy person disambiguation.

---

## 6. Test pyramid and shift-left

- **Pyramid weight:** Many fast unit tests (backend pytest + web vitest), fewer integration tests, smallest live-prod battery surface. Run `python scripts/audit-test-pyramid.py --json docs/delivery/test-pyramid-audit-latest.json` when assessing debt.
- **Inverted pyramid anti-pattern:** When live batteries (`verify-unified-turn-*-live.py`, `smoke-*-live.py`) catch regressions that cheap local tests should catch first, add or strengthen **unit/contract tests** before expanding batteries.
- **Shift-left:** Phase 0 investigation and evidence-linked PASS (sections 1–5) apply at design time — not only at release.

## 7. Flaky tests and harness honesty

- **Flaky test SLA:** Treat intermittent failures as defects — fix or delete within **7 days**; do not rely on silent re-runs until green.
- **No silent softening:** Any change that makes a test pass more easily (looser assertion, exit code `2`→`0`, expanded allowlist) requires an **explicit justification in the same commit**, reviewed like production code. (STA-305 exit-code regression is the canonical example.)

## 8. LLM product quality (standing suites)

Maintain the batteries listed in `docs/delivery/llm-quality-test-suite.md`. Re-run the **full combined battery** after any change to Module D voice spec, unified-turn prompt assembly, or task model tier — not ad hoc spot checks only.

**Gap:** prompt-injection resistance battery is **not yet implemented** — track before claiming LLM QA complete.

## 9. Dependency audit in CI

`pnpm audit --audit-level=critical` and `pip-audit` run on every PR in `.github/workflows/ci.yml` and **fail the build on new critical** findings. **High** severities are reported in the same job (`continue-on-error`) and require reachability triage (runtime vs dev-only) before dismissing — do not treat dev-only ESLint/shadcn highs as production blockers without documenting that triage.

---

## How to cite

When closing tickets, prefer: *“PASS against [artifact] on prod SHA [sha]”*
over *“fixed in code.”*
