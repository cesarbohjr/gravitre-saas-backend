/**
 * GRAVITRE_AI_FLOAT_ENABLED — Phase 5 feature flag.
 *
 * Phase 5 default ON (`!== "false"`). Kill-switch: set env to exact `"false"`.
 */
import { afterEach, describe, expect, it, vi } from "vitest"

const ENV_KEY = "NEXT_PUBLIC_AI_FLOAT_ENABLED"
const originalValue = process.env[ENV_KEY]

afterEach(() => {
  if (originalValue === undefined) {
    delete process.env[ENV_KEY]
  } else {
    process.env[ENV_KEY] = originalValue
  }
  vi.resetModules()
})

describe("GRAVITRE_AI_FLOAT_ENABLED", () => {
  it("defaults to enabled (true) when the env var is unset — Phase 5 rollout", async () => {
    delete process.env[ENV_KEY]
    vi.resetModules()
    const { GRAVITRE_AI_FLOAT_ENABLED } = await import("@/lib/ai-workspace-flags")
    expect(GRAVITRE_AI_FLOAT_ENABLED).toBe(true)
  })

  it("disables only when explicitly set to the exact string 'false'", async () => {
    process.env[ENV_KEY] = "false"
    vi.resetModules()
    const { GRAVITRE_AI_FLOAT_ENABLED } = await import("@/lib/ai-workspace-flags")
    expect(GRAVITRE_AI_FLOAT_ENABLED).toBe(false)
  })

  it("stays enabled for other truthy-ish values including 'true'", async () => {
    for (const value of ["true", "1", "TRUE", "yes", ""]) {
      process.env[ENV_KEY] = value
      vi.resetModules()
      const { GRAVITRE_AI_FLOAT_ENABLED } = await import("@/lib/ai-workspace-flags")
      expect(GRAVITRE_AI_FLOAT_ENABLED).toBe(true)
    }
  })
})
