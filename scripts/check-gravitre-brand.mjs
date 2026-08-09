#!/usr/bin/env node
/**
 * Phase 4 CI guard: fail when case-insensitive `gravitree` appears outside
 * the allowlisted inventory / historical / dual-read-compat paths.
 *
 * Self-test (prove the guard works):
 *   node scripts/check-gravitre-brand.mjs --self-test
 * Writes a temp file containing "Gravitree", asserts exit 1, deletes it,
 * then asserts a clean tree passes.
 */
import {
  existsSync,
  readdirSync,
  readFileSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs"
import { dirname, join, relative } from "node:path"
import { fileURLToPath } from "node:url"
import { spawnSync } from "node:child_process"

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..")
const PATTERN = /gravitree/i

/** Exact relative paths (posix) always allowed. */
const ALLOWED_EXACT = new Set([
  "docs/delivery/gravitre-routing-decision-map.md",
  "docs/delivery/gravitree-brand-rename-inventory-2026-08.md",
  "scripts/apply-gravitre-brand-rename.py",
  "scripts/check-gravitre-brand.mjs",
])

/** Any file under these directory prefixes is allowed (historical). */
const ALLOWED_DIR_PREFIXES = ["supabase/migrations/"]

/**
 * Phase 2 dual-read / backward-compat surfaces that intentionally keep the
 * legacy spelling alongside the canonical gravitre_* form.
 */
const ALLOWED_DUAL_READ = new Set([
  "backend/app/intelligence_packs/shared/auth_mode.py",
  "backend/app/services/conversation_write_guard.py",
  "backend/app/main.py",
  "backend/app/routers/assistant.py",
  "backend/app/routers/connectors.py",
  "backend/app/routers/extension.py",
  "backend/app/operators/react_engine.py",
  "backend/app/services/extension_bridge_service.py",
  "backend/tests/conftest.py",
  "backend/tests/intelligence_packs/test_auth_mode_and_stubs.py",
  "backend/tests/services/test_conversation_write_guard.py",
  "backend/tests/services/test_ensure_owned_conversation.py",
  "apps/extension/background.js",
  "apps/extension/content/shared.js",
  "apps/web/lib/conversation-smoke-guard.ts",
  "apps/web/lib/connectors.ts",
  "apps/web/__tests__/lib/connectors-hub-visibility.test.ts",
  ".github/workflows/ci.yml",
  "scripts/smoke-phase4-cisa-sec-followons-live.py",
])

const SKIP_DIR_NAMES = new Set([
  ".git",
  "node_modules",
  ".next",
  "dist",
  "coverage",
  "__pycache__",
  ".pytest_cache",
  ".mypy_cache",
  ".ruff_cache",
  ".turbo",
  ".venv",
  "venv",
  ".cursor",
  ".cursor-tmp",
  "turbopack",
])

function toPosix(p) {
  return p.replace(/\\/g, "/").replace(/^\.\//, "")
}

function isAllowed(relPosix) {
  if (ALLOWED_EXACT.has(relPosix)) return true
  if (ALLOWED_DUAL_READ.has(relPosix)) return true
  for (const prefix of ALLOWED_DIR_PREFIXES) {
    if (relPosix.startsWith(prefix)) return true
  }
  return false
}

function findViaRg() {
  const globs = [
    "!**/.git/**",
    "!**/node_modules/**",
    "!**/.next/**",
    "!**/dist/**",
    "!**/coverage/**",
    "!**/__pycache__/**",
    "!**/.pytest_cache/**",
    "!**/.mypy_cache/**",
    "!**/.ruff_cache/**",
    "!**/.turbo/**",
    "!**/.venv/**",
    "!**/venv/**",
    "!**/.cursor/**",
    "!**/.cursor-tmp/**",
    "!**/turbopack/**",
    "!**/*.tsbuildinfo",
  ]
  const args = ["-i", "-l", "--hidden", "--no-messages"]
  for (const g of globs) {
    args.push("-g", g)
  }
  args.push("gravitree", ".")
  const result = spawnSync("rg", args, { cwd: ROOT, encoding: "utf8" })
  if (result.error || result.status === 2) return null
  const out = String(result.stdout || "").trim()
  if (!out) return []
  return out
    .split(/\r?\n/)
    .map((line) => toPosix(line.trim()))
    .filter(Boolean)
}

function findViaWalk() {
  const offenders = []
  function walk(dir) {
    let entries
    try {
      entries = readdirSync(dir)
    } catch {
      return
    }
    for (const name of entries) {
      if (SKIP_DIR_NAMES.has(name)) continue
      const full = join(dir, name)
      let st
      try {
        st = statSync(full)
      } catch {
        continue
      }
      if (st.isDirectory()) {
        walk(full)
        continue
      }
      if (
        /\.(png|jpg|jpeg|gif|webp|ico|woff2?|ttf|eot|mp4|webm|pdf|zip|gz|sst|meta|del|pack|idx|bin|tsbuildinfo)$/i.test(
          name,
        )
      ) {
        continue
      }
      const rel = toPosix(relative(ROOT, full))
      if (!rel || isAllowed(rel)) continue
      let src
      try {
        src = readFileSync(full, "utf8")
      } catch {
        continue
      }
      if (PATTERN.test(src) || PATTERN.test(rel)) offenders.push(rel)
    }
  }
  walk(ROOT)
  return offenders
}

export function findOffendingFiles() {
  const viaRg = findViaRg()
  const hits = viaRg === null ? findViaWalk() : viaRg
  return [...new Set(hits.filter((rel) => !isAllowed(rel)))].sort()
}

function runCheck() {
  const offenders = findOffendingFiles()
  if (offenders.length) {
    console.error("gravitre-brand FAIL — gravitree found outside allowlist:")
    for (const rel of offenders) console.error(`  - ${rel}`)
    return 1
  }
  console.log("gravitre-brand PASS")
  return 0
}

function runSelfTest() {
  const tmpFile = join(ROOT, "scripts", "_gravitre-brand-self-test-temp.txt")
  writeFileSync(tmpFile, "Intentional Gravitree brand misspelling for self-test.\n", "utf8")

  const failRun = spawnSync(process.execPath, [fileURLToPath(import.meta.url)], {
    cwd: ROOT,
    encoding: "utf8",
  })
  if (failRun.status === 0) {
    rmSync(tmpFile, { force: true })
    console.error("gravitre-brand self-test FAIL — expected non-zero exit with temp Gravitree file")
    return 1
  }
  if (!String(failRun.stderr || failRun.stdout || "").includes("_gravitre-brand-self-test-temp")) {
    rmSync(tmpFile, { force: true })
    console.error("gravitre-brand self-test FAIL — temp offender not listed")
    console.error(failRun.stderr || failRun.stdout)
    return 1
  }

  rmSync(tmpFile, { force: true })
  if (existsSync(tmpFile)) {
    console.error("gravitre-brand self-test FAIL — could not delete temp file")
    return 1
  }

  const passRun = spawnSync(process.execPath, [fileURLToPath(import.meta.url)], {
    cwd: ROOT,
    encoding: "utf8",
  })
  if (passRun.status !== 0) {
    console.error("gravitre-brand self-test FAIL — clean tree did not pass")
    console.error(passRun.stderr || passRun.stdout)
    return 1
  }
  if (!String(passRun.stdout || "").includes("gravitre-brand PASS")) {
    console.error("gravitre-brand self-test FAIL — missing PASS marker")
    return 1
  }
  console.log("gravitre-brand self-test PASS")
  return 0
}

const args = process.argv.slice(2)
const code = args.includes("--self-test") ? runSelfTest() : runCheck()
process.exit(code)
