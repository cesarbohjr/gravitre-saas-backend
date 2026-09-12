"use client"

import * as React from "react"
import Link from "next/link"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { Check, Copy } from "lucide-react"

import { cn } from "@/lib/utils"

/**
 * The single renderer for assistant Markdown on every Gravitre conversation
 * surface. `ChatTranscript` is the only real transcript component (every surface
 * reaches it through `GravitreAIConversationTranscript`), so this file is the one
 * place assistant formatting is defined.
 *
 * Why an explicit component map rather than `@tailwindcss/typography`:
 *
 * The previous styling was a `prose prose-sm dark:prose-invert ...` class string,
 * but that plugin was never installed — it is absent from package.json and from
 * node_modules, and `.prose` appears zero times in the shipped production CSS.
 * Every one of those classes was a no-op. Tailwind Preflight, meanwhile, is very
 * much live and resets exactly what Markdown depends on:
 *
 *   ol,ul,menu { list-style: none }              -> no bullets, no numbers
 *   *,::before,::after { margin: 0; padding: 0 } -> no paragraph or list spacing
 *   h1..h6 { font-size: inherit; font-weight: inherit }  -> headings look like body
 *
 * So correctly-structured Markdown ("- option one") parsed into real <ul><li> and
 * then rendered as unmarked, unindented, unspaced lines. That is why a genuine
 * four-item list appeared as four undifferentiated blocks, with bold the only
 * surviving formatting (Preflight does not reset <strong>).
 *
 * Adopting the typography plugin would have imported a third-party type scale and
 * palette that competes with the Gravitre/Nodus tokens. Mapping the elements
 * ourselves keeps one design system, adds no dependency, and lets the spacing and
 * sizes below be stated exactly.
 */

/** Vertical rhythm. Block-level children own their bottom margin; `last:mb-0`
 *  keeps the bubble from ending in dead space. */
const BLOCK = "mb-3 last:mb-0"

/**
 * Conservative whitespace repair. Deliberately NOT a list-inference pass: turning
 * arbitrary newline-separated text into bullets would invent structure the model
 * never asked for and would misread ordinary prose. All this does is collapse
 * runs of blank lines, which models emit freely and which otherwise open large
 * holes between paragraphs.
 */
export function normalizeAssistantMarkdown(input: string): string {
  return input
    .replace(/\r\n?/g, "\n")
    .replace(/[ \t]+$/gm, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim()
}

function CodeBlock({
  children,
  language,
}: {
  children: React.ReactNode
  language: string | null
}) {
  const [copied, setCopied] = React.useState(false)
  const preRef = React.useRef<HTMLPreElement>(null)

  const copy = React.useCallback(() => {
    const text = preRef.current?.textContent ?? ""
    if (!text) return
    void navigator.clipboard?.writeText(text).then(
      () => {
        setCopied(true)
        window.setTimeout(() => setCopied(false), 1500)
      },
      () => {
        /* Clipboard denied (permissions/insecure origin). The code is still
           selectable, so failing quietly beats an error the user cannot act on. */
      },
    )
  }, [])

  return (
    <div className={cn(BLOCK, "overflow-hidden rounded-[var(--np-radius-md)] border border-divide")}>
      <div className="flex items-center justify-between gap-2 border-b border-divide bg-[color:var(--g-surface-2)] px-2.5 py-1">
        {/* Labelled for screen readers as well as sighted readers: a bare "ts"
            is meaningless out of context. */}
        <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-muted-foreground">
          {language || "code"}
        </span>
        <button
          type="button"
          onClick={copy}
          aria-label={copied ? "Code copied" : "Copy code"}
          className="flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#16a374]/40"
        >
          {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre
        ref={preRef}
        // tabIndex makes a horizontally scrolling region reachable by keyboard.
        tabIndex={0}
        className="overflow-x-auto px-3 py-2 font-mono text-[12.5px] leading-[1.5]"
      >
        {children}
      </pre>
    </div>
  )
}

type Props = { children?: React.ReactNode; className?: string }

/**
 * Exported for tests so the mapping can be asserted without mounting a whole
 * transcript.
 */
export const assistantMarkdownComponents = {
  p: ({ children }: Props) => <p className={cn(BLOCK, "leading-[1.6]")}>{children}</p>,

  // pl-5 leaves room for the marker; marker colour keeps bullets from competing
  // with the text. space-y-1 is the list-item rhythm.
  ul: ({ children }: Props) => (
    <ul className={cn(BLOCK, "list-disc space-y-1 pl-5 marker:text-muted-foreground")}>
      {children}
    </ul>
  ),
  ol: ({ children }: Props) => (
    <ol className={cn(BLOCK, "list-decimal space-y-1 pl-5 marker:text-muted-foreground")}>
      {children}
    </ol>
  ),
  li: ({ children }: Props) => (
    // A "loose" list (blank lines between items) wraps each item's content in a
    // <p>. Without mb-0 that paragraph reintroduces the gap that made list items
    // read as separate paragraphs, so the nesting is corrected here rather than
    // by rewriting the model's Markdown.
    <li className="leading-[1.6] [&>ol]:mt-1 [&>p]:mb-0 [&>ul]:mt-1">{children}</li>
  ),

  // Restrained hierarchy: assistant prose, not marketing copy. first:mt-0 stops a
  // leading heading from pushing itself off the top of the bubble.
  h1: ({ children }: Props) => (
    <h1 className="mt-5 mb-2 text-[21px] font-semibold leading-snug first:mt-0">{children}</h1>
  ),
  h2: ({ children }: Props) => (
    <h2 className="mt-5 mb-2 text-[19px] font-semibold leading-snug first:mt-0">{children}</h2>
  ),
  h3: ({ children }: Props) => (
    <h3 className="mt-4 mb-1.5 text-[17px] font-semibold leading-snug first:mt-0">{children}</h3>
  ),
  h4: ({ children }: Props) => (
    <h4 className="mt-3 mb-1 text-[15px] font-semibold first:mt-0">{children}</h4>
  ),
  h5: ({ children }: Props) => (
    <h5 className="mt-3 mb-1 text-[15px] font-semibold first:mt-0">{children}</h5>
  ),
  h6: ({ children }: Props) => (
    <h6 className="mt-3 mb-1 text-[15px] font-semibold first:mt-0">{children}</h6>
  ),

  strong: ({ children }: Props) => <strong className="font-semibold">{children}</strong>,
  em: ({ children }: Props) => <em className="italic">{children}</em>,
  hr: () => <hr className={cn(BLOCK, "border-t border-divide")} />,

  blockquote: ({ children }: Props) => (
    <blockquote
      className={cn(BLOCK, "border-l-2 border-divide pl-3 text-muted-foreground [&>p]:mb-0")}
    >
      {children}
    </blockquote>
  ),

  // Inline code stays inline-sized. A larger pill would break the line rhythm and
  // read as a badge rather than as code.
  code: ({ children, className }: Props) => (
    <code
      className={cn(
        "rounded bg-[color:var(--g-surface-2)] px-1 py-px font-mono text-[0.9em]",
        className,
      )}
    >
      {children}
    </code>
  ),

  // react-markdown nests <code> inside <pre>. The language lives on that child's
  // `language-*` class, so it is read here and the child's own wrapper dropped —
  // otherwise the inline <code> styling above would apply inside the block.
  pre: ({ children }: Props) => {
    const child = React.isValidElement(children)
      ? (children as React.ReactElement<{ className?: string; children?: React.ReactNode }>)
      : null
    const cls = child?.props?.className ?? ""
    const language = /language-([\w-]+)/.exec(cls)?.[1] ?? null
    return <CodeBlock language={language}>{child?.props?.children ?? children}</CodeBlock>
  },

  // Wrapped so a wide table scrolls inside the bubble instead of stretching it.
  table: ({ children }: Props) => (
    <div className={cn(BLOCK, "overflow-x-auto rounded-[var(--np-radius-md)] border border-divide")}>
      <table className="w-full border-collapse text-[13px]">{children}</table>
    </div>
  ),
  thead: ({ children }: Props) => (
    <thead className="bg-[color:var(--g-surface-2)]">{children}</thead>
  ),
  th: ({ children }: Props) => (
    <th className="border-b border-divide px-2.5 py-1.5 text-left font-semibold">{children}</th>
  ),
  td: ({ children }: Props) => (
    <td className="border-b border-divide px-2.5 py-1.5 align-top last:border-0">{children}</td>
  ),

  a: ({ href, children, ...props }: Props & { href?: string }) => {
    const raw = (href || "").trim()
    // Legacy CTAs used ?conversation=; AI page hydrates via ?c=.
    const normalized = raw.startsWith("/ai?conversation=")
      ? raw.replace("/ai?conversation=", "/ai?c=")
      : raw
    if (normalized.startsWith("/")) {
      return (
        <Link href={normalized} className="text-[color:var(--g-brand)] underline underline-offset-2">
          {children}
        </Link>
      )
    }
    if (normalized.startsWith("http://") || normalized.startsWith("https://")) {
      return (
        <a
          href={normalized}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[color:var(--g-brand)] underline underline-offset-2"
          {...props}
        >
          {children}
        </a>
      )
    }
    // Anything else — javascript:, data:, mailto-with-payload, a malformed scheme
    // — is rendered as inert text. Model output is untrusted, so an unrecognised
    // scheme must never become a clickable target.
    return <span>{children}</span>
  },
}

/**
 * Memoized on the text so completed messages stop re-rendering while a later
 * message streams. Without this, every token re-parsed every message in the
 * thread.
 */
export const AssistantMarkdown = React.memo(function AssistantMarkdown({
  children,
  className,
}: {
  children: string
  className?: string
}) {
  const source = React.useMemo(() => normalizeAssistantMarkdown(children), [children])
  return (
    <div className={cn("text-[15px] leading-[1.6] break-words", className)}>
      {/* No rehype-raw: raw HTML in model output stays inert text rather than
          being parsed, so there is no injection surface to sanitize. Do not add
          rehype-raw here without a sanitizer. */}
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={assistantMarkdownComponents}>
        {source}
      </ReactMarkdown>
    </div>
  )
})
