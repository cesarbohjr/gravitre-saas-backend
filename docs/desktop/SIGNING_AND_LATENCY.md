# Desktop — signing certs + summon latency

## Rust (local) — PASS

```text
rustc 1.97.1
cargo 1.97.1
toolchain: stable-x86_64-pc-windows-msvc
```

Install (already applied via winget):

```powershell
winget install --id Rustlang.Rustup -e
$env:Path = "$env:USERPROFILE\.cargo\bin;" + $env:Path
```

Local Windows release build produced:

```text
…/cargo-target/release/gravitre-desktop.exe
…/bundle/msi/Gravitre_0.1.0_x64_en-US.msi
…/bundle/nsis/Gravitre_0.1.0_x64-setup.exe
```

## CI artifacts — PASS (draft release)

Evidence:

- Icon-fix run: https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/31409015268 — **success** (Windows + macOS aarch64/x64 + Linux)
- Cargo.lock run: https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/31409546855 — **success**

Draft release `desktop-v0.1.0` assets (unsigned):

| Asset | Present |
|-------|---------|
| `Gravitre_0.1.0_amd64.AppImage` / `.deb` / `.rpm` | yes |
| `Gravitre_0.1.0_x64-setup.exe` / `_en-US.msi` | yes |
| `Gravitre_0.1.0_x64.dmg` + `Gravitre_x64.app.tar.gz` | yes |
| `Gravitre_0.1.0_aarch64.dmg` (marketing `latest.json`) | confirm on draft after aarch64 upload |

Publish path: GitHub → Releases → draft **Gravitre Desktop v0.1.0** → Publish when ready.  
Then rewrite `apps/web/public/desktop/latest.json` URLs to the published asset names (tag `desktop-v0.1.0`).

## Code signing — BLOCKED on secrets (you must provision)

These cannot be invented in-repo. Until set, installers remain **unsigned** (SmartScreen / Gatekeeper warnings).

### macOS (Apple Developer Program)

1. Enroll in Apple Developer (~$99/yr).
2. Create **Developer ID Application** certificate.
3. Export `.p12` + password.
4. Create app-specific password for notarytool.
5. Add GitHub Actions secrets:
   - `APPLE_CERTIFICATE` (base64 of `.p12`)
   - `APPLE_CERTIFICATE_PASSWORD`
   - `APPLE_SIGNING_IDENTITY` (e.g. `Developer ID Application: …`)
   - `APPLE_ID`, `APPLE_PASSWORD`, `APPLE_TEAM_ID`
6. Wire into `.github/workflows/desktop-tauri.yml` env (tauri-action reads these).

### Windows

1. Purchase a code-signing cert (EV preferred for reputation; OV works).
2. Install on the signing machine / use cloud HSM (e.g. Azure Trusted Signing).
3. Set Tauri / workflow:
   - `tauri.conf.json` → `bundle.windows.certificateThumbprint`
   - or CI secrets for `WINDOWS_CERTIFICATE` / thumbprint per your vendor’s docs.

### Tauri updater signing (separate)

1. `pnpm tauri signer generate -w ~/.tauri/gravitre.key`
2. Put **public** key in `tauri.conf.json` → `plugins.updater.pubkey`
3. Put **private** key in CI secret `TAURI_SIGNING_PRIVATE_KEY` (+ password if used)
4. Set `createUpdaterArtifacts: true`

## Summon latency measurement — PASS (warm, local Windows)

Binary logs to stderr and `%TEMP%\gravitre-desktop-summon.log`:

```text
[gravitre-desktop] summon_to_native_focus_ms=<n>
[gravitre-desktop] summon_to_input_ready_ms=<n>
```

Path: summon start → window shown/focused → frontend focuses textarea → `report_input_ready`.

### Evidence (2026-08-10, this Windows host)

Warm process, `GRAVITRE_BENCH_SUMMON=1` (hide → `show_companion(measure=true)` × 5). Same show/focus/input-ready path as Alt+Space show.

| Sample | `summon_to_input_ready_ms` |
|--------|----------------------------|
| 0 | 15 |
| 1 | 27 |
| 2 | 55 |
| 3 | 34 |
| 4 | 42 |

- **min / median / max:** 15 / 34 / 55 ms  
- **vs 150ms target:** all samples under budget → **PASS** for warm summon  
- `summon_to_native_focus_ms` reported `0` (sub-ms show+focus; clock is ms resolution)

### Caveats (honest)

1. **Alt+Space not used for this sample** — on this host `ChatGPT Classic` already owns Alt+Space (`HotKey already registered`). App soft-fails registration and keeps tray / single-instance summon. Re-measure with true Alt+Space after quitting ChatGPT or changing our shortcut.
2. **Warm only** — process already running; cold start **NOT RUN**.
3. **Unsigned** local release binary.

### How to re-run

```powershell
cd apps/desktop
$env:Path = "$env:USERPROFILE\.cargo\bin;" + $env:Path
pnpm exec tauri build --no-bundle
$exe = "<path from build output>\gravitre-desktop.exe"
Remove-Item "$env:TEMP\gravitre-desktop-summon.log" -ErrorAction SilentlyContinue
$env:GRAVITRE_BENCH_SUMMON = "1"
Start-Process $exe
# wait ~14s, then:
Get-Content "$env:TEMP\gravitre-desktop-summon.log"
```

True Alt+Space (after freeing the hotkey): hide then show twice; read the same log.

## Status labels

| Item | Status |
|------|--------|
| Install Rust locally | **PASS** — rustc 1.97.1 |
| Local Windows MSI/NSIS | **PASS** — built on this host |
| CI Linux / Windows / macOS | **PASS** — runs `31409015268`, `31409546855` |
| Signed macOS/Windows | **NOT RUN** — certs not in secrets |
| Summon ≤150ms (warm) | **PASS** — median 34ms, max 55ms @ 2026-08-10 (bench path; see caveats) |
| Cold start | **NOT RUN** |
