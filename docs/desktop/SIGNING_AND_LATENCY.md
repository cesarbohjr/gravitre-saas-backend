# Desktop — signing certs + summon latency

## Rust (local) — DONE on this Windows host

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

## CI artifacts (as of draft `desktop-v0.1.0`)

| Platform | Status |
|----------|--------|
| Linux `.AppImage` / `.deb` / `.rpm` | Built — on **draft** release |
| Windows | Job succeeded; confirm MSI attached to draft (re-run after icon fix if missing) |
| macOS | **Failed** on `No matching IconType` — fixed by generating `icon.icns` via `pnpm tauri icon` |

Publish path: GitHub → Releases → draft **Gravitre Desktop v0.1.0** → Publish when ready.  
Then rewrite `apps/web/public/desktop/latest.json` URLs to the published asset names.

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

## Summon latency measurement

Binary logs:

```text
[gravitre-desktop] summon_to_input_ready_ms=<n>
```

Path: global shortcut pressed → window shown/focused → frontend focuses textarea → `report_input_ready`.

**Benchmark:** ChatGPT desktop ~150ms. Goal: report real `n` on a warm process (companion already running, window hidden).

### How to measure locally (Windows)

```powershell
cd apps/desktop
$env:Path = "$env:USERPROFILE\.cargo\bin;" + $env:Path
pnpm tauri:build
# Run the built exe (path under src-tauri/target/release or bundle/msi)
# Press Alt+Space twice (hide then show), read console / DevTools for summon_to_input_ready_ms
```

Cold start (process not running) is a separate metric — report both if possible.

## Status labels

| Item | Status |
|------|--------|
| Install Rust locally | **PASS** — rustc 1.97.1 on this host |
| CI Linux artifacts | **PASS** — draft release assets present |
| CI macOS bundle | Fix pushed (`icon.icns`) — re-run CI |
| Signed macOS/Windows | **NOT RUN** — certs not in secrets |
| Summon ≤150ms | Measure after local/CI Windows binary run |
