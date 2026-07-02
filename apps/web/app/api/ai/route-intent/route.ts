import { NextRequest } from "next/server"
import { generateText, Output } from "ai"
import { z } from "zod"

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

const MODES = ["execute", "chat", "find"] as const
type Mode = (typeof MODES)[number]

const CLASSIFIER_MODEL = "openai/gpt-4.1-mini"

const intentSchema = z.object({
  mode: z.enum(MODES),
  confidence: z.number().min(0).max(1),
  reason: z.string(),
})

/** Fast, dependency-free fallback used when the model call is unavailable. */
function heuristicRoute(prompt: string): { mode: Mode; confidence: number; reason: string } {
  const text = prompt.toLowerCase().trim()

  const findSignals = [
    /^(find|show|list|where|which|open|get)\b/,
    /\b(search for|look up|link to|pull up)\b/,
    /\b(runs?|workflows?|agents?|connectors?|sources?|docs?|documents?)\b.*\b(named|called|with|for)\b/,
  ]
  const executeSignals = [
    /^(run|create|build|fix|deploy|sync|generate|schedule|kick off|start|execute|delegate|investigate|resolve|retry)\b/,
    /\b(task|job|execution plan|approval|async)\b/,
  ]

  if (findSignals.some((re) => re.test(text))) {
    return { mode: "find", confidence: 0.55, reason: "Looks like a lookup for an existing record." }
  }
  if (executeSignals.some((re) => re.test(text))) {
    return { mode: "execute", confidence: 0.55, reason: "Looks like a request to perform tracked work." }
  }
  return { mode: "chat", confidence: 0.4, reason: "Defaulting to a conversational answer." }
}

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
      system: [
        "You are an intent router for the Gravitre AI platform.",
        "Classify the user's message into exactly one mode:",
        "- execute: the user wants Gravitre to DO something and track it — create tasks, run jobs, fix/deploy/sync, generate execution plans, handle approvals.",
        "- chat: the user wants a conversational answer — questions, explanations, brainstorming, summaries, how-to, daily briefings.",
        "- find: the user wants to locate an EXISTING record (a workflow, run, agent, connector, source, or document) and get a link to it.",
        "Prefer 'chat' when the message is a question that expects an explanation rather than an action or a lookup.",
        "Set confidence between 0 and 1 and give a one-sentence reason.",
      ].join("\n"),
      prompt: sample,
    })

    const result = experimental_output
    return Response.json({
      mode: result.mode,
      confidence: result.confidence,
      reason: result.reason,
      source: "model",
    })
  } catch (error) {
    console.log("[v0] route-intent model classification failed, using heuristic:", error)
    const fallback = heuristicRoute(prompt)
    return Response.json({ ...fallback, source: "heuristic" })
  }
}
