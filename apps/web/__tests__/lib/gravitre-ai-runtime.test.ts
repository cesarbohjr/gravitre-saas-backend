import { describe, expect, it, beforeEach } from "vitest"
import {
  CANONICAL_AI_RUNTIME_OWNER_ID,
  getGravitreAiLiveRuntimeCount,
  getGravitreAiLiveRuntimeOwnerIds,
  recordCanonicalChatSubmit,
  registerGravitreAiChatRuntime,
  resetGravitreAiChatRuntimeRegistryForTests,
  getGravitreAiRuntimeDebugSnapshot,
} from "@/lib/gravitre-ai-runtime"

describe("canonical AI runtime registry", () => {
  beforeEach(() => {
    resetGravitreAiChatRuntimeRegistryForTests()
  })

  it("starts empty", () => {
    expect(getGravitreAiLiveRuntimeCount()).toBe(0)
  })

  it("counts one live instance and unregisters on dispose", () => {
    const dispose = registerGravitreAiChatRuntime(CANONICAL_AI_RUNTIME_OWNER_ID)
    expect(getGravitreAiLiveRuntimeCount()).toBe(1)
    expect(getGravitreAiLiveRuntimeOwnerIds()).toEqual([CANONICAL_AI_RUNTIME_OWNER_ID])
    const id = getGravitreAiRuntimeDebugSnapshot().currentInstanceId
    expect(id).toBeTruthy()
    dispose()
    expect(getGravitreAiLiveRuntimeCount()).toBe(0)
    expect(getGravitreAiRuntimeDebugSnapshot().unmountCount).toBe(1)
    expect(getGravitreAiRuntimeDebugSnapshot().mountCount).toBe(1)
  })

  it("counts two mounts of the same owner id as two live instances — the duplication this exists to catch", () => {
    registerGravitreAiChatRuntime(CANONICAL_AI_RUNTIME_OWNER_ID)
    registerGravitreAiChatRuntime(CANONICAL_AI_RUNTIME_OWNER_ID)
    expect(getGravitreAiLiveRuntimeCount()).toBe(2)
    expect(getGravitreAiLiveRuntimeOwnerIds()).toEqual([CANONICAL_AI_RUNTIME_OWNER_ID])
  })

  it("records chat submits separately from mount count", () => {
    registerGravitreAiChatRuntime(CANONICAL_AI_RUNTIME_OWNER_ID)
    recordCanonicalChatSubmit({ surface: "ai_chat" })
    recordCanonicalChatSubmit({ surface: "ai_chat" })
    expect(getGravitreAiRuntimeDebugSnapshot().chatSubmitCount).toBe(2)
    expect(getGravitreAiLiveRuntimeCount()).toBe(1)
  })
})
