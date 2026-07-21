/**
 * Prepare assistant markdown for browser speech synthesis.
 * Strips code, links, and formatting so TTS sounds conversational.
 */

/** Remove fenced code blocks and inline code spans. */
function stripCode(text: string): string {
  return text
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/`[^`]+`/g, " ")
}

/** Replace markdown links with speakable link text or a short placeholder. */
function stripLinks(text: string): string {
  return text
    .replace(/!\[([^\]]*)\]\([^)]+\)/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, (_, label: string) => {
      const trimmed = label.trim()
      if (!trimmed || /^https?:\/\//i.test(trimmed)) return "a link"
      return trimmed
    })
    .replace(/https?:\/\/\S+/g, "a link")
}

/** Remove markdown structure characters while keeping readable words. */
function stripMarkdownStructure(text: string): string {
  return text
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/^\s*[-*+]\s+/gm, "")
    .replace(/^\s*\d+\.\s+/gm, "")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/__([^_]+)__/g, "$1")
    .replace(/_([^_]+)_/g, "$1")
    .replace(/~~([^~]+)~~/g, "$1")
    .replace(/^\s*>\s?/gm, "")
    .replace(/\|/g, " ")
}

/** Collapse whitespace and trim for natural pacing. */
function normalizeWhitespace(text: string): string {
  return text.replace(/\s+/g, " ").trim()
}

/** Split long sentences for more natural spoken delivery. */
function softenForSpeech(text: string): string {
  return text
    .replace(/\s*;\s*/g, ". ")
    .replace(/\s*:\s*/g, ". ")
    .replace(/\.{2,}/g, ".")
}

/**
 * Convert assistant markdown into plain speech-friendly text.
 * Returns empty string when nothing speakable remains.
 */
export function textForSpeech(raw: string): string {
  if (!raw.trim()) return ""

  let text = raw
  text = stripCode(text)
  text = stripLinks(text)
  text = stripMarkdownStructure(text)
  text = softenForSpeech(text)
  text = normalizeWhitespace(text)

  return text
}
