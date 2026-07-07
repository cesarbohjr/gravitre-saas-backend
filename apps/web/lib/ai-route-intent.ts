export const AI_ROUTE_MODES = ["execute", "chat", "find"] as const

export type AiRouteMode = (typeof AI_ROUTE_MODES)[number]

export type AiRouteDecision = {
  mode: AiRouteMode
  confidence: number
  reason: string
}

const EXECUTE_VERBS =
  /\b(run|create|build|make|fix|deploy|sync|generate|schedule|kick off|start|execute|delegate|investigate|resolve|retry|set up|spin up|provision|add|update|delete|remove|enable|disable|approve|reject|send|publish|launch|draft|write|prepare|configure|install|trigger|queue|assign)\b/

const EXECUTE_OBJECTS =
  /\b(agent|workflow|connector|integration|task|job|run|campaign|report|plan|automation|sequence|approval|operator|playbook|pipeline)\b/

const FIND_LOOKUP =
  /\b(find|show me|show the|list|where is|where's|where are|which|open the|locate|pull up|look up|search for|get the|link to)\b/

const FIND_ENTITY_LOOKUP =
  /^(find|show|list|where|which|open|locate|get)\b.*\b(runs?|workflows?|agents?|connectors?|sources?|documents?)\b/

const CHAT_QUESTION =
  /^(what|why|how|when|who|can you explain|tell me about|summarize|describe|help me understand|is there|are there|should i|would you recommend)\b/

const OPERATIONAL_EXECUTE =
  /\b(fix|debug|investigate|resolve|retry|re-run|rerun|failed|failure|error|alert|incident|outage|sync failed|timed out)\b/

const CONVERSATIONAL_CREATE =
  /\b(create|build|make|set up|spin up|provision|add|generate|draft)\b.*\b(agent|workflow|automation|playbook|operator)\b/

/** Creation requests that should use Manus-like chat dialogue, not the execute dashboard. */
export function isConversationalOperatorPrompt(prompt: string): boolean {
  const text = prompt.toLowerCase().trim()
  if (!CONVERSATIONAL_CREATE.test(text)) return false
  if (OPERATIONAL_EXECUTE.test(text)) return false
  return true
}

function scoreConversationalOperator(text: string): number {
  return isConversationalOperatorPrompt(text) ? 7 : 0
}

function scoreExecute(text: string): number {
  let score = 0
  if (/^(run|create|build|make|fix|deploy|sync|generate|schedule|execute|delegate|set up|spin up|provision|add)\b/.test(text)) {
    score += 3
  }
  if (EXECUTE_VERBS.test(text) && EXECUTE_OBJECTS.test(text)) {
    score += 4
  }
  if (/\b(create|build|make|set up|spin up|provision|add|generate|draft|write)\b.*\b(for me|for us|on my behalf)\b/.test(text)) {
    score += 3
  }
  if (/\b(for me|for us|on my behalf)\b.*\b(create|build|make|set up|generate|run|fix)\b/.test(text)) {
    score += 3
  }
  if (/\b(task|job|execution plan|approval|async|operator session)\b/.test(text)) {
    score += 2
  }
  if (/\b(fix|resolve|retry|re-run|rerun)\b.*\b(run|workflow|connector|issue|error|failure|alert|sync)\b/.test(text)) {
    score += 3
  }
  if (OPERATIONAL_EXECUTE.test(text)) {
    score += 4
  }
  return score
}

function scoreFind(text: string): number {
  let score = 0
  if (/^(find|show|list|where|which|open|locate|get)\b/.test(text)) {
    score += 2
  }
  if (FIND_LOOKUP.test(text)) {
    score += 3
  }
  if (FIND_ENTITY_LOOKUP.test(text)) {
    score += 3
  }
  if (/\b(named|called)\b/.test(text) && EXECUTE_OBJECTS.test(text)) {
    score += 2
  }
  // Penalize creation/delegation phrasing — not a lookup.
  if (/\b(create|build|make|set up|provision|generate|draft|write|run|fix|deploy|schedule)\b/.test(text)) {
    score -= 4
  }
  return Math.max(0, score)
}

function scoreChat(text: string): number {
  let score = 0
  if (CHAT_QUESTION.test(text)) {
    score += 3
  }
  if (/\?\s*$/.test(text)) {
    score += 2
  }
  if (/\b(explain|brainstorm|compare|pros and cons|best practice|overview|walk me through)\b/.test(text)) {
    score += 2
  }
  // Action phrasing should not default to chat.
  if (scoreExecute(text) >= 3) {
    score -= 2
  }
  return Math.max(0, score)
}

/* Fast, dependency-free routing used when the model call is unavailable. */

const CONNECTOR_INTEGRATIONS =
  /\b(hubspot|salesforce|slack|zendesk|github|stripe|jira|quickbooks|pipedrive|intercom|notion|asana|teams|gmail|google|microsoft|monday|clickup|figma|canva|pagerduty|linkedin|netsuite|workday|marketo|odoo|confluence|crm)\b/

const CONNECTOR_ACTION_VERBS =
  /\b(search|find|list|get|lookup|query|show|fetch|create|update|post|send|write|close|log|notify|message|assign|enroll|add|sync|pull|push|run|execute|trigger)\b/

/** Connector read/write and connector inventory questions must use governed chat execution. */
export function isConnectorChatPrompt(prompt: string): boolean {
  const text = prompt.toLowerCase().trim()
  if (!text) return false
  if (/\b(connector|integration)s?\b/.test(text) && /\b(what|which|any|connected|available|do we have|have we)\b/.test(text)) {
    return true
  }
  if (!CONNECTOR_INTEGRATIONS.test(text)) return false
  return CONNECTOR_ACTION_VERBS.test(text)
}

function scoreConnectorChat(text: string): number {
  return isConnectorChatPrompt(text) ? 8 : 0
}

/** Fast, dependency-free routing used when the model call is unavailable. */
export function heuristicRouteIntent(prompt: string): AiRouteDecision {
  const text = prompt.toLowerCase().trim()
  const conversationalScore = scoreConversationalOperator(text)
  const connectorScore = scoreConnectorChat(text)
  const executeScore = scoreExecute(text)
  const findScore = scoreFind(text)
  const chatScore = scoreChat(text)

  if (conversationalScore >= 6) {
    return {
      mode: "chat",
      confidence: 0.88,
      reason: "Conversational operator flow — confirm details, then create via dialogue.",
    }
  }

  if (connectorScore >= 8) {
    return {
      mode: "chat",
      confidence: 0.9,
      reason: "Connector read/write or integration inventory — use governed chat execution.",
    }
  }

  const ranked = [
    { mode: "execute" as const, score: executeScore, reason: "Looks like a request to perform tracked work." },
    { mode: "find" as const, score: findScore, reason: "Looks like a lookup for an existing record." },
    { mode: "chat" as const, score: chatScore, reason: "Looks like a conversational question or explanation." },
  ].sort((a, b) => b.score - a.score)

  const winner = ranked[0]
  const runnerUp = ranked[1]
  const margin = winner.score - runnerUp.score
  const confidence = winner.score === 0 ? 0.4 : Math.min(0.92, 0.52 + winner.score * 0.08 + margin * 0.05)

  if (winner.score === 0) {
    return { mode: "chat", confidence: 0.4, reason: "Defaulting to a conversational answer." }
  }

  return { mode: winner.mode, confidence, reason: winner.reason }
}

/** Guardrail: model sometimes confuses create/delegate prompts with search lookups. */
export function reconcileModelRouteIntent(
  prompt: string,
  model: AiRouteDecision,
): AiRouteDecision {
  const text = prompt.toLowerCase().trim()
  const conversationalScore = scoreConversationalOperator(text)
  const executeScore = scoreExecute(text)
  const findScore = scoreFind(text)

  if (conversationalScore >= 6) {
    return {
      mode: "chat",
      confidence: Math.max(model.confidence, 0.85),
      reason: "Agent/workflow creation uses conversational operator mode, not the analysis dashboard.",
    }
  }

  if (isConnectorChatPrompt(text)) {
    return {
      mode: "chat",
      confidence: Math.max(model.confidence, 0.88),
      reason: "Connector execution or inventory — routing to governed chat.",
    }
  }

  if (model.mode === "find" && executeScore >= 4 && executeScore > findScore + 1) {
    return {
      mode: "execute",
      confidence: Math.max(model.confidence, 0.78),
      reason: "Creation or delegation request — routing to Execute instead of Search.",
    }
  }

  if (model.mode === "chat" && executeScore >= 5 && executeScore > scoreChat(text) + 2) {
    if (conversationalScore >= 4) {
      return {
        mode: "chat",
        confidence: Math.max(model.confidence, 0.8),
        reason: "Creation request stays in conversational operator mode.",
      }
    }
    return {
      mode: "execute",
      confidence: Math.max(model.confidence, 0.75),
      reason: "Action-oriented request — routing to Execute.",
    }
  }

  if (model.mode === "execute" && findScore >= 5 && findScore > executeScore + 2 && FIND_LOOKUP.test(text)) {
    return {
      mode: "find",
      confidence: Math.max(model.confidence, 0.72),
      reason: "Explicit lookup phrasing — routing to Universal Search.",
    }
  }

  return model
}
