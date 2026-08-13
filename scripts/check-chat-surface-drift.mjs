#!/usr/bin/env node
/**
 * Fail CI when a chat surface re-implements composer voice chrome instead of
 * importing SharedChatComposerControls (in-input waveform + orb).
 * Also fail if Text|Voice toggle, Speak mic, or Dictate is reintroduced on surfaces.
 */
import { readdirSync, readFileSync, statSync } from "node:fs"
import { join, relative, dirname } from "node:path"
import { fileURLToPath } from "node:url"

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..")
const WEB = join(ROOT, "apps", "web")

const ALLOWED_DEFINITIONS = new Set([
  "components/gravitre/assistant/shared-chat-composer-controls.tsx",
  "components/gravitre/assistant/voice-mode-toggle.tsx",
  "components/gravitre/assistant/voice-input-button.tsx",
  "components/gravitre/assistant/voice-session-presence.tsx",
  "app/e2e/shots/voice-states/page.tsx",
])

// The one component allowed to own assistant-avatar rendering, plus the
// transcript that declares the prop and the shot harness that drives states.
const AVATAR_DEFINITIONS = new Set([
  "components/gravitre/assistant/gravitre-chat-avatar.tsx",
  "components/gravitre/assistant/chat-transcript.tsx",
  "app/e2e/shots/avatar-states/page.tsx",
])

// The only files allowed to render voice waveform bars or mount the orb. The
// waveform previously existed twice (a 5-bar copy inside voice-session-presence
// plus the 7-bar spec version), which is how the handoff and the shipped UI
// drifted apart the moment the spec landed.
const VOICE_UI_DEFINITIONS = new Set([
  "components/gravitre/assistant/voice-presentation.tsx",
  "app/e2e/shots/voice-states/page.tsx",
])

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    if (name === "node_modules" || name === ".next" || name === "dist") continue
    const p = join(dir, name)
    const st = statSync(p)
    if (st.isDirectory()) walk(p, out)
    else if (/\.(tsx|jsx)$/.test(name)) out.push(p)
  }
  return out
}

const files = walk(join(WEB, "app")).concat(walk(join(WEB, "components")))
const failures = []

for (const file of files) {
  const rel = relative(WEB, file).replace(/\\/g, "/")
  if (rel.includes("__tests__") || rel.includes(".test.")) continue
  const src = readFileSync(file, "utf8")

  // Voice-presentation rules run BEFORE the composer-chrome exemption below.
  // ALLOWED_DEFINITIONS grants the right to define composer chrome, not to own a
  // private copy of the waveform — and voice-session-presence.tsx, which is on
  // that list, is exactly where the duplicate 5-bar waveform used to live. Running
  // these after the `continue` left that file permanently exempt: I proved it by
  // reinserting a hand-rolled bar there and watching the guard report PASS.
  if (!VOICE_UI_DEFINITIONS.has(rel)) {
    if (/gv-wave-bar/.test(src)) {
      failures.push(
        `${rel}: hand-rolls waveform bars — import GravitreVoiceWaveform from voice-presentation`,
      )
    }
    if (
      /<VoiceOrbTakeover\b/.test(src) &&
      rel !== "components/gravitre/assistant/shared-chat-composer-controls.tsx"
    ) {
      failures.push(
        `${rel}: mounts <VoiceOrbTakeover> outside SharedChatComposerControls — voice presentation must stay shared`,
      )
    }
  }

  if (ALLOWED_DEFINITIONS.has(rel)) continue

  // Text|Voice toggle is retired — waveform inside SharedChatComposerControls is the control.
  if (
    /<VoiceModeToggle\b/.test(src) &&
    rel !== "components/gravitre/assistant/voice-mode-toggle.tsx"
  ) {
    failures.push(`${rel}: mounts retired <VoiceModeToggle> — use in-input waveform via SharedChatComposerControls`)
  }

  // Speak mic button is retired — same path as waveform.
  if (
    /<VoiceInputButton\b/.test(src) &&
    rel !== "components/gravitre/assistant/voice-input-button.tsx"
  ) {
    failures.push(`${rel}: mounts retired <VoiceInputButton> — use in-input waveform via SharedChatComposerControls`)
  }

  // Dictate product must stay gone from customer chat UI
  if (/\bDictate\b/.test(src) && !rel.includes("docs/")) {
    failures.push(`${rel}: contains Dictate label/copy — in-input waveform is the only mic path`)
  }

  // Duplicate composer chrome: local Text|Voice label clusters outside shared path
  if (
    /Text\s*\|\s*Voice/.test(src) &&
    !src.includes("shared-chat-composer-controls") &&
    !rel.includes("voice-mode-toggle")
  ) {
    if (/setModality|modality === ["']voice["']/.test(src) && /<button[^>]*Voice/.test(src)) {
      failures.push(`${rel}: custom Text|Voice markup — use SharedChatComposerControls`)
    }
  }

  // ── Avatar drift ───────────────────────────────────────────────────────────
  // Chat threads always use GravitreChatAvatar (mark + states). Per-agent icons
  // belong on hub/cards, not in the transcript. Labels carry the agent name.

  // 1. Pre-rendered avatar nodes are banned — they drop animated states.
  if (/\bassistantAvatar\s*[=:]/.test(src) && !AVATAR_DEFINITIONS.has(rel)) {
    failures.push(
      `${rel}: passes assistantAvatar (pre-rendered node) — use GravitreChatAvatar via ChatTranscript`,
    )
  }

  // 2. Do not pass per-agent icon identity into the transcript avatar path.
  //    (Headers/hub cards may still use AgentIdentityAvatar in the same file.)
  if (/\bassistantAgent\s*=/.test(src) && !AVATAR_DEFINITIONS.has(rel)) {
    failures.push(
      `${rel}: passes assistantAgent — chat avatar is always Gravitre mark; use assistantLabel for the name only`,
    )
  }
}

// 3. The shared avatar must keep supporting every real pipeline state. Losing one
//    (e.g. dropping `searching` back to a decorative loop) is the same class of
//    silent regression, so the states are asserted explicitly.
{
  const rel = "components/gravitre/assistant/gravitre-chat-avatar.tsx"
  let src = ""
  try {
    src = readFileSync(join(WEB, rel), "utf8")
  } catch {
    failures.push(`${rel}: missing shared stateful avatar component`)
    src = ""
  }
  if (src) {
    for (const state of ["idle", "thinking", "searching", "speaking"]) {
      if (!new RegExp(`["']${state}["']`).test(src)) {
        failures.push(`${rel}: no longer supports the "${state}" avatar state`)
      }
    }
    // Chat avatar is always the Gravitre mark — not a per-agent identity disc.
    if (/<AgentIdentityAvatar\b/.test(src)) {
      failures.push(
        `${rel}: must not render AgentIdentityAvatar — chat discs are always the Gravitre mark`,
      )
    }
    if (!src.includes("gravitre-mark-white.png")) {
      failures.push(`${rel}: must render the Gravitre mark asset`)
    }
    if (!src.includes("useReducedMotion")) {
      failures.push(`${rel}: must honour prefers-reduced-motion`)
    }
  }
}

// 4. Voice motion must stay OPT-IN. This looks pedantic and is not: the original
//    implementation switched animation off under `prefers-reduced-motion: reduce`,
//    which never applied. The per-bar rules carry `:nth-child(N)` (0,2,0), a media
//    query adds no specificity, and raising the override to `:nth-child(n)` was
//    then deleted by Lightning CSS, which correctly simplifies it to the bare
//    class. Assigning animation only inside `no-preference` removes the cascade
//    fight entirely, so this rule pins that structure rather than the outcome.
{
  const rel = "app/globals.css"
  let css = ""
  try {
    css = readFileSync(join(WEB, rel), "utf8")
  } catch {
    failures.push(`${rel}: missing global stylesheet`)
    css = ""
  }
  if (css) {
    const noPref = css.match(/@media\s*\(prefers-reduced-motion:\s*no-preference\)\s*\{[\s\S]*?\n\s*\}/)
    if (!noPref || !/animation-name:\s*gv-wave/.test(noPref[0])) {
      failures.push(
        `${rel}: gv-wave animation-name must be assigned ONLY inside @media (prefers-reduced-motion: no-preference) — a "reduce" override loses to :nth-child specificity and is stripped by the CSS minifier`,
      )
    }
    // The orbs use plain classes, so an equal-specificity override does work for
    // them — but it has to still be there.
    if (!/@media\s*\(prefers-reduced-motion:\s*reduce\)[\s\S]*?gv-orb-/.test(css)) {
      failures.push(`${rel}: orb animation must be disabled under prefers-reduced-motion: reduce`)
    }
  }
}

// Required import sites (must exist and import shared controls)
const requiredImporters = [
  "app/ai/_components/ai-workspace.tsx",
  "app/agents/[id]/chat/page.tsx",
]
for (const rel of requiredImporters) {
  const full = join(WEB, rel)
  let src = ""
  try {
    src = readFileSync(full, "utf8")
  } catch {
    failures.push(`${rel}: missing required chat surface`)
    continue
  }
  if (!src.includes("SharedChatComposerControls")) {
    failures.push(`${rel}: must import/use SharedChatComposerControls`)
  }
  if (!src.includes("spoken_mode")) {
    failures.push(`${rel}: must send spoken_mode on chat transport when Voice modality is active`)
  }
  if (!/assistantLabel=\{/.test(src)) {
    failures.push(`${rel}: must pass assistantLabel into ChatTranscript (persona / agent name)`)
  }
  if (!/agentLabel=\{/.test(src)) {
    failures.push(`${rel}: must pass agentLabel into SharedChatComposerControls for You/agent pills`)
  }
  // Text streaming must not fake Voice "speaking" chrome (11a/11b live floor).
  if (/ttsSpeaking\s*\|\|\s*isStreaming/.test(src) && !/modality\s*===\s*["']voice["']/.test(src)) {
    failures.push(
      `${rel}: voicePresence speaking must gate isStreaming on modality === "voice" (or use ttsSpeaking alone)`,
    )
  }
  if (/\bDictate\b|\bonDictateError\b/.test(src)) {
    failures.push(`${rel}: Dictate affordance must remain removed`)
  }
}

if (failures.length) {
  console.error("chat-surface-drift FAIL:")
  for (const f of failures) console.error(" -", f)
  process.exit(1)
}
console.log("chat-surface-drift PASS")
process.exit(0)
