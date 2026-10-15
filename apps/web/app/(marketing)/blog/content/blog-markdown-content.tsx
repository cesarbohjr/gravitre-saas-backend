import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

/** Match the shared Gravitre blog typography, including responsive GFM tables. */
export function BlogMarkdownContent({ article }: { article: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        h2: ({ children }) => <h2>{children}</h2>,
        h3: ({ children }) => <h3 className="mt-8 text-xl font-semibold tracking-tight text-foreground">{children}</h3>,
        p: ({ children }) => <p>{children}</p>,
        ul: ({ children }) => <ul>{children}</ul>,
        ol: ({ children }) => <ol className="mt-4 list-decimal space-y-2 pl-6">{children}</ol>,
        li: ({ children }) => <li>{children}</li>,
        a: ({ href, children }) => <a href={href}>{children}</a>,
        table: ({ children }) => (
          <div className="my-8 w-full overflow-x-auto rounded-xl border border-border">
            <table className="w-full min-w-[540px] border-collapse text-left text-sm leading-relaxed">{children}</table>
          </div>
        ),
        thead: ({ children }) => <thead className="bg-[color:var(--g-marketing-surface)] text-foreground">{children}</thead>,
        tbody: ({ children }) => <tbody className="divide-y divide-border">{children}</tbody>,
        tr: ({ children }) => <tr className="border-b border-border last:border-b-0">{children}</tr>,
        th: ({ children }) => <th scope="col" className="px-4 py-3 align-top font-semibold text-foreground">{children}</th>,
        td: ({ children }) => <td className="px-4 py-3 align-top text-foreground/90">{children}</td>,
        blockquote: ({ children }) => <blockquote className="my-6 border-l-4 border-primary pl-4 italic">{children}</blockquote>,
        strong: ({ children }) => <strong>{children}</strong>,
      }}
    >
      {article}
    </ReactMarkdown>
  )
}
