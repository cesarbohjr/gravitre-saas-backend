import { NextRequest } from "next/server"
import { generateText, Output } from "ai"
import { z } from "zod"
import {
  AI_ROUTE_MODES,
  heuristicRouteIntent,
  reconcileModelRouteIntent,
  type AiRouteMode,
} from "@/lib/ai-route-intent"

// Classifies a natural-language prompt into one of the three Gravitre AI modes
// so the unified surface can auto-route to the right engine:
//   - execute → Command Center (delegate tracked work / run jobs)
//   - chat    → Workspace Chat (questions, brainstorming, explanations)
//   - find    → Universal Search (look up an existing record and get a link)
//
// This runs on the Node runtime (never edge with the AI SDK) and always
// degrades to a keyword heuristic if the model call fails, so the UI never
// stalls waiting on a classification.

export const maxDuration = 15

const CLASSIFIER_MODEL = "openai/gpt-4.1-mini"

const intentSchema = z.object({
  mode: z.enum(AI_ROUTE_MODES),
  confidence: z.number().min(0).max(1),
  reason: z.string(),
})

const ROUTER_SYSTEM_PROMPT = [
  "You are an intent router for the Gravitre AI platform.",
  "Classify the user's message into exactly one mode:",
  "- execute: the user wants Gravitre to DO something and track it — create/build/run/fix/deploy/sync/generate tasks, agents, workflows, connectors, jobs, execution plans, approvals, or delegated operator work.",
  "- chat: the user wants a conversational answer — questions, explanations, brainstorming, summaries, how-to, daily briefings, advice.",
  "- find: the user wants to locate an EXISTING record (workflow, run, agent, connector, source, document) and get a link — not create something new.",
  "",
  "Critical rules:",
  "- 'create/build/make/set up/generate ... agent/workflow/task' => execute (NOT find).",
  "- 'create ... for me' or 'build ... for us' => execute.",
  "- 'find/show/list/open/locate the ...' or 'where is my ...' => find.",
  "- 'how/why/what/explain ...' without action verbs => chat.",
  "",
  "Examples:",
  "- 'create a new agent for me' => execute",
  "- 'build a HubSpot sync workflow' => execute",
  "- 'find my marketing agent' => find",
  "- 'show me failed runs from yesterday' => find",
  "- 'how do I connect Salesforce?' => chat",
  "",
  "Set confidence between 0 and 1 and give a one-sentence reason.",
].join("\n")

export async function POST(req: NextRequest) {
  let prompt = ""
  try {
    const body = (await req.json()) as { prompt?: unknown }
    if (typeof body.prompt === "string") prompt = body.prompt.trim()
  } catch {
    // ignore malformed body — handled below
  }

  if (!prompt) {
    return Response.json({ error: "Missing prompt" }, { status: 400 })
  }

  // Trim overly long prompts before classification — the intent is almost
  // always clear from the opening sentence.
  const sample = prompt.slice(0, 600)

  try {
    const { experimental_output } = await generateText({
      model: CLASSIFIER_MODEL,
      experimental_output: Output.object({ schema: intentSchema }),
      system: ROUTER_SYSTEM_PROMPT,
      prompt: sample,
    })

    const reconciled = reconcileModelRouteIntent(prompt, {
      mode: experimental_output.mode as AiRouteMode,
      confidence: experimental_output.confidence,
      reason: experimental_output.reason,
    })

    return Response.json({
      mode: reconciled.mode,
      confidence: reconciled.confidence,
      reason: reconciled.reason,
      source: reconciled.mode === experimental_output.mode ? "model" : "model+guardrail",
    })
  } catch (error) {
    console.log("[v0] route-intent model classification failed, using heuristic:", error)
    const fallback = heuristicRouteIntent(prompt)
    return Response.json({ ...fallback, source: "heuristic" })
  }
}
