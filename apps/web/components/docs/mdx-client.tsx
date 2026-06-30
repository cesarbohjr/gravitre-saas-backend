"use client"

import { useState } from "react"
import { CheckCircle2, Copy } from "lucide-react"

export function CodeBlock({ children }: { children: React.ReactNode }) {
  const text =
    typeof children === "string"
      ? children
      : Array.isArray(children)
        ? children.join("")
        : String(children ?? "")

  const [copied, setCopied] = useState(false)

  const copy = () => {
    void navigator.clipboard.writeText(text.trim())
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="relative my-4 overflow-hidden rounded-xl bg-zinc-900">
      <button
        type="button"
        onClick={copy}
        className="absolute right-3 top-3 rounded-lg bg-zinc-700 p-2 transition-colors hover:bg-zinc-600"
        aria-label="Copy code"
      >
        {copied ? (
          <CheckCircle2 className="h-4 w-4 text-emerald-400" />
        ) : (
          <Copy className="h-4 w-4 text-zinc-400" />
        )}
      </button>
      <pre className="overflow-x-auto p-4 text-sm">
        <code className="font-mono text-zinc-300">{text}</code>
      </pre>
    </div>
  )
}

export function Callout({
  title,
  children,
}: {
  title?: string
  children: React.ReactNode
}) {
  return (
    <div className="my-4 rounded-xl border border-emerald-200 bg-emerald-50/70 p-4">
      {title ? <p className="mb-2 text-sm font-medium text-emerald-900">{title}</p> : null}
      <div className="text-sm text-emerald-900/90">{children}</div>
    </div>
  )
}
