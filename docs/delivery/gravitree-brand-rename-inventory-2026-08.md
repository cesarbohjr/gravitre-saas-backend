# Gravitree → Gravitre brand rename — Phase 0 inventory (2026-08-09)

Scan tip: `2221005c` · case-insensitive `gravitree` · excludes `node_modules`, `.git`, `dist`, `.next`, `__pycache__`, `coverage`, `.cursor-tmp`.

| Metric | Value |
|--------|------:|
| Files with content matches | **210** (incl. `.github/workflows/ci.yml`) |
| Match occurrences (approx.) | **~655** |
| Filename-only (no content) | `scripts/gravitree_test_client.py` |

## Categories (primary class)

| Class | Files (approx.) | Priority |
|-------|----------------:|----------|
| **(a) USER-FACING STRINGS** | ~32 | Highest — customer brand defect |
| **(b) CODE IDENTIFIERS** | ~68 | Maintainability |
| **(c) INFRASTRUCTURE/CONFIG** | ~13 | Highest rename risk |
| **(d) DOCS / DELIVERY / SCRIPTS / TESTS** | ~97 | Lowest; historical record may keep audit wording |

## (c) External / infra identifiers (do not rename blindly)

| Identifier | Risk | Plan |
|------------|------|------|
| `gravitree_managed` (DB/API `authMode`) | High — persisted | Dual-read: prefer `gravitre_managed`, accept legacy |
| `X-Gravitree-Smoke-Run` / `GRAVITREE_SMOKE_RUN` | Medium | Accept both spellings |
| `GRAVITREE_CONVERSATION_SMOKE` | Medium | Accept both |
| `NEXT_PUBLIC_GRAVITREE_SMOKE_RUN` / `window.__GRAVITREE_SMOKE_RUN__` | Medium-low | Accept both |
| `X-Gravitree-React-Serial` / `GRAVITREE_REACT_SERIAL_TOOLS` | Medium-low | Accept both |
| `GRAVITREE_AUTH` (extension message) | High if shipped | Accept both message types |
| `POST …/activate-gravitree` | Medium | New path + keep legacy alias |
| `openInGravitreeUrl` | Medium | Emit correct + legacy field |
| `GRAVITREE_SOURCE_UNAVAILABLE` | Medium | Prefer correct; accept legacy in parsers |
| Postgres GUC `gravitree.bypass_…` | Medium | Dual-set in tests; new GUC preferred |
| CWS name/slug `gravitree` | High if published | Fix listing copy; slug may stay until store republish |

## Historical docs

Leave misspelling as *quoted audit finding* in `docs/delivery/gravitre-routing-decision-map.md` where it records the prior deferral. Fix any active brand presentation elsewhere.

## Path renames required

- `apps/web/components/gravitre/gravitree-loader.tsx` → `gravitre-loader.tsx`
- `backend/app/services/gravitree_voice.py` → `gravitre_voice.py`
- `backend/app/services/gravitree_connector_activation.py` → `gravitre_connector_activation.py`
- `backend/tests/services/test_gravitree_voice.py` → `test_gravitre_voice.py`
- `docs/delivery/module-d-gravitree-voice.md` → `module-d-gravitre-voice.md` (or keep + redirect note)
- `scripts/gravitree_test_client.py` → `gravitre_test_client.py`

## Applied (2026-08-09)

Path renames completed (old paths removed; git records rename pairs). Dual-read / backward-compat aliases kept:

| Surface | Canonical | Legacy still accepted / emitted |
|---------|-----------|----------------------------------|
| Auth mode | `gravitre_managed` | `gravitree_managed` via `is_gravitre_managed_mode` / `normalize_auth_mode_value`; BYO forbidden set includes both |
| Smoke header / env | `x-gravitre-smoke-run`, `GRAVITRE_SMOKE_RUN`, `GRAVITRE_CONVERSATION_SMOKE` | `x-gravitree-smoke-run`, `GRAVITREE_*`; `mark_smoke_run()` sets both env names |
| React serial | `x-gravitre-react-serial`, `GRAVITRE_REACT_SERIAL_TOOLS` | `x-gravitree-react-serial`, `GRAVITREE_REACT_SERIAL_TOOLS` |
| Error code (emit) | `GRAVITRE_SOURCE_UNAVAILABLE` | parsers accept `GRAVITREE_SOURCE_UNAVAILABLE` |
| Activate route | `POST …/activate-gravitre` | thin deprecated alias `POST …/activate-gravitree` |
| Extension handoff JSON | `openInGravitreUrl` | also emits `openInGravitreeUrl` (same value) |
| Extension auth message | `GRAVITRE_AUTH` | background accepts `GRAVITREE_AUTH` |
| Browser smoke flag | `__GRAVITRE_SMOKE_RUN__` / `NEXT_PUBLIC_GRAVITRE_SMOKE_RUN` | also `__GRAVITREE_SMOKE_RUN__` / `NEXT_PUBLIC_GRAVITREE_SMOKE_RUN` |
| Postgres GUC | (prefer `gravitre.bypass_…` in new docs) | historical migration left as `gravitree.bypass_…`; no runtime SET helper found to dual-set |

CI: `scripts/check-gravitre-brand.mjs` (+ `--self-test`) wired next to chat-surface drift in `.github/workflows/ci.yml`. Dual-read files are an explicit allowlist beside inventory / migrations.

## Live tip verification (2026-08-09)

| Check | Result | Evidence |
|-------|--------|----------|
| Git tip | PASS | `93bac82e534ac110343c828a435bf26588b2cffa` on `main` |
| Vercel | PASS | `dpl_EYZ16qGvEZUFfkv3U8BsgDKvSLrh` READY · aliases include `gravitre.app` |
| API | PASS | `GET https://api.gravitre.app/health` @ 2026-08-09T21:59:45Z → `git_sha=93bac82e534ac110343c828a435bf26588b2cffa` |
| Marketing home | PASS | `https://gravitre.app/` HTML: `Gravitree=0`, `Gravitre=26` |
| Extension marketing | PASS | `https://gravitre.app/features/extension` HTML: `Gravitree=0` |
| CI brand guard | PASS | `node scripts/check-gravitre-brand.mjs` + `--self-test` → PASS |
| Focused pytest | PASS | 57 passed (`test_auth_mode_and_stubs`, `test_conversation_write_guard`, `test_gravitre_voice`) |
