"use client"

import AgentChatPage from "@/app/agents/[id]/chat/page"

/** Playwright harness: real agent-chat orchestrator with a fixture agent id. */
export default function AgentChatProofPage() {
  return <AgentChatPage params={Promise.resolve({ id: "agt_lead_triage" })} />
}
