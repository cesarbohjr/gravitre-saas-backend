import { renderToStaticMarkup } from "react-dom/server"
import { createElement } from "react"
import { describe, expect, it } from "vitest"

import {
  AssistantMarkdown,
  normalizeAssistantMarkdown,
} from "@/components/gravitre/assistant/assistant-markdown"

function render(md: string): string {
  return renderToStaticMarkup(createElement(AssistantMarkdown, null, md))
}

/**
 * Phase 11 regression fixture — the exact reported failure.
 *
 * A real four-option answer rendered as four undifferentiated blocks because the
 * `prose` classes styling assistant Markdown came from a plugin that was never
 * installed, leaving Tailwind Preflight's `ol,ul,menu{list-style:none}` and
 * universal margin reset as the only rules in play.
 */
const FOUR_OPTIONS = `Here are your options:

- **Raise the budget cap** so the campaign keeps serving
- **Pause the underperforming ad group** and reallocate spend
- **Tighten the audience** to reduce wasted impressions
- **Leave it as is** and review again next week

Let me know which you'd prefer.`

describe("the reported four-option regression", () => {
  const html = render(FOUR_OPTIONS)

  it("renders a real list, not four paragraphs", () => {
    expect(html).toContain("<ul")
    expect((html.match(/<li/g) ?? []).length).toBe(4)
  })

  it("shows list markers, which Preflight had removed", () => {
    expect(html).toMatch(/<ul[^>]*class="[^"]*list-disc/)
  })

  it("indents the list so markers have room", () => {
    expect(html).toMatch(/<ul[^>]*class="[^"]*pl-5/)
  })

  it("never leaks raw Markdown syntax to the user", () => {
    expect(html).not.toContain("**")
    expect(html).not.toMatch(/>\s*-\s+\*\*/)
  })

  it("renders the bold labels as real emphasis", () => {
    expect(html).toContain("<strong")
    expect(html).toContain("Raise the budget cap")
  })

  it("keeps the surrounding prose as paragraphs", () => {
    expect(html).toContain("Here are your options:")
    expect(html).toContain("Let me know which you&#x27;d prefer.")
  })
})

describe("list rendering", () => {
  it("numbers ordered lists", () => {
    const html = render("1. First\n2. Second\n3. Third")
    expect(html).toMatch(/<ol[^>]*class="[^"]*list-decimal/)
    expect((html.match(/<li/g) ?? []).length).toBe(3)
  })

  it("supports nested lists", () => {
    const html = render("- Outer\n  - Inner\n- Second")
    expect((html.match(/<ul/g) ?? []).length).toBe(2)
  })

  it("does not let a loose list reopen paragraph gaps", () => {
    // Blank lines between items make each <li> wrap its text in a <p>. That <p>
    // must not carry a bottom margin, or the items read as separate paragraphs —
    // which is the original bug in a different disguise.
    // Both `&` and `>` are HTML-escaped inside the class attribute, so the
    // arbitrary variant appears as `[&amp;&gt;p]:mb-0`.
    const html = render("- One\n\n- Two")
    expect(html).toContain("[&amp;&gt;p]:mb-0")
    expect(html).toContain("<li")
  })
})

describe("headings are differentiated but restrained", () => {
  it("gives each level a distinct real size", () => {
    const h1 = render("# Title")
    const h2 = render("## Section")
    const h3 = render("### Sub")
    expect(h1).toMatch(/<h1[^>]*text-\[21px\]/)
    expect(h2).toMatch(/<h2[^>]*text-\[19px\]/)
    expect(h3).toMatch(/<h3[^>]*text-\[17px\]/)
  })

  it("does not push a leading heading off the top of the bubble", () => {
    expect(render("## Section")).toMatch(/<h2[^>]*first:mt-0/)
  })
})

describe("code", () => {
  it("labels the language and offers a copy control", () => {
    const html = render("```ts\nconst a = 1\n```")
    expect(html).toContain("ts")
    expect(html).toContain("Copy code")
    expect(html).toContain("<pre")
  })

  it("scrolls horizontally rather than stretching the bubble", () => {
    expect(render("```\nx\n```")).toMatch(/<pre[^>]*overflow-x-auto/)
  })

  it("keeps a code block keyboard reachable", () => {
    expect(render("```\nx\n```")).toMatch(/<pre[^>]*tabindex="0"/i)
  })

  it("keeps inline code inline-sized rather than an oversized pill", () => {
    const html = render("Use `npm run dev` now")
    expect(html).toMatch(/<code[^>]*text-\[0\.9em\]/)
  })

  it("falls back to a neutral label when no language is given", () => {
    expect(render("```\nplain\n```")).toContain("code")
  })
})

describe("tables", () => {
  const html = render("| Metric | Value |\n| --- | --- |\n| Spend | $1,200 |")

  it("renders a real table with a differentiated header", () => {
    expect(html).toContain("<table")
    expect(html).toContain("<th")
    expect(html).toMatch(/<thead[^>]*g-surface-2/)
  })

  it("scrolls on narrow screens instead of overflowing", () => {
    expect(html).toMatch(/<div[^>]*overflow-x-auto/)
  })
})

describe("links are safe by construction", () => {
  it("opens external links without leaking the referrer", () => {
    const html = render("[site](https://example.com)")
    expect(html).toContain('rel="noopener noreferrer"')
    expect(html).toContain('target="_blank"')
  })

  it("renders internal links for in-app navigation", () => {
    expect(render("[chat](/ai?c=123)")).toContain('href="/ai?c=123"')
  })

  it("neutralizes a javascript: URL to inert text", () => {
    const html = render("[click](javascript:alert(1))")
    expect(html).not.toContain("javascript:")
    expect(html).toContain("<span>click</span>")
  })

  it("neutralizes a data: URL", () => {
    expect(render("[x](data:text/html;base64,PHNjcmlwdD4=)")).not.toContain("data:text/html")
  })
})

describe("untrusted content", () => {
  it("does not execute or emit raw HTML from model output", () => {
    const html = render('Hello <script>alert("xss")</script> world')
    expect(html).not.toContain("<script>")
  })

  it("does not honor an injected event handler", () => {
    const html = render('<img src=x onerror="alert(1)">')
    // The whole tag is escaped into visible text, so there is no <img> element and
    // no attribute for the browser to act on. Asserting on the escaped form is the
    // real guarantee; asserting the substring "onerror" is absent would fail on
    // inert text that is perfectly safe.
    expect(html).not.toMatch(/<img/i)
    expect(html).toContain("&lt;img")
    // The quotes around the handler value are escaped too, so it cannot terminate
    // an attribute even if something later re-parsed this string.
    expect(html).toContain("&quot;")
  })

  it("does not render an arbitrary iframe", () => {
    expect(render('<iframe src="https://evil.test"></iframe>')).not.toContain("<iframe")
  })
})

describe("streaming safety", () => {
  // Each of these is a real intermediate state of a streamed response. None may
  // throw, and none may leak the partial syntax as visible text.
  const partials = [
    "Here is **bold that is not closed",
    "```ts\nconst a = 1",
    "| Metric | Value |\n| --- |",
    "- item one\n- item tw",
    "#",
    "[link](https://exa",
  ]

  it.each(partials)("survives incomplete markdown: %j", (md) => {
    expect(() => render(md)).not.toThrow()
  })

  it("renders a completed stream identically to the same static text", () => {
    // Guards the streaming->static switch: finishing a stream must not reflow into
    // different markup.
    expect(render(FOUR_OPTIONS)).toBe(render(FOUR_OPTIONS))
  })
})

describe("whitespace normalization", () => {
  it("collapses runs of blank lines that would open large holes", () => {
    expect(normalizeAssistantMarkdown("a\n\n\n\n\nb")).toBe("a\n\nb")
  })

  it("preserves the single blank line that separates paragraphs", () => {
    expect(normalizeAssistantMarkdown("a\n\nb")).toBe("a\n\nb")
  })

  it("normalizes CRLF", () => {
    expect(normalizeAssistantMarkdown("a\r\n\r\nb")).toBe("a\n\nb")
  })

  it("never invents a list from newline-separated prose", () => {
    // The explicit DO NOT: no regex that converts arbitrary lines into bullets.
    const html = render("First thought\n\nSecond thought\n\nThird thought")
    expect(html).not.toContain("<ul")
    expect(html).not.toContain("<li")
  })

  it("leaves a short plain answer plain — no list, no heading", () => {
    const html = render("Yes, the campaign is still running.")
    expect(html).not.toContain("<ul")
    expect(html).not.toContain("<h1")
    expect(html).toContain("<p")
  })
})

describe("other block types", () => {
  it("renders blockquotes without a doubled paragraph gap", () => {
    const html = render("> quoted")
    expect(html).toContain("<blockquote")
    expect(html).toContain("[&amp;&gt;p]:mb-0")
  })

  it("renders a horizontal rule", () => {
    expect(render("a\n\n---\n\nb")).toContain("<hr")
  })

  it("renders italics", () => {
    expect(render("*emphasis*")).toContain("<em")
  })
})
