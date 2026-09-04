#!/usr/bin/env node
/**
 * Class B — mutation proof for scripts/check-chat-surface-drift.mjs
 *
 * Independent verification (UI 2.0 program closure bar):
 * 1. Baseline must PASS
 * 2. Injected hand-roll / fork / missing-export mutations must FAIL with expected text
 * 3. Cleanup must restore PASS
 *
 * Evidence is printed to stdout; exit 0 only if every case behaves.
 */
import { spawnSync } from "node:child_process"
import { mkdirSync, writeFileSync, unlinkSync, readFileSync, existsSync, rmdirSync } from "node:fs"
import { join, dirname } from "node:path"
import { fileURLToPath } from "node:url"

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..")
const WEB = join(ROOT, "apps", "web")
const GUARD = join(ROOT, "scripts", "check-chat-surface-drift.mjs")
const MUT_DIR = join(WEB, "components", "_drift_mutation_probe")
const MUT_FILE = join(MUT_DIR, "mutation-probe.tsx")
const VOICE_PRESENTATION = join(WEB, "components", "gravitre", "assistant", "voice-presentation.tsx")

function runGuard() {
  const result = spawnSync(process.execPath, [GUARD], {
    cwd: ROOT,
    encoding: "utf8",
  })
  return {
    code: result.status ?? 1,
    out: `${result.stdout ?? ""}${result.stderr ?? ""}`,
  }
}

function assert(cond, msg) {
  if (!cond) throw new Error(msg)
}

const cases = []

function record(name, ok, detail) {
  cases.push({ name, ok, detail })
  console.log(`${ok ? "PASS" : "FAIL"} — ${name}${detail ? `: ${detail}` : ""}`)
}

try {
  // ── Baseline ─────────────────────────────────────────────────────────────
  {
    const { code, out } = runGuard()
    const ok = code === 0 && /chat-surface-drift PASS/.test(out)
    record("baseline clean tree", ok, ok ? "exit 0" : `exit ${code}`)
    assert(ok, "baseline must PASS before mutations")
  }

  mkdirSync(MUT_DIR, { recursive: true })

  // ── Mutation A: hand-rolled waveform bars ────────────────────────────────
  {
    writeFileSync(
      MUT_FILE,
      `"use client"\nexport function Probe() {\n  return <div className="gv-wave-bar" />\n}\n`,
      "utf8",
    )
    const { code, out } = runGuard()
    const ok =
      code === 1 &&
      /hand-rolls waveform bars|GravitreWave/.test(out)
    record("mutation A gv-wave-bar", ok, ok ? "caught" : out.split("\n").slice(0, 4).join(" | "))
    assert(ok, "mutation A must FAIL")
  }

  // ── Mutation B: forked marketing orb name ────────────────────────────────
  {
    writeFileSync(
      MUT_FILE,
      `"use client"\nexport function MarketingGravitreOrb() { return null }\n`,
      "utf8",
    )
    const { code, out } = runGuard()
    const ok = code === 1 && /forked orb name|MarketingGravitreOrb/.test(out)
    record("mutation B MarketingGravitreOrb", ok, ok ? "caught" : out.split("\n").slice(0, 4).join(" | "))
    assert(ok, "mutation B must FAIL")
  }

  // ── Mutation C: strip GravitreWave export temporarily ────────────────────
  {
    unlinkSync(MUT_FILE)
    const original = readFileSync(VOICE_PRESENTATION, "utf8")
    assert(original.includes("export const GravitreWave"), "GravitreWave export missing pre-mutation")
    const mutated = original.replace(
      "export const GravitreWave = GravitreVoiceWaveform",
      "const GravitreWave = GravitreVoiceWaveform /* mutation-probe */",
    )
    assert(mutated !== original, "failed to apply GravitreWave export mutation")
    writeFileSync(VOICE_PRESENTATION, mutated, "utf8")
    try {
      const { code, out } = runGuard()
      const ok = code === 1 && /GravitreWave/.test(out)
      record("mutation C missing GravitreWave export", ok, ok ? "caught" : out.split("\n").slice(0, 4).join(" | "))
      assert(ok, "mutation C must FAIL")
    } finally {
      writeFileSync(VOICE_PRESENTATION, original, "utf8")
    }
  }

  // Cleanup probe file/dir
  try {
    if (existsSync(MUT_FILE)) unlinkSync(MUT_FILE)
  } catch {
    /* ignore */
  }
  try {
    rmdirSync(MUT_DIR)
  } catch {
    /* ignore non-empty */
  }

  // ── Restore baseline ─────────────────────────────────────────────────────
  {
    const { code, out } = runGuard()
    const ok = code === 0 && /chat-surface-drift PASS/.test(out)
    record("restore clean tree", ok, ok ? "exit 0" : `exit ${code}`)
    assert(ok, "restore must PASS")
  }

  const failed = cases.filter((c) => !c.ok)
  if (failed.length) {
    console.error("\nClass B mutation proof FAIL")
    process.exit(1)
  }
  console.log("\nClass B mutation proof PASS — baseline + 3 mutations + restore")
  process.exit(0)
} catch (err) {
  // Best-effort restore of voice presentation if we crashed mid-mutation C
  try {
    if (existsSync(MUT_FILE)) unlinkSync(MUT_FILE)
  } catch {
    /* ignore */
  }
  console.error("Class B mutation proof ERROR:", err instanceof Error ? err.message : err)
  process.exit(1)
}
