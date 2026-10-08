import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

import {
  lastAssistantMessageId,
  reconcileClaimOnConversationChange,
  shouldAutoSpeakReply,
} from "@/lib/voice-auto-tts"

const webRoot = resolve(__dirname, "../..")
const hook = readFileSync(resolve(webRoot, "hooks/use-voice-duplex-session.ts"), "utf8")
const workspace = readFileSync(resolve(webRoot, "app/(app)/ai/_components/ai-workspace.tsx"), "utf8")

/** Body of the first `marker {` block, matched by brace depth. */
function blockAfter(source: string, marker: string): string {
  const start = source.indexOf(marker)
  expect(start, `missing ${marker}`).toBeGreaterThanOrEqual(0)
  const open = source.indexOf("{", start + marker.length - 1)
  let depth = 0
  for (let i = open; i < source.length; i += 1) {
    if (source[i] === "{") depth += 1
    if (source[i] === "}") {
      depth -= 1
      if (depth === 0) return source.slice(open, i + 1)
    }
  }
  throw new Error(`unbalanced block after ${marker}`)
}

const conversation = [
  { id: "u1", role: "user" },
  { id: "a1", role: "assistant" }, // "You have 1,234 companies in HubSpot."
]

describe("opening voice speaks nothing on its own", () => {
  it("arming Voice on a conversation with a stored reply does not read it aloud", () => {
    expect(
      shouldAutoSpeakReply({
        lastAssistantId: lastAssistantMessageId(conversation),
        lastSpokenId: null,
        claim: null,
      }),
    ).toBe(false)
  })

  it("speaks only the reply to a turn sent with Voice armed", () => {
    const claim = { kind: "after" as const, afterAssistantId: lastAssistantMessageId(conversation) }
    // Turn failed or still pending: the old reply is still last and stays silent.
    expect(shouldAutoSpeakReply({ lastAssistantId: "a1", lastSpokenId: null, claim })).toBe(false)
    expect(shouldAutoSpeakReply({ lastAssistantId: "a2", lastSpokenId: null, claim })).toBe(true)
    expect(shouldAutoSpeakReply({ lastAssistantId: "a2", lastSpokenId: "a2", claim })).toBe(false)
  })

  it("a live turn whose audio never played may be spoken, and only that message", () => {
    const claim = { kind: "message" as const, messageId: "voice-assistant-1" }
    expect(shouldAutoSpeakReply({ lastAssistantId: "voice-assistant-1", lastSpokenId: null, claim })).toBe(true)
    expect(shouldAutoSpeakReply({ lastAssistantId: "a1", lastSpokenId: null, claim })).toBe(false)
  })

  it("the workspace auto-TTS effect is gated on a claim, set only by a voice-armed send", () => {
    expect(workspace).toMatch(/shouldAutoSpeakReply\(\{/)
    expect(workspace).toMatch(/claim: voiceReplyClaimRef\.current/)
    expect(workspace).toMatch(
      /voiceReplyClaimRef\.current =\s*modalityRef\.current === "voice"\s*\?\s*\{ kind: "after"/,
    )
  })
})

describe("connecting the Pipecat voice session sends no text turn", () => {
  it("the socket open handler sends nothing", () => {
    const onOpenBodies = hook.split("ws.onopen = () => {").slice(1)
    expect(onOpenBodies.length).toBeGreaterThanOrEqual(1)
    for (const body of onOpenBodies) {
      const block = blockAfter(`ws.onopen = () => {${body}`, "ws.onopen = () => {")
      expect(block).not.toMatch(/\.send\(/)
    }
  })

  it("session.ready only records the conversation id", () => {
    const ready = blockAfter(hook, 'if (kind === "session.ready") {')
    expect(ready).not.toMatch(/\.send\(/)
    expect(ready).not.toMatch(/submitFinalTranscript|runSessionTurn/)
  })

  it("the only text frame the hook sends is an explicit submitFinalTranscript call", () => {
    const textSends = hook.match(/type: "text"/g) || []
    expect(textSends).toHaveLength(1)
    const submit = blockAfter(hook, "submitFinalTranscript: async (text: string, opts?: { speculative?: boolean }) => {")
    expect(submit).toMatch(/ws\.send\(JSON\.stringify\(\{ type: "text", text: trimmed \}\)\)/)
    expect(submit).toMatch(/if \(!trimmed\) return/)
  })
})

describe("voice reply claims stay in their conversation", () => {
  const claim = { kind: "after" as const, afterAssistantId: "a1" }

  it("a new chat's claim adopts the id the chat gets", () => {
    expect(reconcileClaimOnConversationChange({ claim, owner: null, next: "c-new" })).toEqual({
      claim,
      owner: "c-new",
    })
  })

  it("switching to another conversation drops the claim", () => {
    expect(reconcileClaimOnConversationChange({ claim, owner: "c1", next: "c2" })).toEqual({
      claim: null,
      owner: null,
    })
  })

  it("the same conversation keeps it", () => {
    expect(reconcileClaimOnConversationChange({ claim, owner: "c1", next: "c1" }).claim).toBe(claim)
  })

  it("the workspace reconciles the claim when the active conversation changes", () => {
    expect(workspace).toMatch(/reconcileClaimOnConversationChange\(\{/)
  })
})
