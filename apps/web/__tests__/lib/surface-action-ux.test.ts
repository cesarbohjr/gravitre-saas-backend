import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

const webRoot = resolve(__dirname, "../..")

describe("surface action UX regressions", () => {
  it("does not obscure response-style choices with a sticky save bar", () => {
    const editor = readFileSync(resolve(webRoot, "components/gravitre/agent-profile-editors.tsx"), "utf8")
    expect(editor).not.toMatch(/sticky bottom-0/)
    expect(editor).toMatch(/Unsaved changes/)
  })

  it("makes custom capability persistence state explicit", () => {
    const editor = readFileSync(resolve(webRoot, "components/gravitre/agent-profile-editors.tsx"), "utf8")
    expect(editor).toMatch(/Save capabilities/)
    expect(editor).toMatch(/disabled=\{saving \|\| !dirty\}/)
  })

  it("uses intent-based Model Studio destinations instead of workspace jargon", () => {
    const studio = readFileSync(resolve(webRoot, "components/intelligence/pages/model-studio-stage.tsx"), "utf8")
    expect(studio).toMatch(/Create or upload dataset/)
    expect(studio).toMatch(/Manage your datasets in Data/)
    expect(studio).not.toMatch(/Open training workspace/)
    expect(studio).not.toMatch(/Open full training workspace/)
  })

  it("guards and resets profile photo uploads", () => {
    const profile = readFileSync(resolve(webRoot, "app/(app)/settings/profile/page.tsx"), "utf8")
    expect(profile).toMatch(/5 \* 1024 \* 1024/)
    expect(profile).toMatch(/setIsUploadingAvatar\(true\)/)
    expect(profile).toMatch(/hasProfilePhoto/)
    expect(profile).toMatch(/Add photo/)
    expect(profile).toMatch(/Change photo/)
    expect(profile).toMatch(/Remove photo/)
    expect(profile).toMatch(/Upload photo/)
    expect(profile).toMatch(/<Dialog /)
    expect(profile).toMatch(/input\.value = ""/)
  })
})
