/**
 * OnboardingChecklist floats bottom-right. Below `md` it must clear
 * MobileBottomNav (56px + safe area) like GravitreAIHelper, and start right of
 * the helper launcher instead of covering it.
 */
import { readFileSync } from "node:fs"
import { join } from "node:path"
import { describe, expect, it } from "vitest"

const source = readFileSync(join(process.cwd(), "components/gravitre/onboarding-checklist.tsx"), "utf8")
const floatClass = source.match(/className="(fixed z-50[^"]*)"/)?.[1] ?? ""

describe("OnboardingChecklist — mobile placement", () => {
  it("sits above MobileBottomNav with the same offset as the AI helper launcher", () => {
    expect(floatClass).toContain("max-md:bottom-[calc(56px+env(safe-area-inset-bottom)+12px)]")
  })

  it("starts right of the launcher on mobile and keeps the desktop card placement", () => {
    expect(floatClass).toContain("max-md:left-[88px]")
    expect(floatClass).toContain("md:bottom-6")
    expect(floatClass).toContain("md:right-6")
    expect(floatClass).toContain("md:w-80")
  })
})
