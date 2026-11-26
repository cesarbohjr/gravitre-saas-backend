import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { buildPipecatVoiceWsUrl, resolvePipecatWsOrigin } from "@/lib/pipecat-voice-client"
import { getAccessToken } from "@/lib/auth-context"
import { getSelectedOrgFromStorage } from "@/lib/org-context"
import type { VoiceStatus } from "@/lib/tier1-voice-client"

vi.mock("@/lib/auth-context", () => ({ getAccessToken: vi.fn() }))
vi.mock("@/lib/org-context", () => ({ getSelectedOrgFromStorage: vi.fn() }))
const token = vi.mocked(getAccessToken)
const org = vi.mocked(getSelectedOrgFromStorage)
const status = (hint: string, path?: string) => ({ pipecat_ws_hint: hint, pipecat_ws_path: path }) as VoiceStatus
beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_VOICE_WS_BASE", "")
  vi.stubEnv("NEXT_PUBLIC_BACKEND_WS_URL", "")
  token.mockReset().mockResolvedValue("fixture-token")
  org.mockReset().mockReturnValue({ id: "org-a" } as ReturnType<typeof getSelectedOrgFromStorage>)
})
afterEach(() => vi.unstubAllEnvs())

describe("DEC-015 credential destination and reconnect scope", () => {
  it("uses canonical production origin and scopes every new URL", async () => {
    const built = await buildPipecatVoiceWsUrl({ status: status("wss://api.gravitre.app"), agentId: "agent-a", conversationId: "conv-a" })
    expect(built).toHaveProperty("url")
    if (!("url" in built)) throw new Error("missing URL")
    const url = new URL(built.url)
    expect(url.origin).toBe("wss://api.gravitre.app")
    expect(url.pathname).toBe("/api/voice/pipecat/ws")
    expect(Object.fromEntries(url.searchParams)).toEqual({access_token:"fixture-token",org_id:"org-a",agent_id:"agent-a",conversation_id:"conv-a"})
    token.mockResolvedValue("fresh-token")
    const next = await buildPipecatVoiceWsUrl({})
    expect("url" in next && new URL(next.url).searchParams.get("access_token")).toBe("fresh-token")
  })
  it.each(["wss://foreign.example.invalid", "ws://api.gravitre.app", "wss://api.gravitre.app@foreign.example.invalid", "wss://api.gravitre.app/other", "wss://api.gravitre.app?x=1", "wss://api.gravitre.app#x"])("rejects hint %s before fetching token", async hint => {
    expect(await buildPipecatVoiceWsUrl({status:status(hint)})).toHaveProperty("error")
    expect(token).not.toHaveBeenCalled()
  })
  it.each(["//foreign.example.invalid", "/api/voice/pipecat/ws?x=1", "/api/voice/other", "/api/voice/pipecat/ws#x"])("rejects route %s", async path => {
    expect(await buildPipecatVoiceWsUrl({path})).toHaveProperty("error")
    expect(token).not.toHaveBeenCalled()
  })
  it("preserves explicitly configured staging and loopback destinations", () => {
    vi.stubEnv("NEXT_PUBLIC_VOICE_WS_BASE", "https://qa.example.invalid")
    expect(resolvePipecatWsOrigin(status("wss://foreign.example.invalid"))).toBe("wss://qa.example.invalid")
    vi.stubEnv("NEXT_PUBLIC_VOICE_WS_BASE", "http://localhost:8000")
    expect(resolvePipecatWsOrigin()).toBe("ws://localhost:8000")
  })
  it("refuses an org change while authentication is pending", async () => {
    org.mockReturnValueOnce({id:"org-a"} as ReturnType<typeof getSelectedOrgFromStorage>)
       .mockReturnValueOnce({id:"org-b"} as ReturnType<typeof getSelectedOrgFromStorage>)
    expect(await buildPipecatVoiceWsUrl({})).toEqual({error:"Organization changed; restart voice"})
  })
})
