import type { ReactElement, ReactNode, HTMLAttributes, AnchorHTMLAttributes } from "react"
import Link from "next/link"

import { CodeBlock, Callout } from "@/components/docs/mdx-client"

function extractText(node: ReactNode): string {
  if (typeof node === "string") return node
  if (typeof node === "number") return String(node)
  if (Array.isArray(node)) return node.map(extractText).join("")
  if (node && typeof node === "object" && "props" in node) {
    const props = (node as { props?: { children?: ReactNode } }).props
    return extractText(props?.children)
  }
  return ""
}

export const mdxComponents = {
  h1: (props: HTMLAttributes<HTMLHeadingElement>) => (
    <h1 className="mb-4 mt-8 text-2xl font-semibold text-zinc-900 first:mt-0" {...props} />
  ),
  h2: (props: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h2 className="mb-3 mt-10 text-xl font-semibold text-zinc-900" {...props} />
  ),
  h3: (props: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h3 className="mb-2 mt-6 text-lg font-medium text-zinc-900" {...props} />
  ),
  p: (props: React.HTMLAttributes<HTMLParagraphElement>) => (
    <p className="mb-4 leading-7 text-zinc-600" {...props} />
  ),
  ul: (props: React.HTMLAttributes<HTMLUListElement>) => (
    <ul className="mb-4 list-disc space-y-2 pl-6 text-zinc-600" {...props} />
  ),
  ol: (props: React.HTMLAttributes<HTMLOListElement>) => (
    <ol className="mb-4 list-decimal space-y-2 pl-6 text-zinc-600" {...props} />
  ),
  li: (props: React.HTMLAttributes<HTMLLIElement>) => (
    <li className="leading-7" {...props} />
  ),
  a: (props: React.AnchorHTMLAttributes<HTMLAnchorElement>) => {
    const href = props.href ?? "#"
    const isExternal = href.startsWith("http")

    if (isExternal) {
      return (
        <a
          className="font-medium text-emerald-700 underline-offset-2 hover:underline"
          target="_blank"
          rel="noopener noreferrer"
          {...props}
        />
      )
    }

    return (
      <Link
        href={href}
        className="font-medium text-emerald-700 underline-offset-2 hover:underline"
      >
        {props.children}
      </Link>
    )
  },
  code: (props: React.HTMLAttributes<HTMLElement>) => {
    const isBlock = typeof props.className === "string" && props.className.includes("language-")
    if (isBlock) {
      return <CodeBlock>{props.children}</CodeBlock>
    }
    return (
      <code className="rounded bg-zinc-100 px-1.5 py-0.5 font-mono text-sm text-zinc-800" {...props} />
    )
  },
  pre: ({ children }: { children?: React.ReactNode }) => (
    <CodeBlock>{extractText(children)}</CodeBlock>
  ),
  blockquote: (props: React.HTMLAttributes<HTMLQuoteElement>) => (
    <blockquote className="my-4 border-l-4 border-emerald-300 pl-4 text-zinc-600" {...props} />
  ),
  hr: () => <hr className="my-8 border-zinc-200" />,
  Callout,
}
