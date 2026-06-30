import Link from "next/link"
import type { ReactNode } from "react"
import { ArrowRight, Check } from "lucide-react"

import type { DocTier } from "@/lib/docs/types"
import { PlanBadge } from "./plan-badge"

/* ----------------------------------------------------------------------------
 * Steps — numbered setup flows
 * ------------------------------------------------------------------------- */

export function Steps({ children }: { children: ReactNode }) {
  return <div className="my-6 flex flex-col gap-6 [counter-reset:step]">{children}</div>
}

export function Step({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <div className="relative grid grid-cols-[2rem_1fr] gap-4 [counter-increment:step]">
      <div className="flex flex-col items-center">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-emerald-200 bg-emerald-50 text-sm font-semibold text-emerald-700 before:content-[counter(step)]" />
        <div className="mt-2 w-px flex-1 bg-zinc-200" />
      </div>
      <div className="min-w-0 pb-2">
        {title ? <p className="mb-1 font-semibold text-zinc-900">{title}</p> : null}
        <div className="text-sm leading-relaxed text-zinc-600 [&>:first-child]:mt-0">{children}</div>
      </div>
    </div>
  )
}

/* ----------------------------------------------------------------------------
 * Cards
 * ------------------------------------------------------------------------- */

export function CardGrid({ children }: { children: ReactNode }) {
  return <div className="my-6 grid gap-4 sm:grid-cols-2">{children}</div>
}

export function Card({
  title,
  href,
  children,
}: {
  title: string
  href?: string
  children?: ReactNode
}) {
  const inner = (
    <>
      <p className="flex items-center justify-between font-medium text-zinc-900">
        {title}
        {href ? (
          <ArrowRight className="h-4 w-4 text-zinc-400 transition-transform group-hover:translate-x-0.5 group-hover:text-emerald-600" />
        ) : null}
      </p>
      {children ? <div className="mt-1 text-sm leading-relaxed text-zinc-500">{children}</div> : null}
    </>
  )

  const className =
    "group block rounded-xl border border-zinc-200 bg-white p-4 transition-all hover:border-emerald-300 hover:shadow-sm"

  if (href) {
    return (
      <Link href={href} className={className}>
        {inner}
      </Link>
    )
  }
  return <div className={className}>{inner}</div>
}

/* ----------------------------------------------------------------------------
 * Screenshot frames — dark app chrome window
 * ------------------------------------------------------------------------- */

interface ScreenshotPin {
  n: number
  /** percentage offsets within the frame */
  x: number
  y: number
}

function ChromeBar({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 border-b border-white/10 bg-[#11161D] px-3 py-2">
      <span className="h-2.5 w-2.5 rounded-full bg-rose-400/70" />
      <span className="h-2.5 w-2.5 rounded-full bg-amber-400/70" />
      <span className="h-2.5 w-2.5 rounded-full bg-emerald-400/70" />
      {label ? (
        <span className="ml-3 truncate rounded bg-white/5 px-2 py-0.5 font-mono text-[11px] text-zinc-400">
          {label}
        </span>
      ) : null}
    </div>
  )
}

export function Screenshot({
  src,
  alt,
  caption,
  route,
  pins,
}: {
  src: string
  alt: string
  caption?: string
  route?: string
  pins?: ScreenshotPin[]
}) {
  return (
    <figure className="my-6">
      <div className="overflow-hidden rounded-xl border border-zinc-200 shadow-lg shadow-zinc-900/5">
        <ChromeBar label={route} />
        <div className="relative bg-[#0B0F14]">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={src} alt={alt} className="block w-full" loading="lazy" />
          {pins?.map((pin) => (
            <span
              key={pin.n}
              className="absolute flex h-6 w-6 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border-2 border-white bg-emerald-600 text-xs font-bold text-white shadow-md"
              style={{ left: `${pin.x}%`, top: `${pin.y}%` }}
            >
              {pin.n}
            </span>
          ))}
        </div>
      </div>
      {caption ? (
        <figcaption className="mt-2 text-center text-sm text-zinc-500">{caption}</figcaption>
      ) : null}
    </figure>
  )
}

export function ScreenshotPlaceholder({
  route,
  label,
}: {
  route: string
  label?: string
}) {
  return (
    <figure className="my-6">
      <div className="overflow-hidden rounded-xl border border-zinc-200 shadow-lg shadow-zinc-900/5">
        <ChromeBar label={route} />
        <div className="flex aspect-[16/10] flex-col items-center justify-center gap-2 bg-[#0B0F14] bg-[radial-gradient(circle_at_1px_1px,rgba(255,255,255,0.06)_1px,transparent_0)] [background-size:20px_20px]">
          <span className="rounded-md border border-white/10 bg-white/5 px-3 py-1 font-mono text-xs text-zinc-400">
            {route}
          </span>
          <span className="text-xs text-zinc-600">{label ?? "Product screenshot"}</span>
        </div>
      </div>
    </figure>
  )
}

/* ----------------------------------------------------------------------------
 * Diagram — ASCII / mermaid-friendly container with legend
 * ------------------------------------------------------------------------- */

export function Diagram({
  title,
  legend,
  children,
}: {
  title?: string
  legend?: ReactNode
  children: ReactNode
}) {
  return (
    <figure className="my-6 overflow-hidden rounded-xl border border-zinc-200 bg-zinc-50">
      {title ? (
        <div className="border-b border-zinc-200 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-zinc-500">
          {title}
        </div>
      ) : null}
      <pre className="overflow-x-auto p-4 font-mono text-xs leading-relaxed text-zinc-700">
        {children}
      </pre>
      {legend ? (
        <figcaption className="border-t border-zinc-200 px-4 py-2 text-xs text-zinc-500">
          {legend}
        </figcaption>
      ) : null}
    </figure>
  )
}

/* ----------------------------------------------------------------------------
 * TierCallout — "Requires Control plan"
 * ------------------------------------------------------------------------- */

export function TierCallout({
  tier,
  children,
}: {
  tier: DocTier
  children?: ReactNode
}) {
  return (
    <div className="my-5 flex items-start gap-3 rounded-xl border border-zinc-200 bg-zinc-50 p-4">
      <PlanBadge tier={tier} />
      <p className="text-sm leading-relaxed text-zinc-600">
        {children ?? (
          <>
            This feature requires the <strong>{tier}</strong> plan or higher.
          </>
        )}{" "}
        <Link href="/docs/billing/plans" className="font-medium text-emerald-700 hover:underline">
          View plans
        </Link>
      </p>
    </div>
  )
}

/* ----------------------------------------------------------------------------
 * VendorLogo
 * ------------------------------------------------------------------------- */

export function VendorLogo({
  name,
  src,
  size = 40,
}: {
  name: string
  src?: string
  size?: number
}) {
  if (src) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={src}
        alt={`${name} logo`}
        width={size}
        height={size}
        className="rounded-lg object-contain"
      />
    )
  }
  return (
    <span
      className="flex items-center justify-center rounded-lg border border-zinc-200 bg-white font-semibold text-zinc-700"
      style={{ width: size, height: size }}
      aria-label={`${name} logo`}
    >
      {name.charAt(0).toUpperCase()}
    </span>
  )
}

/* ----------------------------------------------------------------------------
 * FAQItem — inline question/answer (native disclosure)
 * ------------------------------------------------------------------------- */

export function FAQItem({ question, children }: { question: string; children: ReactNode }) {
  return (
    <details className="group border-b border-zinc-200 py-3">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-sm font-medium text-zinc-900">
        {question}
        <span className="text-zinc-400 transition-transform group-open:rotate-45">+</span>
      </summary>
      <div className="mt-2 text-sm leading-relaxed text-zinc-600">{children}</div>
    </details>
  )
}

/* ----------------------------------------------------------------------------
 * CompareTable — docs name vs UI route
 * ------------------------------------------------------------------------- */

export function CompareTable({
  rows,
  leftHeader = "Docs name",
  rightHeader = "In the app",
}: {
  rows: { left: string; right: string }[]
  leftHeader?: string
  rightHeader?: string
}) {
  return (
    <div className="my-6 overflow-hidden rounded-xl border border-zinc-200">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-zinc-200 bg-zinc-50 text-left">
            <th className="px-4 py-2.5 font-medium text-zinc-700">{leftHeader}</th>
            <th className="px-4 py-2.5 font-medium text-zinc-700">{rightHeader}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.left} className="border-b border-zinc-100 last:border-0">
              <td className="px-4 py-2.5 font-medium text-zinc-900">{row.left}</td>
              <td className="px-4 py-2.5 text-zinc-500">{row.right}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/* ----------------------------------------------------------------------------
 * Prerequisites checklist (used by integration template)
 * ------------------------------------------------------------------------- */

export function Prerequisites({ items }: { items: string[] }) {
  return (
    <div className="my-5 rounded-xl border border-zinc-200 bg-zinc-50 p-4">
      <p className="mb-3 text-sm font-semibold text-zinc-900">Prerequisites</p>
      <ul className="space-y-2">
        {items.map((item) => (
          <li key={item} className="flex items-start gap-2 text-sm text-zinc-600">
            <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
            {item}
          </li>
        ))}
      </ul>
    </div>
  )
}
