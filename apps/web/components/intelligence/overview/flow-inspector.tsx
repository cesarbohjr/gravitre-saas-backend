"use client"

import Link from "next/link"
import {
  agoLabel,
  layerById,
  type FlowEvent,
  type FlowEventTone,
  type FlowLayerId,
  type FlowModel,
} from "@/components/intelligence/overview/flow-model"
import { TONE_VAR, type PlacedNode } from "@/components/intelligence/overview/flow-map"
import { cn } from "@/lib/utils"

const EVENT_DOT: Record<FlowEventTone, string> = {
  forward: "var(--g-brand)",
  feedback: "var(--g-approval)",
  danger: "var(--g-danger)",
  neutral: "var(--g-text-muted)",
  intelligence: "var(--g-intelligence)",
}

const label = "text-[11px] font-medium text-[color:var(--g-text-muted)]"

export type InspectorSelection = { kind: "layer"; id: FlowLayerId } | { kind: "node"; id: string } | null

export function pathLabel(path: string[], placed: Map<string, PlacedNode>): string {
  return path.map((id) => placed.get(id)?.label ?? "").filter(Boolean).join(" → ")
}

export function FlowInspector({
  model,
  placed,
  selection,
  events,
  streamTitle,
  streamMeta,
  live,
  now,
  traceId,
  onTrace,
  onBack,
  onSelectNode,
  onSelectLayer,
  nodeSignals,
  nodeStrength,
}: {
  model: FlowModel
  placed: Map<string, PlacedNode>
  selection: InspectorSelection
  events: FlowEvent[]
  streamTitle: string
  streamMeta: string
  live: boolean
  now: number
  traceId: string | null
  onTrace: (event: FlowEvent) => void
  onBack: () => void
  onSelectNode: (id: string) => void
  onSelectLayer: (id: FlowLayerId) => void
  nodeSignals: (id: string) => number | null
  nodeStrength: (id: string) => number | null
}) {
  if (selection?.kind === "layer") {
    const layer = layerById(model.layers, selection.id)
    const items = [...placed.values()].filter((n) => n.layer === layer.id && !n.placeholder)
    const max = Math.max(1, ...items.map((n) => nodeSignals(n.id) ?? 0))
    return (
      <div className="flex flex-col gap-3">
        <button type="button" onClick={onBack} className="self-start text-xs font-medium text-[color:var(--g-text-secondary)] hover:text-foreground">
          ← All activity
        </button>
        <div className="flex items-center gap-2.5">
          <span className="h-3 w-3 rounded-[3px]" style={{ background: TONE_VAR[layer.tone] }} aria-hidden />
          <h2 className="text-xl font-semibold text-foreground">{layer.name}</h2>
        </div>
        <p className="text-[13px] leading-relaxed text-[color:var(--g-text-secondary)]">{layer.desc}</p>
        {items.length === 0 ? (
          <p className="text-[13px] text-[color:var(--g-text-muted)]">
            {[...placed.values()].find((n) => n.layer === layer.id)?.desc ?? "Nothing here yet."}
          </p>
        ) : (
          <div className="flex flex-col gap-1.5">
            {items.map((n) => {
              const sig = nodeSignals(n.id)
              return (
                <button
                  key={n.id}
                  type="button"
                  onClick={() => onSelectNode(n.id)}
                  className="flex flex-col gap-1.5 rounded-[var(--np-radius-sm,8px)] border border-[color:var(--g-border-subtle)] px-3 py-2.5 text-left transition-colors hover:border-[color:var(--g-text-primary)]"
                >
                  <span className="flex items-baseline justify-between gap-2">
                    <span className="truncate text-[13px] font-medium text-foreground">{n.label}</span>
                    <span className="shrink-0 font-mono text-[11px] text-[color:var(--g-text-muted)]">
                      {sig == null ? n.sub : `${sig.toLocaleString("en-US")} signals`}
                    </span>
                  </span>
                  {sig != null ? (
                    <span className="block h-1 overflow-hidden rounded-full bg-[color:var(--g-surface-2)]">
                      <span
                        className="block h-full rounded-full"
                        style={{ width: `${Math.round((sig / max) * 100)}%`, background: TONE_VAR[layer.tone] }}
                      />
                    </span>
                  ) : null}
                </button>
              )
            })}
          </div>
        )}
        <Link href={layer.href} className="text-[13px] font-medium text-[color:var(--g-brand-active,var(--g-brand))] hover:underline">
          Open {layer.page} →
        </Link>
      </div>
    )
  }

  if (selection?.kind === "node") {
    const node = placed.get(selection.id)
    if (node) {
      const layer = layerById(model.layers, node.layer)
      const ins = model.edges.filter((e) => e.b === node.id).map((e) => placed.get(e.a)).filter((n): n is PlacedNode => Boolean(n))
      const outs = model.edges.filter((e) => e.a === node.id).map((e) => placed.get(e.b)).filter((n): n is PlacedNode => Boolean(n))
      const sig = nodeSignals(node.id)
      const strength = nodeStrength(node.id)
      const recent = events.filter((e) => e.path.includes(node.id)).slice(0, 3)
      const nodeChips = (list: PlacedNode[]) => (
        <div className="flex flex-wrap gap-1.5">
          {list.map((x) => (
            <button
              key={x.id}
              type="button"
              onClick={() => onSelectNode(x.id)}
              className="inline-flex min-h-8 items-center gap-1.5 rounded-full border border-[color:var(--g-border-subtle)] px-2.5 text-xs text-foreground transition-colors hover:border-[color:var(--g-text-primary)]"
            >
              <span className="h-2 w-2 rounded-full" style={{ background: TONE_VAR[x.tone] }} aria-hidden />
              {x.label}
            </button>
          ))}
        </div>
      )
      return (
        <div className="flex flex-col gap-3.5">
          <nav aria-label="Drill path" className="flex flex-wrap items-center gap-1.5 text-xs text-[color:var(--g-text-muted)]">
            <button type="button" onClick={onBack} className="text-[color:var(--g-text-secondary)] hover:text-foreground">
              All
            </button>
            <span aria-hidden>›</span>
            <button type="button" onClick={() => onSelectLayer(node.layer)} className="text-[color:var(--g-text-secondary)] hover:text-foreground">
              {layer.name}
            </button>
            <span aria-hidden>›</span>
            <span className="truncate font-medium text-foreground">{node.label}</span>
          </nav>
          <div className="flex items-center gap-2.5">
            <span className="h-3 w-3 shrink-0 rounded-full border-2" style={{ borderColor: TONE_VAR[node.tone] }} aria-hidden />
            <h2 className="text-xl font-semibold text-foreground">{node.label}</h2>
          </div>
          <p className="text-[13px] leading-relaxed text-[color:var(--g-text-secondary)]">{node.desc}</p>
          <dl className="grid grid-cols-3 gap-2">
            {[
              ["Signals", sig == null ? "—" : sig.toLocaleString("en-US")],
              ["Links", String(ins.length + outs.length)],
              ["Strength", strength == null ? "—" : `${Math.round(strength * 100)}%`],
            ].map(([k, v]) => (
              <div key={k} className="rounded-[var(--np-radius-sm,8px)] bg-[color:var(--g-surface-2)] px-2.5 py-2">
                <dt className="text-[11px] text-[color:var(--g-text-muted)]">{k}</dt>
                <dd className="font-mono text-base font-semibold tabular-nums text-foreground">{v}</dd>
              </div>
            ))}
          </dl>
          {ins.length ? (
            <div className="flex flex-col gap-1.5">
              <span className={label}>Learns from</span>
              {nodeChips(ins)}
            </div>
          ) : null}
          {outs.length ? (
            <div className="flex flex-col gap-1.5">
              <span className={label}>Powers</span>
              {nodeChips(outs)}
            </div>
          ) : null}
          <div className="flex flex-col gap-1.5">
            <span className={label}>Recent signals</span>
            {recent.length ? (
              <ul className="flex flex-col gap-2">
                {recent.map((r) => (
                  <li key={r.id} className="grid grid-cols-[8px_minmax(0,1fr)_auto] items-start gap-2 text-[12.5px] leading-snug">
                    <span className="mt-1.5 h-2 w-2 rounded-full" style={{ background: EVENT_DOT[r.tone] }} aria-hidden />
                    <span className="text-foreground">{r.text}</span>
                    <span className="font-mono text-[11px] text-[color:var(--g-text-muted)]">{agoLabel(r.at, now)}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <span className="text-[12.5px] text-[color:var(--g-text-muted)]">
                Nothing in this window yet. It will appear here the moment a signal passes through.
              </span>
            )}
          </div>
          <Link href={node.href} className="text-[13px] font-medium text-[color:var(--g-brand-active,var(--g-brand))] hover:underline">
            Open in {layer.page} →
          </Link>
        </div>
      )
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="flex items-center gap-2 text-base font-semibold text-foreground">
          <span className="relative flex h-2 w-2" aria-hidden>
            {live ? <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[color:var(--g-brand)] opacity-50 motion-reduce:hidden" /> : null}
            <span className={cn("relative inline-flex h-2 w-2 rounded-full", live ? "bg-[color:var(--g-brand)]" : "bg-[color:var(--g-approval)]")} />
          </span>
          {streamTitle}
        </h2>
        <span className="font-mono text-[11px] text-[color:var(--g-text-muted)]">{streamMeta}</span>
      </div>
      <p className="text-[13px] leading-relaxed text-[color:var(--g-text-secondary)]">
        Each line is one interaction moving through the core. Click one to trace its path on the map.
      </p>
      {events.length === 0 ? (
        <p className="rounded-[var(--np-radius-sm,8px)] border border-dashed border-[color:var(--g-border-subtle)] px-3 py-4 text-[13px] text-[color:var(--g-text-muted)]">
          Nothing has reached the core yet. Syncs, runs and approvals show up here the moment they happen.
        </p>
      ) : (
        <ol className="flex flex-col gap-1" aria-label={streamTitle}>
          {events.slice(0, 7).map((e) => {
            const on = traceId === e.id
            return (
              <li key={e.id}>
                <button
                  type="button"
                  aria-pressed={on}
                  onClick={() => onTrace(e)}
                  className={cn(
                    "grid w-full grid-cols-[10px_minmax(0,1fr)_auto] items-start gap-2.5 rounded-[var(--np-radius-sm,8px)] border px-2.5 py-2 text-left transition-colors",
                    on
                      ? "border-[color:var(--g-brand)]/30 bg-[color:var(--g-brand-soft)]"
                      : "border-transparent hover:bg-[color:var(--g-surface-2)]",
                  )}
                >
                  <span className="mt-1.5 h-2 w-2 rounded-full" style={{ background: EVENT_DOT[e.tone] }} aria-hidden />
                  <span className="flex min-w-0 flex-col gap-1">
                    <span className="text-[13px] leading-snug text-foreground">{e.text}</span>
                    <span className="truncate font-mono text-[10.5px] text-[color:var(--g-text-muted)]">{pathLabel(e.path, placed)}</span>
                  </span>
                  <span className="font-mono text-[11px] text-[color:var(--g-text-muted)]">{agoLabel(e.at, now)}</span>
                </button>
              </li>
            )
          })}
        </ol>
      )}
    </div>
  )
}
