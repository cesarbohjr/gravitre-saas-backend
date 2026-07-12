/**
 * STA-308: conversation sidebar titles are set only at create time.
 * When the user starts a sufficiently different task in the same thread,
 * refresh the stored title so the sidebar matches the active ask.
 */

const TITLE_MAX_LEN = 80

const STOPWORDS = new Set([
  "the",
  "a",
  "an",
  "in",
  "on",
  "to",
  "for",
  "of",
  "and",
  "or",
  "with",
  "from",
  "also",
  "then",
  "please",
  "can",
  "you",
  "could",
  "would",
  "should",
  "my",
  "me",
  "our",
  "us",
  "this",
  "that",
  "just",
  "now",
  "into",
  "via",
  "using",
])

/** Affirmations / confirm-via-chat — never retitle from these. */
const AFFIRMATION_RE =
  /^(yes|y|yeah|yep|yup|ok|okay|sure|confirm|confirmed|proceed|go\s*ahead|do\s*it|approve|approved|lgtm|ship\s*it|continue|sounds?\s+good)[.!?]*$/i

/** Soft follow-ups that refine the same task rather than start a new one. */
const CONTINUATION_RE =
  /^(also\b|and then\b|wait\b|actually\b|instead\b|never\s*mind\b|change that\b|same but\b|make it\b|update that\b|tweak\b)/i

const MIN_CONTENT_TOKENS = 3
const JACCARD_REFRESH_BELOW = 0.35

export function deriveConversationTitle(prompt: string): string {
  const trimmed = prompt.trim().replace(/\s+/g, " ")
  if (!trimmed) return "Chat"
  return trimmed.length <= TITLE_MAX_LEN ? trimmed : `${trimmed.slice(0, TITLE_MAX_LEN - 1)}…`
}

export function tokenizeConversationTitle(text: string): Set<string> {
  const tokens = text
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .split(/\s+/)
    .filter((t) => t.length > 2 && !STOPWORDS.has(t))
  return new Set(tokens)
}

export function jaccardSimilarity(a: Set<string>, b: Set<string>): number {
  if (a.size === 0 && b.size === 0) return 1
  if (a.size === 0 || b.size === 0) return 0
  let intersection = 0
  for (const token of a) {
    if (b.has(token)) intersection += 1
  }
  const union = a.size + b.size - intersection
  return union === 0 ? 0 : intersection / union
}

/**
 * Returns true when an existing thread's title should be replaced by the
 * derived title of `nextPrompt` (new episode / divergent task).
 */
export function shouldRefreshConversationTitle(
  currentTitle: string,
  nextPrompt: string,
): boolean {
  const prompt = nextPrompt.trim()
  if (!prompt) return false
  if (AFFIRMATION_RE.test(prompt)) return false
  if (CONTINUATION_RE.test(prompt)) return false

  const nextTitle = deriveConversationTitle(prompt)
  const current = (currentTitle || "").trim()
  if (!current || current === "Chat") return true
  if (current.toLowerCase() === nextTitle.toLowerCase()) return false

  const currentTokens = tokenizeConversationTitle(current)
  const nextTokens = tokenizeConversationTitle(nextTitle)
  // Follow-ups that are too thin to be a new task leave the original title.
  if (nextTokens.size < MIN_CONTENT_TOKENS) return false
  // Brand-new threads sometimes store a placeholder; always take a real ask.
  if (currentTokens.size < 2) return true

  return jaccardSimilarity(currentTokens, nextTokens) < JACCARD_REFRESH_BELOW
}
