import { describe, expect, it } from "vitest"
import { renderToString } from "react-dom/server"
import {
  BuildWithUsScene,
  GovernedScene,
  MarketplaceScene,
  OpenRolesScene,
  SupportScene,
  UseCasesScene,
} from "@/components/marketing/nodus/scenes/scenes"
import { StageTraceVisual, CAREERS_TRACE_STAGES } from "@/components/marketing/system/stage-trace-visual"

/**
 * Wide Nodus scenes ship a stacked phone layout (swapped by container query)
 * so tiles and text stay full size instead of shrinking with the stage.
 */
describe("marketing graphics on phones", () => {
  it.each([
    ["Governed", GovernedScene],
    ["Build with us", BuildWithUsScene],
    ["Support", SupportScene],
    ["Open roles", OpenRolesScene],
    ["Marketplace", MarketplaceScene],
  ])("%s scene renders a stacked phone layout", (_name, Scene) => {
    const html = renderToString(<Scene />)
    expect(html).toContain("@container")
    expect(html).toContain("@min-[440px]:hidden")
    expect(html).toContain("max-width:320px")
  })

  it("use cases stacks until the column is 760px wide", () => {
    const html = renderToString(<UseCasesScene />)
    expect(html).toContain("@min-[760px]:hidden")
    expect(html).toContain("max-width:320px")
  })

  it("the step trace has a vertical phone layout", () => {
    const html = renderToString(<StageTraceVisual stages={CAREERS_TRACE_STAGES} ariaLabel="Careers path" />)
    expect(html).toContain("@min-[620px]:hidden")
    expect(html).toMatch(/<ol[^>]*flex-col/)
  })
})
