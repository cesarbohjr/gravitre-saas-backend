#!/usr/bin/env node
/**
 * Structural regression guard for CognitiveTurnKernel / One Brain intake.
 * Asserts key files exist and that streaming LIVE stays after the kernel call.
 * Exit 1 on any failure.
 */
import { existsSync, readFileSync } from "node:fs"
import { join, dirname } from "node:path"
import { fileURLToPath } from "node:url"
import { spawnSync } from "node:child_process"

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..")
const failures = []

function fail(msg) {
  failures.push(msg)
}

function mustExist(rel) {
  const abs = join(ROOT, rel)
  if (!existsSync(abs)) fail(`missing required file: ${rel}`)
  return abs
}

function read(rel) {
  const abs = mustExist(rel)
  if (!existsSync(abs)) return ""
  return readFileSync(abs, "utf8")
}

function mustContain(rel, needle, label = needle) {
  const src = read(rel)
  if (!src.includes(needle)) fail(`${rel}: expected to contain ${label}`)
}

// --- 1) Key files exist ---
mustExist("backend/app/services/cognitive_turn_kernel.py")
mustExist("backend/app/services/cognitive_planner.py")
mustExist("supabase/migrations/20260813120000_cognitive_turn_kernel.sql")

// --- 2) agent_intelligence: run_pre_act present; kernel before apply_unified_turn_live in streaming ---
{
  const rel = "backend/app/operators/agent_intelligence.py"
  const src = read(rel)
  if (!src.includes("run_pre_act")) {
    fail(`${rel}: expected run_pre_act (CognitiveTurnKernel pre-ACT)`)
  }

  const streamingMarker = "async def execute_task_streaming"
  const streamIdx = src.indexOf(streamingMarker)
  if (streamIdx < 0) {
    fail(`${rel}: execute_task_streaming not found`)
  } else {
    // Region: from streaming def to next top-level-ish async def at same indent, or EOF.
    const after = src.slice(streamIdx)
    const nextDef = after.search(/\n    async def |\n    def /)
    const region = nextDef > 0 ? after.slice(0, nextDef) : after

    const kernelIdx = region.indexOf("run_pre_act")
    const liveIdx = region.indexOf("apply_unified_turn_live")
    if (kernelIdx < 0) {
      fail(`${rel}: execute_task_streaming must call run_pre_act`)
    } else if (liveIdx < 0) {
      fail(`${rel}: execute_task_streaming must reference apply_unified_turn_live`)
    } else if (kernelIdx >= liveIdx) {
      fail(
        `${rel}: CognitiveTurnKernel run_pre_act must appear BEFORE apply_unified_turn_live in execute_task_streaming (got kernel@${kernelIdx} live@${liveIdx})`,
      )
    }
  }
}

// --- 3) unified_turn_reasoning_service accepts cognitive_context ---
mustContain(
  "backend/app/services/unified_turn_reasoning_service.py",
  "cognitive_context=",
  "cognitive_context=",
)

// --- 4) extension_bridge wires kernel entry adapter ---
mustContain(
  "backend/app/services/extension_bridge_service.py",
  "run_kernel_for_entry",
  "run_kernel_for_entry",
)

// --- 5) council_service wires kernel entry adapter ---
mustContain(
  "backend/app/services/council_service.py",
  "run_kernel_for_entry",
  "run_kernel_for_entry",
)

// --- 6) Phase D structural wiring ---
mustExist("backend/app/services/cognitive_evidence_envelope.py")
mustExist("backend/app/knowledge_fabric/temporal.py")
mustExist("supabase/migrations/20260813140000_cognitive_phase_d_aliases.sql")
mustContain(
  "backend/app/services/cognitive_turn_kernel.py",
  "confidence_summary",
  "confidence_summary persist",
)
mustContain(
  "backend/app/services/cognitive_turn_kernel.py",
  "what_if",
  "what_if product path",
)
mustContain(
  "backend/app/services/verification_critic_service.py",
  "mandatory",
  "mandatory critic flag",
)
mustContain(
  "backend/app/services/unified_turn_reasoning_service.py",
  "attach_evidence_envelope",
  "LIVE evidence envelope",
)
mustContain(
  "backend/app/operators/agent_intelligence.py",
  "build_evidence_envelope",
  "classical evidence envelope",
)

// --- 7) Optional python import smoke ---
{
  const py = spawnSync(
    "python",
    [
      "-c",
      "from app.services.cognitive_turn_kernel import CognitiveTurnKernel, CognitiveTurnRequest; from app.services.cognitive_planner import CognitivePlanner; from app.services.cognitive_evidence_envelope import build_evidence_envelope; print('ok')",
    ],
    {
      cwd: join(ROOT, "backend"),
      encoding: "utf8",
      env: { ...process.env, PYTHONPATH: "." },
    },
  )
  if (py.error && (py.error.code === "ENOENT" || String(py.error).includes("ENOENT"))) {
    console.log("cognitive-regression-suite: python not available — skipped import smoke")
  } else if (py.status !== 0) {
    // Retry with python3
    const py3 = spawnSync(
      "python3",
      [
        "-c",
        "from app.services.cognitive_turn_kernel import CognitiveTurnKernel, CognitiveTurnRequest; from app.services.cognitive_planner import CognitivePlanner; from app.services.cognitive_evidence_envelope import build_evidence_envelope; print('ok')",
      ],
      {
        cwd: join(ROOT, "backend"),
        encoding: "utf8",
        env: { ...process.env, PYTHONPATH: "." },
      },
    )
    if (py3.error && (py3.error.code === "ENOENT" || String(py3.error).includes("ENOENT"))) {
      console.log("cognitive-regression-suite: python not available — skipped import smoke")
    } else if (py3.status !== 0 && py.status !== 0) {
      fail(
        `python import smoke failed: ${(py.stderr || py.stdout || py3.stderr || py3.stdout || "").trim().slice(0, 400)}`,
      )
    }
  }
}

// --- 8) Targeted cognitive eval pytest (pending-reply + council + kernel) ---
// When COGNITIVE_REGRESSION_RUN_PYTEST=1 (backend CI job), require these to pass.
{
  const runPytest =
    process.env.COGNITIVE_REGRESSION_RUN_PYTEST === "1" ||
    process.env.COGNITIVE_REGRESSION_RUN_PYTEST === "true"
  if (runPytest) {
    const args = [
      "-m",
      "pytest",
      "-q",
      "tests/services/test_pending_reply_classifier.py",
      "tests/services/test_council_service.py",
      "tests/services/test_cognitive_turn_kernel.py",
      "tests/services/test_cognitive_evidence_envelope.py",
    ]
    const env = {
      ...process.env,
      PYTHONPATH: ".",
      APP_ENV: process.env.APP_ENV || "dev",
      SUPABASE_URL: process.env.SUPABASE_URL || "https://test.supabase.co",
      SUPABASE_ANON_KEY: process.env.SUPABASE_ANON_KEY || "anon-test",
      SUPABASE_SERVICE_ROLE_KEY: process.env.SUPABASE_SERVICE_ROLE_KEY || "service-role-test",
    }
    let result = spawnSync("python", args, {
      cwd: join(ROOT, "backend"),
      encoding: "utf8",
      env,
    })
    if (result.error && (result.error.code === "ENOENT" || String(result.error).includes("ENOENT"))) {
      result = spawnSync("python3", args, {
        cwd: join(ROOT, "backend"),
        encoding: "utf8",
        env,
      })
    }
    if (result.error) {
      fail(`targeted cognitive pytest spawn failed: ${result.error.message || result.error}`)
    } else if (result.status !== 0) {
      fail(
        `targeted cognitive pytest failed:\n${(result.stdout || "").trim().slice(0, 800)}\n${(result.stderr || "").trim().slice(0, 800)}`,
      )
    } else {
      console.log("cognitive-regression-suite: targeted pytest PASS (pending-reply + council + kernel + evidence)")
    }
  } else {
    console.log(
      "cognitive-regression-suite: targeted pytest skipped (set COGNITIVE_REGRESSION_RUN_PYTEST=1)",
    )
  }
}

if (failures.length) {
  console.error("cognitive-regression-suite FAILED:")
  for (const f of failures) console.error(`  - ${f}`)
  process.exit(1)
}

console.log("cognitive-regression-suite PASS")
process.exit(0)
