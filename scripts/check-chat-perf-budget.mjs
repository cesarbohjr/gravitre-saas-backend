#!/usr/bin/env node
/**
 * CI guard: fail when /ai conversation-list or page-load perf marks exceed budget.
 * Playwright ai-page-load.spec.ts enforces browser-level timing; this script is
 * for optional local mark dumps via window.__gravitreChatPerf export (dev).
 */
const budgets = {
  conversation_list: Number(process.env.CHAT_PERF_BUDGET_CONVERSATION_LIST_MS ?? 8000),
  page_load: Number(process.env.CHAT_PERF_BUDGET_PAGE_LOAD_MS ?? 12000),
}

const marks = globalThis.__gravitreChatPerfMarks
if (!Array.isArray(marks)) {
  console.log("SKIP — no perf marks supplied (__gravitreChatPerfMarks)")
  process.exit(0)
}

let failed = false
for (const [stage, budget] of Object.entries(budgets)) {
  const row = marks.filter((m) => m.stage === stage).pop()
  if (!row) continue
  if (row.ms > budget) {
    console.error(`FAIL chat-perf ${stage}: ${row.ms}ms > ${budget}ms budget`)
    failed = true
  } else {
    console.log(`PASS chat-perf ${stage}: ${row.ms}ms <= ${budget}ms`)
  }
}
process.exit(failed ? 1 : 0)
