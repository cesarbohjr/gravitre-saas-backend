#!/usr/bin/env node
/**
 * Fail CI when a chat surface re-implements VoiceModeToggle / Speak mic / presence
 * chrome instead of importing SharedChatComposerControls.
 * Also fail if a separate "Dictate" affordance is reintroduced.
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
  if (ALLOWED_DEFINITIONS.has(rel)) continue
  if (rel.includes("__tests__") || rel.includes(".test.")) continue
  const src = readFileSync(file, "utf8")

  // Surfaces that mount VoiceModeToggle must go through SharedChatComposerControls
  if (/<VoiceModeToggle\b/.test(src) && !src.includes("SharedChatComposerControls")) {
    failures.push(`${rel}: mounts <VoiceModeToggle> without SharedChatComposerControls`)
  }

  // Speak mic only via shared controls
  if (/<VoiceInputButton\b/.test(src) && !src.includes("SharedChatComposerControls")) {
    failures.push(`${rel}: mounts <VoiceInputButton> without SharedChatComposerControls`)
  }

  // Dictate product must stay gone from customer chat UI
  if (/\bDictate\b/.test(src) && !rel.includes("docs/")) {
    failures.push(`${rel}: contains Dictate label/copy — Voice modality Speak only`)
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

  // ── Avatar drift (the gap that let this regression ship) ────────────────────
  // The guard covered composer chrome but said nothing about avatars, so main
  // chat's assistant avatar could regress to a static mark while department chat
  // kept its rich one, and CI stayed green. These three rules close that.

  // 1. The `assistantAvatar` prop was the escape hatch: passing a pre-rendered
  //    node replaced the stateful avatar wholesale and silently dropped every
  //    animated state. Identity must travel as data (`assistantAgent`) instead.
  if (/\bassistantAvatar\s*[=:]/.test(src) && !AVATAR_DEFINITIONS.has(rel)) {
    failures.push(
      `${rel}: passes assistantAvatar (pre-rendered node) — use assistantAgent so identity and state compose`,
    )
  }

  // 2. A chat transcript surface must not hand-roll an assistant avatar. Anything
  //    rendering AgentIdentityAvatar as the *transcript* avatar bypasses the
  //    state layer; the identity avatar is still fine for headers and hub cards.
  if (
    /<ChatTranscript\b/.test(src) &&
    /<AgentIdentityAvatar\b/.test(src) &&
    !src.includes("assistantAgent")
  ) {
    failures.push(
      `${rel}: renders <ChatTranscript> with a local <AgentIdentityAvatar> avatar — pass assistantAgent instead`,
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
    // Identity must compose, not be replaced: this component has to keep
    // delegating to the shared identity avatar rather than reimplementing it.
    if (!src.includes("AgentIdentityAvatar")) {
      failures.push(`${rel}: must render AgentIdentityAvatar for named agents (one identity implementation)`)
    }
    if (!src.includes("useReducedMotion")) {
      failures.push(`${rel}: must honour prefers-reduced-motion`)
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
