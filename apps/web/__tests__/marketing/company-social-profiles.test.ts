import { describe, expect, it } from "vitest"
import { GRAVITRE_SOCIAL_PROFILES } from "@/lib/company-social-profiles"

describe("Gravitre official social profiles", () => {
  it("provides at least three distinct absolute HTTPS company profile URLs", () => {
    expect(GRAVITRE_SOCIAL_PROFILES.length).toBeGreaterThanOrEqual(3)
    const urls = GRAVITRE_SOCIAL_PROFILES.map((profile) => profile.url)
    expect(new Set(urls).size).toBe(urls.length)
    for (const url of urls) {
      const parsed = new URL(url)
      expect(parsed.protocol).toBe("https:")
      expect(parsed.hostname).not.toBe("gravitre.app")
    }
  })

  it("includes the four confirmed public brand profiles", () => {
    expect(GRAVITRE_SOCIAL_PROFILES.map((profile) => profile.name)).toEqual(["LinkedIn", "X", "Threads", "Instagram"])
  })
})
