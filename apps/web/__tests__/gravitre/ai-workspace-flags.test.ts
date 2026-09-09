/**
 * GRAVITRE_AI_FLOAT_ENABLED — Phase 2 feature flag. See
 * lib/ai-workspace-flags.ts.
 *
 * The flag is read once at module scope (`process.env...` evaluated at
 * import time, same pattern as lib/marketing-flags.ts), so each case here
 * resets the module registry and re-imports after setting/clearing the env
 * var, rather than mutating the already-imported constant.
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
  it("defaults to disabled (false) when the env var is unset — this is the safety-critical case", async () => {
    delete process.env[ENV_KEY]
    vi.resetModules()
    const { GRAVITRE_AI_FLOAT_ENABLED } = await import("@/lib/ai-workspace-flags")
    expect(GRAVITRE_AI_FLOAT_ENABLED).toBe(false)
  })

  it("stays disabled for any value other than the exact string 'true'", async () => {
    for (const value of ["false", "1", "TRUE", "yes", ""]) {
      process.env[ENV_KEY] = value
      vi.resetModules()
      const { GRAVITRE_AI_FLOAT_ENABLED } = await import("@/lib/ai-workspace-flags")
      expect(GRAVITRE_AI_FLOAT_ENABLED).toBe(false)
    }
  })

  it("enables only when explicitly set to 'true'", async () => {
    process.env[ENV_KEY] = "true"
    vi.resetModules()
    const { GRAVITRE_AI_FLOAT_ENABLED } = await import("@/lib/ai-workspace-flags")
    expect(GRAVITRE_AI_FLOAT_ENABLED).toBe(true)
  })
})
