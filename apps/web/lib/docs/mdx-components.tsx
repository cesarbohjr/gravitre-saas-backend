import type { ReactNode, HTMLAttributes } from "react"
import Link from "next/link"

import { CodeBlock, Callout, Tabs, Tab } from "@/components/docs/mdx-client"
import {
  Steps,
  Step,
  Card,
  CardGrid,
  Screenshot,
  ScreenshotPlaceholder,
  Diagram,
  TierCallout,
  VendorLogo,
  FAQItem,
  CompareTable,
  Prerequisites,
} from "@/components/docs/mdx-elements"
import { PlanBadge } from "@/components/docs/plan-badge"

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
    <h1 className="mb-4 mt-8 text-2xl font-semibold text-foreground first:mt-0" {...props} />
  ),
  h2: (props: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h2 className="mb-3 mt-10 scroll-mt-24 text-xl font-semibold text-foreground" {...props} />
  ),
  h3: (props: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h3 className="mb-2 mt-6 scroll-mt-24 text-lg font-medium text-foreground" {...props} />
  ),
  p: (props: React.HTMLAttributes<HTMLParagraphElement>) => (
    <p className="mb-4 leading-7 text-muted-foreground" {...props} />
  ),
  ul: (props: React.HTMLAttributes<HTMLUListElement>) => (
    <ul className="mb-4 list-disc space-y-2 pl-6 text-muted-foreground" {...props} />
  ),
  ol: (props: React.HTMLAttributes<HTMLOListElement>) => (
    <ol className="mb-4 list-decimal space-y-2 pl-6 text-muted-foreground" {...props} />
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
          className="font-medium text-brand-text underline-offset-2 hover:underline"
          target="_blank"
          rel="noopener noreferrer"
          {...props}
        />
      )
    }

    return (
      <Link
        href={href}
        className="font-medium text-brand-text underline-offset-2 hover:underline"
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
      <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-sm text-foreground" {...props} />
    )
  },
  pre: ({ children }: { children?: React.ReactNode }) => (
    <CodeBlock>{extractText(children)}</CodeBlock>
  ),
  blockquote: (props: React.HTMLAttributes<HTMLQuoteElement>) => (
    <blockquote className="my-4 border-l-4 border-brand/50 pl-4 text-muted-foreground" {...props} />
  ),
  hr: () => <hr className="my-8 border-border" />,
  table: (props: React.HTMLAttributes<HTMLTableElement>) => (
    <div className="my-6 overflow-x-auto rounded-xl border border-border">
      <table className="w-full text-sm" {...props} />
    </div>
  ),
  thead: (props: React.HTMLAttributes<HTMLTableSectionElement>) => (
    <thead className="border-b border-border bg-muted text-left" {...props} />
  ),
  th: (props: React.HTMLAttributes<HTMLTableCellElement>) => (
    <th className="px-4 py-2.5 font-medium text-foreground" {...props} />
  ),
  td: (props: React.HTMLAttributes<HTMLTableCellElement>) => (
    <td className="border-b border-border-subtle px-4 py-2.5 text-muted-foreground" {...props} />
  ),
  // Doc authoring components
  Callout,
  Tabs,
  Tab,
  Steps,
  Step,
  Card,
  CardGrid,
  Screenshot,
  ScreenshotPlaceholder,
  Diagram,
  TierCallout,
  PlanBadge,
  VendorLogo,
  FAQItem,
  CompareTable,
  Prerequisites,
}
