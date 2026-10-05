import fs from "node:fs"
import path from "node:path"

describe("Pipecat acoustic barge-in authority", () => {
  it("does not wire raw browser energy directly to bargeIn on the Pipecat mic path", () => {
    const source = fs.readFileSync(
      path.join(process.cwd(), "hooks/use-voice-duplex-session.ts"),
      "utf8",
    )
    const pipecatStart = source.indexOf("const startPipecat = useCallback")
    const legacyStart = source.indexOf("const start = useCallback", pipecatStart)
    const pipecatBlock = source.slice(pipecatStart, legacyStart)

    expect(pipecatBlock).toContain("BackchannelAwareUserTurnStartStrategy")
    expect(pipecatBlock).not.toContain("onBargeIn: () => void bargeIn()")
  })

  it("keeps explicit/manual barge-in available", () => {
    const source = fs.readFileSync(
      path.join(process.cwd(), "hooks/use-voice-duplex-session.ts"),
      "utf8",
    )
    expect(source).toContain("const bargeIn = useCallback")
    expect(source).toContain("encodePipecatInterrupt({ playbackOffsetMs })")
  })
})
