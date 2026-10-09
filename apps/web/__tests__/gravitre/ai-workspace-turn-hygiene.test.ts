import { readFileSync } from "node:fs"
import { join } from "node:path"
import { describe, expect, it } from "vitest"

// Source contract for the chat turn fixes in ai-workspace.tsx. The component is
// too large to mount here, so these pin the specific lines that regressed.
const source = readFileSync(
  join(__dirname, "../../app/(app)/ai/_components/ai-workspace.tsx"),
  "utf8",
)

describe("ai-workspace turn hygiene", () => {
  it("only sends a server Stop on conversation switch when a turn is running", () => {
    expect(source).toMatch(/const switchingAwayFromLiveTurn =/)
    expect(source).toMatch(
      /if \(switchingAwayFromLiveTurn\) \{\s*stopChatTurn\(\{ conversationId: activeConversationIdRef\.current, stopStream: stop \}\)/,
    )
  })

  it("does not let null data frames wipe the approval card or execution result", () => {
    expect(source).not.toMatch(/if \("pendingTask" in payload\)/)
    expect(source).not.toMatch(/if \("executionResult" in payload\)/)
    expect(source).toMatch(/if \(payload\.pendingTask\) setPendingTask\(payload\.pendingTask\)/)
  })

  it("drops a failed prompt before resending it", () => {
    expect(source).toMatch(
      /last\?\.role === "user" && uiMessageText\(last\)\.trim\(\) === prompt\.trim\(\)/,
    )
  })

  it("gives the phone sheet the same history list as the full page", () => {
    expect(source).toMatch(/historyPanel=\{conversationSidebar\}/)
  })
})
