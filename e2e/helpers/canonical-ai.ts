import type { Page, Route } from "@playwright/test"

export type CanonicalAiDebug = {
  liveInstanceCount: number
  liveOwnerIds: string[]
  liveInstanceIds: string[]
  currentInstanceId: string | null
  mountCount: number
  unmountCount: number
  chatSubmitCount: number
  conversationId: string | null
  streamStatus: string | null
  presentation: string | null
  canonicalPresentation: string | null
  pathname: string | null
  agentScopeId: string | null
  agentScopeName: string | null
  selected: { kind: string; id: string; label: string } | null
  lastChatRequestSummary: Record<string, unknown> | null
}

export function uiMessageStream(text: string, delayMs = 0): string {
  const chunks = [
    `data: ${JSON.stringify({ type: "start" })}\n\n`,
    `data: ${JSON.stringify({ type: "text-start", id: "0" })}\n\n`,
    `data: ${JSON.stringify({ type: "text-delta", id: "0", delta: text })}\n\n`,
    `data: ${JSON.stringify({ type: "text-end", id: "0" })}\n\n`,
    `data: ${JSON.stringify({ type: "finish" })}\n\n`,
    "data: [DONE]\n\n",
  ]
  void delayMs
  return chunks.join("")
}

export async function mockCanonicalChat(page: Page, options?: { slowMs?: number; body?: string }) {
  const posts: unknown[] = []
  await page.route("**/api/chat", async (route: Route) => {
    posts.push(route.request().postDataJSON())
    const body = uiMessageStream(options?.body ?? "Northwind pipeline looks healthy.")
    if (options?.slowMs) {
      await new Promise((resolve) => setTimeout(resolve, options.slowMs))
    }
    await route.fulfill({
      status: 200,
      headers: {
        "content-type": "text/event-stream",
        "x-vercel-ai-ui-message-stream": "v1",
        "cache-control": "no-cache",
      },
      body,
    })
  })
  return posts
}

export async function readAiDebug(page: Page): Promise<CanonicalAiDebug | null> {
  return page.evaluate(() => {
    const w = window as Window & { __GRAVITRE_AI_DEBUG?: CanonicalAiDebug }
    return w.__GRAVITRE_AI_DEBUG ?? null
  })
}

export async function waitForTestApi(page: Page, timeout = 60_000) {
  // Playwright signature is (fn, arg, options). Passing `{ timeout }` as the
  // second argument used to wait until the *test* budget expired.
  await page.waitForFunction(
    () =>
      Boolean(
        (window as Window & { __GRAVITRE_AI_TEST?: { restoreFromHelper: () => void } }).__GRAVITRE_AI_TEST,
      ),
    undefined,
    { timeout },
  )
}

export async function waitForRuntime(page: Page, timeout = 90_000) {
  await page.waitForFunction(
    () => {
      const w = window as Window & { __GRAVITRE_AI_DEBUG?: { liveInstanceCount?: number } }
      return (w.__GRAVITRE_AI_DEBUG?.liveInstanceCount ?? 0) >= 1
    },
    undefined,
    { timeout },
  )
}

export async function openHelper(page: Page) {
  await waitForTestApi(page)
  const helper = page.locator("[data-gravitre-ai-helper]")
  if (await helper.isVisible()) {
    await helper.click({ force: true })
    return
  }
  await page.evaluate(() => {
    const api = (window as Window & { __GRAVITRE_AI_TEST?: { restoreFromHelper: () => void } }).__GRAVITRE_AI_TEST
    api?.restoreFromHelper()
  })
}
