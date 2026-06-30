"use client"

import {
  Children,
  isValidElement,
  useState,
  type ReactElement,
  type ReactNode,
} from "react"
import { AlertTriangle, CheckCircle2, Copy, Info, Lightbulb, OctagonAlert } from "lucide-react"

export function CodeBlock({
  children,
  language,
}: {
  children: React.ReactNode
  language?: string
}) {
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
    <div className="group relative my-4 overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900">
      <div className="flex items-center justify-between border-b border-zinc-800 px-4 py-2">
        <span className="font-mono text-xs uppercase tracking-wide text-zinc-500">
          {language ?? "code"}
        </span>
        <button
          type="button"
          onClick={copy}
          className="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-zinc-200"
          aria-label="Copy code"
        >
          {copied ? (
            <>
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
              Copied
            </>
          ) : (
            <>
              <Copy className="h-3.5 w-3.5" />
              Copy
            </>
          )}
        </button>
      </div>
      <pre className="overflow-x-auto p-4 text-sm">
        <code className="font-mono text-zinc-300">{text}</code>
      </pre>
    </div>
  )
}

type CalloutType = "info" | "warning" | "tip" | "danger"

const CALLOUT_STYLES: Record<
  CalloutType,
  { container: string; title: string; body: string; icon: typeof Info }
> = {
  tip: {
    container: "border-emerald-200 bg-emerald-50/70",
    title: "text-emerald-900",
    body: "text-emerald-900/90",
    icon: Lightbulb,
  },
  info: {
    container: "border-zinc-200 bg-zinc-50",
    title: "text-zinc-900",
    body: "text-zinc-600",
    icon: Info,
  },
  warning: {
    container: "border-amber-200 bg-amber-50/70",
    title: "text-amber-900",
    body: "text-amber-900/90",
    icon: AlertTriangle,
  },
  danger: {
    container: "border-rose-200 bg-rose-50/70",
    title: "text-rose-900",
    body: "text-rose-900/90",
    icon: OctagonAlert,
  },
}

export function Callout({
  title,
  type = "tip",
  children,
}: {
  title?: string
  type?: CalloutType
  children: React.ReactNode
}) {
  const style = CALLOUT_STYLES[type] ?? CALLOUT_STYLES.tip
  const Icon = style.icon
  return (
    <div className={`my-5 flex gap-3 rounded-xl border p-4 ${style.container}`}>
      <Icon className={`mt-0.5 h-5 w-5 shrink-0 ${style.title}`} aria-hidden />
      <div className="min-w-0">
        {title ? <p className={`mb-1 text-sm font-semibold ${style.title}`}>{title}</p> : null}
        <div className={`text-sm leading-relaxed [&_a]:underline ${style.body}`}>{children}</div>
      </div>
    </div>
  )
}

interface TabProps {
  label: string
  children: ReactNode
}

export function Tab({ children }: TabProps) {
  return <>{children}</>
}

export function Tabs({ children }: { children: ReactNode }) {
  const tabs = Children.toArray(children).filter(
    (child): child is ReactElement<TabProps> => isValidElement(child),
  )
  const [active, setActive] = useState(0)

  if (tabs.length === 0) return null

  return (
    <div className="my-5 overflow-hidden rounded-xl border border-zinc-200">
      <div role="tablist" className="flex flex-wrap gap-1 border-b border-zinc-200 bg-zinc-50 px-2 py-1.5">
        {tabs.map((tab, index) => {
          const selected = index === active
          return (
            <button
              key={tab.props.label ?? index}
              role="tab"
              aria-selected={selected}
              type="button"
              onClick={() => setActive(index)}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                selected
                  ? "bg-white text-emerald-700 shadow-sm"
                  : "text-zinc-500 hover:text-zinc-900"
              }`}
            >
              {tab.props.label ?? `Tab ${index + 1}`}
            </button>
          )
        })}
      </div>
      <div role="tabpanel" className="px-4 py-2">
        {tabs[active]}
      </div>
    </div>
  )
}
