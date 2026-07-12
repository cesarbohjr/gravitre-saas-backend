import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

function readMaxDuration(relPath: string): number {
  const src = readFileSync(resolve(__dirname, "../..", relPath), "utf8")
  const match = src.match(/export const maxDuration\s*=\s*(\w+)/)
  expect(match, `maxDuration export missing in ${relPath}`).not.toBeNull()
  const token = match![1]
  if (/^\d+$/.test(token)) return Number(token)
  // Named constant, e.g. CHAT_PROXY_MAX_DURATION_SECONDS
  const constMatch = src.match(
    new RegExp(`export const ${token}\\s*=\\s*(\\d+)`),
  )
  expect(constMatch, `${token} definition missing in ${relPath}`).not.toBeNull()
  return Number(constMatch![1])
}

describe("STA-315 chat proxy maxDuration", () => {
  it("raises chat proxy ceiling to at least 300s (confirm-via-chat residual)", () => {
    const chatCeiling = readMaxDuration("app/api/chat/route.ts")
    expect(chatCeiling).toBeGreaterThanOrEqual(300)
  })

  it("stays aligned with notifications SSE ceiling", () => {
    const chatCeiling = readMaxDuration("app/api/chat/route.ts")
    const notificationsCeiling = readMaxDuration(
      "app/api/notifications/stream/route.ts",
    )
    expect(chatCeiling).toBeGreaterThanOrEqual(notificationsCeiling)
  })
})
