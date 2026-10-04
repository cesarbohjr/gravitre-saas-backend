import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

const webRoot = resolve(__dirname, "../..")

function source(relative: string) {
  return readFileSync(resolve(webRoot, relative), "utf8")
}

describe("Gravitre 3.0 chat surface", () => {
  it("redirects the legacy /ai destination to Home and summons the assistant", () => {
    const page = source("app/ai/page.tsx")
    expect(page).toContain("AiCompatibilityRedirect")
    expect(page).toContain("summonWorkspace")
    expect(page).toContain("router.replace(APP_ROUTES.home)")
  })

  it("keeps Chat out of admin sidebar and mobile destinations", () => {
    const sidebar = source("components/gravitre/sidebar-nav-config.ts")
    expect(sidebar).not.toMatch(/name:\s*"Chat"/)
    expect(sidebar).not.toContain('icon: "chat"')

    const mobile = source("components/gravitre/mobile-bottom-nav.tsx")
    expect(mobile).not.toMatch(/name:\s*"Chat"/)
    expect(mobile).not.toContain('href: APP_ROUTES.gravitreAi')
    expect(mobile).not.toContain('"/ai"')
  })

  it("opens command-palette chat actions via summonWorkspace, not /ai navigation", () => {
    const palette = source("components/gravitre/command-palette.tsx")
    expect(palette).toContain("Start chat")
    expect(palette).toContain("summonWorkspace()")
    expect(palette).not.toMatch(/Start chat[\s\S]{0,200}router\.push\(APP_ROUTES\.gravitreAi\)/)
  })

  it("uses checkbox bulk selection plus per-item menus without a duplicate selection mode", () => {
    const sidebar = source("components/gravitre/assistant/conversation-sidebar.tsx")
    expect(sidebar).toContain('aria-label={allSelected ? "Clear selection" : "Select all conversations"}')
    expect(sidebar).toContain("aria-label=\"Conversation options\"")
    expect(sidebar).not.toContain("enterSelection")
    expect(sidebar).not.toContain("selectionMode")
    expect(sidebar).toContain("writeStoredHistorySort")
    expect(sidebar).toContain("writeStoredHistoryDateFilter")
  })

  it("deletes through optimistic cache mutation then the conversations API", () => {
    const workspace = source("app/ai/_components/ai-workspace.tsx")
    expect(workspace).toContain("optimisticRemoveConversations")
    expect(workspace).toContain("conversationsApi.delete")
    expect(workspace).toContain("conversationsApi.bulkDelete")
  })

  it("wires embedded exit controls and persists explicit window-mode changes", () => {
    const workspace = source("app/ai/_components/ai-workspace.tsx")
    expect(workspace).toContain('surface="embedded"')
    expect(workspace).toContain("openAsFloat")
    expect(workspace).toContain("choosePresentationMode")
    expect(workspace).toContain("ChatWindowControls")
  })

  it("applies Gravitre 3.0 window chrome to floating and expanded shells", () => {
    const float = source("components/gravitre/ai-floating-workspace.tsx")
    const shell = source("components/gravitre/ai-workspace-shell.tsx")
    expect(float).toContain("WINDOW_CHROME.frame")
    expect(shell).toContain("WINDOW_CHROME.frame")
    expect(shell).not.toContain("shadow-2xl")
    expect(shell).not.toContain('className="dark flex min-h-12')
  })
})
