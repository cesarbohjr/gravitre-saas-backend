import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

import { GRAVITRE_AI_WORKSPACE_LAYOUT_ID } from "@/lib/gravitre-ai-presentation"

const webRoot = resolve(__dirname, "../..")

describe("UX Reset Phase 4 — shared workspace motion", () => {
  it("compact and expanded/fullscreen share one layout id", () => {
    expect(GRAVITRE_AI_WORKSPACE_LAYOUT_ID).toBe("gravitre-ai-workspace-frame")
    const floatSrc = readFileSync(
      resolve(webRoot, "components/gravitre/ai-floating-workspace.tsx"),
      "utf8",
    )
    const shellSrc = readFileSync(
      resolve(webRoot, "components/gravitre/ai-workspace-shell.tsx"),
      "utf8",
    )
    expect(floatSrc).toMatch(/layoutId=\{reduceMotion \? undefined : GRAVITRE_AI_WORKSPACE_LAYOUT_ID\}/)
    expect(shellSrc).toMatch(/layoutId=\{reduceMotion \? undefined : GRAVITRE_AI_WORKSPACE_LAYOUT_ID\}/)
    expect(floatSrc).toMatch(/MOTION\.major/)
    expect(shellSrc).toMatch(/MOTION\.major/)
  })
})
