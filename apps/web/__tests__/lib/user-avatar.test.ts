import { describe, expect, it } from "vitest"
import { initialsFromDisplayName, resolveAvatarUrl } from "@/lib/user-avatar"

describe("initialsFromDisplayName", () => {
  it("uses first and last name initials", () => {
    expect(initialsFromDisplayName("Sarah Chen")).toBe("SC")
  })

  it("uses first two letters for single names", () => {
    expect(initialsFromDisplayName("Sarah")).toBe("SA")
  })

  it("falls back to email local part", () => {
    expect(initialsFromDisplayName("", "sarah@company.com")).toBe("SA")
  })
})

describe("resolveAvatarUrl", () => {
  it("returns the first non-empty candidate", () => {
    expect(resolveAvatarUrl(null, "", "https://example.com/a.png")).toBe("https://example.com/a.png")
  })
})
