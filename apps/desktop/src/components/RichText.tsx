import { Fragment, type ReactNode } from "react"

/** Bold, inline code and links inside one line. Built as elements, never as HTML. */
function inline(text: string, key: string): ReactNode[] {
  const out: ReactNode[] = []
  const re = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\((https?:\/\/[^)\s]+)\))/g
  let last = 0
  let m: RegExpExecArray | null
  let i = 0
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index))
    const tok = m[0]
    if (tok.startsWith("**")) out.push(<b key={`${key}-${i++}`}>{tok.slice(2, -2)}</b>)
    else if (tok.startsWith("`")) out.push(<code key={`${key}-${i++}`} className="mono" style={{ fontSize: "0.92em", background: "var(--s2)", padding: "1px 4px", borderRadius: 4 }}>{tok.slice(1, -1)}</code>)
    else {
      const label = tok.slice(1, tok.indexOf("]"))
      out.push(
        <a key={`${key}-${i++}`} href={m[2]} target="_blank" rel="noreferrer">
          {label}
        </a>,
      )
    }
    last = m.index + tok.length
  }
  if (last < text.length) out.push(text.slice(last))
  return out
}

/** The small part of Markdown answers use: paragraphs, bullet and numbered lists, headings, bold. */
export function RichText({ text, size = 15 }: { text: string; size?: number }) {
  const blocks: ReactNode[] = []
  const lines = text.replace(/\r\n/g, "\n").split("\n")
  let list: { ordered: boolean; items: string[] } | null = null
  let para: string[] = []
  const flushPara = () => {
    if (para.length) {
      const k = `p${blocks.length}`
      blocks.push(
        <p key={k} style={{ margin: 0, fontSize: size, lineHeight: 1.6 }}>
          {para.map((line, i) => (
            <Fragment key={i}>
              {i > 0 ? <br /> : null}
              {inline(line, `${k}-${i}`)}
            </Fragment>
          ))}
        </p>,
      )
      para = []
    }
  }
  const flushList = () => {
    if (list) {
      const k = `l${blocks.length}`
      const items = list.items.map((item, i) => (
        <li key={i} style={{ margin: "2px 0" }}>
          {inline(item, `${k}-${i}`)}
        </li>
      ))
      const style = { margin: 0, paddingLeft: 22, fontSize: size, lineHeight: 1.6 }
      blocks.push(list.ordered ? <ol key={k} style={style}>{items}</ol> : <ul key={k} style={style}>{items}</ul>)
      list = null
    }
  }
  for (const raw of lines) {
    const line = raw.trimEnd()
    const bullet = /^\s*[-*•]\s+(.*)$/.exec(line)
    const numbered = /^\s*\d+[.)]\s+(.*)$/.exec(line)
    const heading = /^#{1,4}\s+(.*)$/.exec(line)
    if (!line.trim()) {
      flushPara()
      flushList()
    } else if (heading) {
      flushPara()
      flushList()
      blocks.push(
        <p key={`h${blocks.length}`} style={{ margin: 0, fontSize: size, fontWeight: 600 }}>
          {inline(heading[1], `h${blocks.length}`)}
        </p>,
      )
    } else if (bullet || numbered) {
      flushPara()
      const ordered = Boolean(numbered)
      if (list && list.ordered !== ordered) flushList()
      list ??= { ordered, items: [] }
      list.items.push((bullet || numbered)![1])
    } else {
      flushList()
      para.push(line)
    }
  }
  flushPara()
  flushList()
  return <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>{blocks}</div>
}
