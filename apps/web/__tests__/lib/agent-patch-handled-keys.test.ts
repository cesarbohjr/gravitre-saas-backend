import { describe, expect, it } from "vitest"
import {
  AGENT_PATCH_HANDLED_KEYS,
  agentPatchBodyIsHandled,
} from "@/lib/agent-patch-handled-keys"

describe("agent-patch-handled-keys", () => {
  it("includes knowledge pack keys so PATCH stays on Supabase path", () => {
    expect(AGENT_PATCH_HANDLED_KEYS).toContain("knowledgePacks")
    expect(AGENT_PATCH_HANDLED_KEYS).toContain("knowledge_packs")
  })

  it("recognizes camelCase knowledgePacks as handled", () => {
    expect(agentPatchBodyIsHandled({ knowledgePacks: ["pack.sales"] }, {})).toBe(true)
  })

  it("recognizes snake_case knowledge_packs as handled", () => {
    expect(agentPatchBodyIsHandled({}, { knowledge_packs: ["pack.sales"] })).toBe(true)
  })

  it("returns false for unhandled agent fields that must proxy to FastAPI", () => {
    expect(agentPatchBodyIsHandled({ trainingProfile: {} }, {})).toBe(false)
  })
})
