#!/usr/bin/env node
/**
 * Playback-continuity harness for streamed voice PCM (SYNTHETIC).
 *
 * Feeds a synthetic speech-like 24 kHz stream through the real player code in
 * headless Chromium, with Pipecat pacing (40 ms chunks sent every 20 ms),
 * 0..300 ms per-message delivery jitter, optional odd-length messages, and a
 * mid-stream flush (barge-in) followed by a second reply. The output is
 * recorded with an AudioWorklet tap and scanned for discontinuities.
 *
 * Usage (from apps/web):
 *   node scripts/voice-playback-continuity/run.mjs [--out results.json] [--quick]
 * Env: PLAYWRIGHT_MODULE (path to a playwright / @playwright/test package),
 *      CHROMIUM_PATH (browser executable; default: Playwright's bundled one).
 */
import { createServer } from "node:http"
import { readFile, writeFile } from "node:fs/promises"
import { createRequire } from "node:module"
import path from "node:path"
import { fileURLToPath } from "node:url"

const here = path.dirname(fileURLToPath(import.meta.url))
const webRoot = path.resolve(here, "../..")
const require = createRequire(import.meta.url)
const args = process.argv.slice(2)
const outPath = args.includes("--out") ? args[args.indexOf("--out") + 1] : null
const quick = args.includes("--quick")
const enforce = args.includes("--enforce")
const compare = args.includes("--compare-policies")
const shardSeed = process.env.VOICE_COMPARISON_SEED === undefined ? null : Number(process.env.VOICE_COMPARISON_SEED)
if (shardSeed !== null && (!compare || ![1, 2, 3].includes(shardSeed))) throw new Error("Invalid comparison seed shard")
if (compare && (enforce || process.env.SCENARIO_FILTER)) throw new Error("Paired comparison must run unfiltered, independently of standing gate")
if (enforce && process.env.SCENARIO_FILTER) throw new Error("Enforced matrix cannot be filtered")

const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "@playwright/test")
function loadEsbuild() {
  // esbuild is not a direct dependency; reach it through vitest -> vite.
  try {
    return require("esbuild")
  } catch {
    const viaVitest = createRequire(require.resolve("vitest/package.json"))
    return createRequire(viaVitest.resolve("vite/package.json"))("esbuild")
  }
}
const esbuild = loadEsbuild()

const bundle = await esbuild.build({
  entryPoints: [path.join(here, "page.ts")],
  bundle: true,
  write: false,
  format: "esm",
  target: "es2020",
  tsconfig: path.join(webRoot, "tsconfig.json"),
  logLevel: "warning",
  // Next inlines these; the harness never reads them.
  define: { "process.env": "{}", "process.env.NODE_ENV": "\"production\"" },
})
const pageJs = bundle.outputFiles[0].text
const html = `<!doctype html><meta charset="utf-8"><title>continuity</title><script type="module" src="/harness.js"></script>`

const server = createServer(async (req, res) => {
  const url = new URL(req.url, "http://x")
  if (url.pathname === "/") return res.writeHead(200, { "content-type": "text/html" }).end(html)
  if (url.pathname === "/harness.js") return res.writeHead(200, { "content-type": "text/javascript" }).end(pageJs)
  if (url.pathname.startsWith("/voice-worklets/")) {
    try {
      const body = await readFile(path.join(webRoot, "public", url.pathname))
      return res.writeHead(200, { "content-type": "text/javascript" }).end(body)
    } catch {
      /* fall through */
    }
  }
  res.writeHead(404).end()
})
await new Promise((r) => server.listen(0, "127.0.0.1", r))
const base = `http://127.0.0.1:${server.address().port}/`

const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || undefined,
  args: ["--autoplay-policy=no-user-gesture-required"],
})
const page = await browser.newPage()
page.on("pageerror", (e) => console.error("[pageerror]", e.message))
page.on("console", (m) => {
  if (m.type() === "error" || m.type() === "warning") console.error("[page]", m.text())
})
await page.goto(base)
await page.waitForFunction(() => window.harnessReady === true)

/** Largest per-sample change the clean signal can have (see signalAt in page.ts). */
function maxSignalStep(rate) {
  const f0 = 210
  const deriv = 0.5 * (0.6 * 2 * Math.PI * f0 + 0.3 * 2 * Math.PI * 2 * f0 + 0.1 * 2 * Math.PI * 4 * f0) + 0.5 * 0.4 * 2 * Math.PI * 1.3
  return deriv / rate
}

/** About -46 dBFS: a step into or out of silence larger than this is audible. */
const HARD_EDGE = 0.005

function analyse({ samples, sampleRate, firstPushFrame, flushFrame, secondPushFrame, arrivals }) {
  if (!Number.isInteger(flushFrame) || !Number.isInteger(secondPushFrame) || flushFrame <= 0 || secondPushFrame <= flushFrame || secondPushFrame >= samples.length || samples.some(v => !Number.isFinite(v))) throw new Error("Invalid captured audio or clock bounds")
  const x = Float32Array.from(samples)
  const thr = 2 * maxSignalStep(sampleRate)
  const nz = (v) => Math.abs(v) > 1e-5
  // A reply "starts" once it is clearly audible, so a fade-in's first
  // near-zero samples are not mistaken for a gap.
  const firstFrom = (from) => {
    for (let i = from; i < x.length; i++) if (Math.abs(x[i]) > 0.01) return i
    return -1
  }
  let last = -1
  for (let i = x.length - 1; i >= 0; i--) if (nz(x[i])) { last = i; break }
  if (!Number.isInteger(firstPushFrame) || firstPushFrame < 0 || firstPushFrame >= flushFrame) throw new Error("Invalid first push boundary")
  const r1Start = firstFrom(firstPushFrame)
  const flushGuard = Math.round(0.35 * sampleRate)
  const r2Start = firstFrom(secondPushFrame)
  let lastResidual = flushFrame - 1
  for (let i = flushFrame; i < secondPushFrame; i++) if (Math.abs(x[i]) > HARD_EDGE) lastResidual = i
  const residualMs = Math.max(0, lastResidual - flushFrame + 1) * 1000 / sampleRate
  const windows = [
    ["reply1", r1Start, flushFrame - Math.round(0.02 * sampleRate)],
    ["reply2", r2Start, last],
  ]
  const minGap = Math.round(0.001 * sampleRate)
  const res = { threshold: thr, residualMs, firstStartupMs: r1Start < 0 ? null : (r1Start-firstPushFrame)*1000/sampleRate, secondStartupMs: r2Start < 0 ? null : (r2Start-secondPushFrame)*1000/sampleRate, secondReplySpanMs: r2Start < 0 ? 0 : (last - r2Start + 1) * 1000 / sampleRate }
  let jumpsTotal = 0
  let hardEdgesTotal = 0
  let gapsTotal = 0
  let gapMsTotal = 0
  for (const [name, a, b] of windows) {
    let jumps = 0
    let maxJump = 0
    let gaps = 0
    let gapFrames = 0
    let run = 0
    let hardEdges = 0
    const edges = []
    if (a < 0 || b <= a) {
      res[name] = { missing: true }
      continue
    }
    for (let i = a + 1; i <= b; i++) {
      const d = Math.abs(x[i] - x[i - 1])
      if (d > maxJump) maxJump = d
      if (d > thr) jumps += 1
      if (!nz(x[i])) run += 1
      else {
        if (run >= minGap) {
          gaps += 1
          gapFrames += run
          // Entering or leaving the silence on a non-faded sample is a click.
          if (Math.abs(x[i - run - 1]) > HARD_EDGE) hardEdges += 1
          if (Math.abs(x[i]) > HARD_EDGE) hardEdges += 1
          // Level just before and after the silent run: a hard cut shows here.
          edges.push([+((i - run) / sampleRate).toFixed(3), +x[i - run - 1].toFixed(4), +x[i].toFixed(4), +x[i + 1].toFixed(4)])
          if (process.env.DEBUG_DUMP) console.error("gap", (i - run) / sampleRate, run, Array.from(x.subarray(i - run - 6, i - run + 1)).map((v) => v.toFixed(5)).join(" "), "|", Array.from(x.subarray(i - 3, i + 12)).map((v) => v.toFixed(5)).join(" "))
        }
        run = 0
      }
    }
    res[name] = { jumps, maxJump: +maxJump.toFixed(4), gaps, hardEdges, gapMs: +((gapFrames / sampleRate) * 1000).toFixed(1), gapEdges: edges }
    jumpsTotal += jumps
    hardEdgesTotal += hardEdges
    gapsTotal += gaps
    gapMsTotal += (gapFrames / sampleRate) * 1000
  }
  // The flush itself: from 20 ms before the flush to the start of reply 2.
  let flushJumps = 0
  let flushMax = 0
  const fa = Math.max(1, flushFrame - Math.round(0.02 * sampleRate))
  const fb = r2Start > 0 ? r2Start : Math.min(x.length, flushFrame + flushGuard)
  for (let i = fa; i < fb; i++) {
    const d = Math.abs(x[i] - x[i - 1])
    if (d > flushMax) flushMax = d
    if (d > thr) flushJumps += 1
  }
  res.flush = { jumps: flushJumps, maxJump: +flushMax.toFixed(4) }
  res.totals = { jumps: jumpsTotal + flushJumps, hardGapEdges: hardEdgesTotal, gaps: gapsTotal, gapMs: +gapMsTotal.toFixed(1) }
  // Optimistic supply-only counterfactual, not a DSP simulation. Actual
  // main-thread arrival frames include scheduling jitter; worklet dispatch
  // and FIR lookahead can only reduce the available reserve further.
  // Compare a constant minimum rate from audible onset, which bounds what
  // a causal controller constrained to that rate could possibly save.
  if (!Array.isArray(arrivals) || arrivals.length === 0) throw Error("Missing packet arrival evidence")
  const startFrames = [r1Start, r2Start]
  res.rateFeasibility = [0, 1].map(reply => {
    const packets = arrivals.filter(a => a.reply === reply)
    if (!packets.length || packets.some((a,i) => !Number.isSafeInteger(a.frame) || a.frame < 0 || !Number.isSafeInteger(a.byteLength) || a.byteLength <= 0 || (i && a.frame < packets[i-1].frame))) throw Error("Invalid packet arrival evidence")
    const start = startFrames[reply]
    const end = reply === 0 ? flushFrame : last
    const bounds = [1, .99, .97, .95].map(rate => {
      let bytes = 0, maxDeficitFrames = 0
      for (const a of packets) {
        if (a.frame > end) break
        if (start >= 0 && a.frame > start) {
          const supplied = Math.floor(bytes / 2) * sampleRate / 24000
          maxDeficitFrames = Math.max(maxDeficitFrames, (a.frame-start)*rate-supplied)
        }
        bytes += a.byteLength
      }
      return { rate, maxSupplyDeficitMs: maxDeficitFrames * 1000 / sampleRate }
    })
    return { reply, audibleStartFrame: start, packetCount: packets.length, bounds }
  })
  return res
}

const matrix = []
const seeds = quick ? [1] : [1, 2, 3]
for (const pacing of [2, 1])
  for (const ctxRate of [48000, 44100])
    for (const oddSplit of [false, true])
      for (const seed of seeds)
        for (const impl of enforce ? ["after"] : ["before", "after"])
          matrix.push({ impl, ctxRate, seed, oddSplit, pacing, replyS: 6, flushAtS: 3.2, secondReplyDelayS: 0.4, secondReplyS: 2.5, jitterMaxMs: 300 })

if (compare) {
  matrix.length = 0
  for (const pacing of [1, 2])
    for (const ctxRate of [44100, 48000])
      for (const oddSplit of [false, true])
        for (const seed of (shardSeed === null ? [1, 2, 3] : [shardSeed]))
          for (const jitterProfile of ["clean", "uniform", "burst"])
            // Rotate policy order deterministically to reduce systematic runner bias.
            for (const policy of ["baseline", "fixed", "adaptive"].map((_, i, a) => a[(i + seed) % a.length]))
              matrix.push({ impl: "after", policy, jitterProfile, pacing, ctxRate, oddSplit, seed, replyS: 6, flushAtS: 3.2, secondReplyDelayS: 0.4, secondReplyS: 2.5, jitterMaxMs: 300 })
}
const results = []
const label = (sc) => `${sc.impl} x${sc.pacing} ${sc.ctxRate} ${sc.oddSplit ? "odd" : "even"} seed=${sc.seed} policy=${sc.policy ?? "default"} jitter=${sc.jitterProfile ?? "uniform"}`
const filter = process.env.SCENARIO_FILTER ? new RegExp(process.env.SCENARIO_FILTER) : null
for (const sc of matrix) {
  if (filter && !filter.test(label(sc))) continue
  const raw = await page.evaluate((s) => window.runScenario(s), sc)
  const metrics = analyse(raw)
  results.push({ scenario: sc, playerKind: raw.playerKind, recordedS: +(raw.samples.length / raw.sampleRate).toFixed(2), metrics, arrivals: raw.arrivals })
  console.log(
    `${label(sc)} [${results.length}/${matrix.length}] [${raw.playerKind}]`,
    `jumps=${metrics.totals.jumps} hardGapEdges=${metrics.totals.hardGapEdges} gaps=${metrics.totals.gaps} gapMs=${metrics.totals.gapMs}`,
    `flushJumps=${metrics.flush.jumps} flushMax=${metrics.flush.maxJump} startupMs=${metrics.firstStartupMs}/${metrics.secondStartupMs} replyGapMs=${metrics.reply1.gapMs}/${metrics.reply2.gapMs}`,
  )
}
await browser.close()
server.close()
const violations = []
if (enforce || compare) {
  for (const { scenario, playerKind, metrics } of results) {
    const fail = (reason) => violations.push({ scenario, reason })
    if (playerKind !== "worklet") fail("expected AudioWorklet player")
    if (metrics.reply1.missing || metrics.reply2.missing) fail("missing audible reply")
    if (metrics.totals.jumps !== 0) fail("waveform discontinuity")
    if (metrics.totals.hardGapEdges !== 0) fail("hard silence edge")
    if (metrics.totals.gapMs > 20) fail("synthetic in-reply silence exceeds 20 ms")
    if (metrics.flush.jumps !== 0) fail("interruption discontinuity")
    if (metrics.residualMs > 50) fail("old reply audible more than 50 ms after flush")
    if (metrics.secondReplySpanMs < scenario.secondReplyS * 1000 - 50) fail("second reply truncated")
  }
  if (results.length !== matrix.length || !results.length) violations.push({ reason: "incomplete matrix" })
}
const comparison = compare ? Object.fromEntries(["baseline", "fixed", "adaptive"].map(policy => {
  const rows = results.filter(r => r.scenario.policy === policy)
  const startup = rows.flatMap(r => [r.metrics.firstStartupMs, r.metrics.secondStartupMs]).filter(Number.isFinite).sort((a,b) => a-b)
  const percentile = p => startup.length ? startup[Math.ceil(startup.length*p)-1] : null
  const failures = violations.filter(v => v.scenario?.policy === policy)
  return [policy, { scenarios: rows.length, p50StartupMs: percentile(.5), p95StartupMs: percentile(.95), failedScenarios: new Set(failures.map(v => JSON.stringify(v.scenario))).size, totalGapMs: rows.reduce((s,r) => s+r.metrics.totals.gapMs,0), maxResidualMs: Math.max(0,...rows.map(r=>r.metrics.residualMs)) }]
})) : null
if (outPath) await writeFile(outPath, JSON.stringify({ synthetic: true, enforced: enforce, comparison, sourceSha: process.env.VOICE_DUPLEX_SOURCE_SHA ?? null, shardSeed, violations, generatedAt: new Date().toISOString(), results }, null, 2))
if (violations.length && !compare) {
  console.error(JSON.stringify(violations))
  process.exitCode = 1
}
