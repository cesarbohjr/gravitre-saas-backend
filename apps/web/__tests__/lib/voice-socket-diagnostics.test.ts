import { beforeEach, describe, expect, it, vi } from "vitest"
import {
  clearVoiceSocketFailures,
  readVoiceSocketFailures,
  recordVoiceSocketFailure,
  redactVoiceWsUrl,
} from "@/lib/voice-socket-diagnostics"

const TOKEN = "eyJhbGciOiJIUzI1NiJ9.super-secret-payload.sig"
const REAL_URL = `wss://api.gravitre.app/api/voice/pipecat/ws?access_token=${TOKEN}&org_id=abc`

beforeEach(() => {
  clearVoiceSocketFailures()
  vi.spyOn(console, "warn").mockImplementation(() => {})
})

describe("redactVoiceWsUrl", () => {
  it("keeps origin and path, which is what distinguishes the candidate causes", () => {
    // wss://api.gravitre.app (reachable) vs wss://gravitre.app (404 on upgrade)
    // is the whole question, and it lives entirely in the origin.
    const out = redactVoiceWsUrl(REAL_URL)
    expect(out).toContain("wss://api.gravitre.app")
    expect(out).toContain("/api/voice/pipecat/ws")
  })

  it("never emits the access token", () => {
    // The token rides in the query string, so an unredacted URL in a console log
    // or a pasted bug report is a live credential leak.
    const out = redactVoiceWsUrl(REAL_URL)
    expect(out).not.toContain(TOKEN)
    expect(out).not.toContain("super-secret-payload")
  })

  it("still shows which parameters were present, without their values", () => {
    const out = redactVoiceWsUrl(REAL_URL)
    expect(out).toContain("access_token=<redacted>")
    expect(out).toContain("org_id=<redacted>")
  })

  it("handles a missing or unparseable url without throwing", () => {
    expect(redactVoiceWsUrl(null)).toBe("(none)")
    expect(redactVoiceWsUrl("")).toBe("(none)")
    expect(redactVoiceWsUrl("   ")).toBe("(none)")
    expect(redactVoiceWsUrl("not a url")).toBe("(unparseable)")
  })
})

describe("recordVoiceSocketFailure", () => {
  const base = {
    event: "close" as const,
    url: "wss://api.gravitre.app/api/voice/pipecat/ws",
    everOpened: true,
    attempt: 0,
    intentional: false,
    sessionWanted: true,
    lastServerError: null,
  }

  it("keeps the close code, which is the fact the diagnosis turns on", () => {
    recordVoiceSocketFailure({ ...base, code: 1006, wasClean: false })
    const [entry] = readVoiceSocketFailures()
    expect(entry.code).toBe(1006)
    expect(entry.wasClean).toBe(false)
    expect(entry.at).toMatch(/^\d{4}-\d{2}-\d{2}T/)
  })

  it("distinguishes a clean close after a server explanation from an unclean drop", () => {
    recordVoiceSocketFailure({
      ...base,
      code: 1000,
      wasClean: true,
      lastServerError: "Deepgram flux failed to start",
    })
    recordVoiceSocketFailure({ ...base, code: 1006, wasClean: false })
    const entries = readVoiceSocketFailures()
    expect(entries).toHaveLength(2)
    expect(entries[0].lastServerError).toBe("Deepgram flux failed to start")
    expect(entries[1].lastServerError).toBeNull()
  })

  it("stays bounded so a reconnect loop cannot grow without limit", () => {
    for (let i = 0; i < 50; i += 1) recordVoiceSocketFailure({ ...base, attempt: i })
    const entries = readVoiceSocketFailures()
    expect(entries).toHaveLength(20)
    // Oldest dropped, newest kept.
    expect(entries.at(-1)?.attempt).toBe(49)
  })
})
