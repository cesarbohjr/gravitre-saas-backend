"use client"

import type { ReactNode } from "react"
import {
  BookOpen,
  Bot,
  CheckCircle2,
  Clock3,
  Code2,
  Eye,
  FileText,
  Headphones,
  LayoutGrid,
  Lock,
  Mail,
  Megaphone,
  MessageSquare,
  PenLine,
  PenTool,
  Plug,
  Route,
  Settings2,
  ShieldCheck,
  TrendingUp,
  Wallet,
  Workflow,
  Zap,
} from "lucide-react"
import { cn } from "@/lib/utils"
import {
  HubSpotLogo,
  LinearLogo,
  NotionLogo,
  SalesforceLogo,
  SlackLogo,
} from "@/components/marketing/nodus-icons/general"
import {
  NodusBadge,
  NodusBars,
  NodusHub,
  NodusLabel,
  NodusPath,
  NodusRow,
  NodusStage,
  NodusTile,
  NodusWindow,
} from "./kit"

/** Absolute placement inside a NodusStage. */
function At({ x, y, w, children, className }: { x: number; y: number; w?: number; children: ReactNode; className?: string }) {
  return (
    <div className={cn("absolute", className)} style={{ left: x, top: y, width: w }}>
      {children}
    </div>
  )
}

const muted = "text-gray-600"

/* ------------------------------------------------------------------ */
/* Home · Governed by design                                           */
/* ------------------------------------------------------------------ */

export function GovernedScene({ className }: { className?: string }) {
  return (
    <NodusStage width={560} height={330} className={className}>
      <At x={16} y={44} w={304}>
        <NodusWindow title="Approval gate">
          <div className="flex flex-col gap-1">
            <NodusRow icon={<FileText className={muted} />} label="Submit request" meta={<NodusBadge tone="brand">Done</NodusBadge>} />
            <NodusRow icon={<Route className={muted} />} label="Auto-route to reviewers" meta={<NodusBadge>Routed</NodusBadge>} />
            <NodusRow active icon={<ShieldCheck className="text-brand" />} label="Review & approve" meta={<NodusBadge tone="warning">Waiting</NodusBadge>} />
            <NodusRow icon={<Lock className={muted} />} label="Immutable audit log" meta={<span className="text-xs text-gray-500">Always on</span>} />
          </div>
        </NodusWindow>
      </At>
      <NodusPath points={[[320, 172], [428, 172]]} />
      <At x={340} y={161}>
        <NodusBadge>Connected</NodusBadge>
      </At>
      <At x={428} y={140}>
        <NodusHub />
      </At>
      <At x={436} y={26}>
        <NodusTile>
          <HubSpotLogo />
        </NodusTile>
      </At>
      <NodusPath points={[[460, 74], [460, 140]]} tone="brand" delay={0.4} />
      <NodusPath points={[[460, 204], [460, 266]]} tone="brand" delay={0.8} />
      <At x={436} y={266}>
        <NodusTile>
          <SalesforceLogo />
        </NodusTile>
      </At>
    </NodusStage>
  )
}

/* ------------------------------------------------------------------ */
/* About · Build with us                                               */
/* ------------------------------------------------------------------ */

function HubSpokes({
  labels,
  tiles,
  badge = "Connected",
}: {
  labels: { icon: ReactNode; text: string }[]
  tiles: ReactNode[]
  badge?: string
}) {
  const hub = { x: 244, y: 128 }
  const cy = hub.y + 32
  const rows = [66, 152, 238]
  return (
    <NodusStage width={560} height={320}>
      {labels.map((l, i) => (
        <At key={l.text} x={24} y={rows[i] - 10}>
          <NodusLabel icon={l.icon}>{l.text}</NodusLabel>
        </At>
      ))}
      {rows.map((y, i) => (
        <NodusPath
          key={`l${i}`}
          points={y === cy ? [[150, y], [hub.x, y]] : [[150, y], [206, y], [206, cy], [hub.x, cy]]}
          tone={(["brand", "info", "warning"] as const)[i]}
          delay={i * 0.35}
        />
      ))}
      <At x={hub.x} y={hub.y}>
        <NodusHub />
      </At>
      <NodusPath points={[[hub.x + 64, cy], [420, cy]]} delay={0.5} />
      <At x={330} y={cy - 11}>
        <NodusBadge>{badge}</NodusBadge>
      </At>
      {tiles.map((t, i) => {
        const ty = [44, 136, 228][i]
        return (
          <div key={i}>
            {ty + 24 !== cy ? (
              <NodusPath points={[[420, cy], [420, ty + 24], [472, ty + 24]]} tone="info" delay={0.9 + i * 0.3} />
            ) : (
              <NodusPath points={[[420, cy], [472, cy]]} tone="info" delay={0.9} />
            )}
            <At x={472} y={ty}>
              <NodusTile>{t}</NodusTile>
            </At>
          </div>
        )
      })}
    </NodusStage>
  )
}

export function BuildWithUsScene() {
  return (
    <HubSpokes
      labels={[
        { icon: <Bot className={muted} />, text: "Agents" },
        { icon: <Workflow className={muted} />, text: "Workflows" },
        { icon: <Plug className={muted} />, text: "Connectors" },
      ]}
      tiles={[<SlackLogo key="s" />, <NotionLogo key="n" />, <LinearLogo key="l" />]}
    />
  )
}

/* ------------------------------------------------------------------ */
/* Support                                                             */
/* ------------------------------------------------------------------ */

export function SupportScene() {
  const cy = 160
  return (
    <NodusStage width={560} height={320}>
      {[
        { icon: <BookOpen className={muted} />, text: "Guides", y: 66 },
        { icon: <FileText className={muted} />, text: "Docs", y: 152 },
        { icon: <MessageSquare className={muted} />, text: "Contact", y: 238 },
      ].map((l, i) => (
        <div key={l.text}>
          <At x={24} y={l.y - 10}>
            <NodusLabel icon={l.icon}>{l.text}</NodusLabel>
          </At>
          <NodusPath
            points={l.y === cy ? [[120, l.y], [200, l.y]] : [[120, l.y], [170, l.y], [170, cy], [200, cy]]}
            tone={(["brand", "info", "warning"] as const)[i]}
            delay={i * 0.35}
          />
        </div>
      ))}
      <At x={200} y={cy - 32}>
        <NodusHub />
      </At>
      <NodusPath points={[[264, cy], [330, cy]]} delay={0.6} />
      <At x={330} y={84} w={220}>
        <NodusWindow title="Your question">
          <div className="flex flex-col gap-1">
            <NodusRow icon={<MessageSquare className={muted} />} label="Asked" meta={<span className="text-xs text-gray-500">2m</span>} />
            <NodusRow icon={<BookOpen className={muted} />} label="Guide" meta={<NodusBadge>Sent</NodusBadge>} />
            <NodusRow active icon={<CheckCircle2 className="text-brand" />} label="Answered" meta={<NodusBadge tone="brand">Resolved</NodusBadge>} />
          </div>
        </NodusWindow>
      </At>
    </NodusStage>
  )
}

/* ------------------------------------------------------------------ */
/* Careers · Open roles                                                */
/* ------------------------------------------------------------------ */

export function OpenRolesScene() {
  return (
    <NodusStage width={560} height={300}>
      <At x={40} y={50} w={320}>
        <NodusWindow title="Teams">
          <div className="flex flex-col gap-1">
            <NodusRow icon={<Code2 className={muted} />} label="Engineering" meta={<NodusBars widths={[100]} className="w-16" />} />
            <NodusRow icon={<PenTool className={muted} />} label="Design" meta={<NodusBars widths={[100]} className="w-12" />} />
            <NodusRow active icon={<Megaphone className="text-brand" />} label="Go-to-market" meta={<NodusBadge tone="brand">Say hello</NodusBadge>} />
          </div>
        </NodusWindow>
      </At>
      <NodusPath points={[[360, 165], [436, 165]]} />
      <At x={436} y={133}>
        <NodusHub />
      </At>
      <NodusPath points={[[468, 197], [468, 236]]} tone="brand" delay={0.6} />
      <At x={444} y={236}>
        <NodusTile>
          <Mail className="text-charcoal-700" />
        </NodusTile>
      </At>
    </NodusStage>
  )
}

/* ------------------------------------------------------------------ */
/* Marketplace                                                         */
/* ------------------------------------------------------------------ */

export function MarketplaceScene() {
  const icons = [TrendingUp, Headphones, Megaphone, Wallet, Settings2, Code2]
  return (
    <NodusStage width={560} height={320}>
      <At x={24} y={40} w={316}>
        <NodusWindow title="Marketplace">
          <div className="grid grid-cols-3 gap-2">
            {icons.map((Icon, i) => (
              <div
                key={i}
                className={cn(
                  "flex flex-col gap-2 rounded-md border p-2",
                  i === 1 ? "border-brand/25 bg-brand/[0.06]" : "border-border",
                )}
              >
                <span className="flex size-7 items-center justify-center rounded-md border border-border bg-card">
                  <Icon className={cn("size-3.5", i === 1 ? "text-brand" : muted)} />
                </span>
                <NodusBars widths={[80, 55]} />
              </div>
            ))}
          </div>
          <div className="mt-2 flex items-center justify-between rounded-md px-1 pt-1">
            <span className="text-charcoal-700 text-xs font-medium">Readiness check</span>
            <NodusBadge tone="brand">Passed</NodusBadge>
          </div>
        </NodusWindow>
      </At>
      <NodusPath points={[[340, 170], [432, 170]]} />
      <At x={432} y={138}>
        <NodusHub />
      </At>
      <At x={440} y={30}>
        <NodusTile>
          <SlackLogo />
        </NodusTile>
      </At>
      <NodusPath points={[[464, 78], [464, 138]]} tone="brand" delay={0.4} />
      <NodusPath points={[[464, 202], [464, 256]]} tone="warning" delay={0.8} />
      <At x={440} y={256}>
        <NodusTile>
          <HubSpotLogo />
        </NodusTile>
      </At>
    </NodusStage>
  )
}

/* ------------------------------------------------------------------ */
/* Guides · featured thumbnails (16:9)                                 */
/* ------------------------------------------------------------------ */

export type GuideSceneKind = "extension" | "agent" | "capabilities" | "workflows" | "reports"

export function GuideScene({ kind }: { kind: GuideSceneKind }) {
  if (kind === "extension") {
    return (
      <NodusStage width={320} height={180}>
        <At x={24} y={20} w={272}>
          <NodusWindow className="p-2.5">
            <div className="flex gap-2">
              <div className="flex flex-1 flex-col gap-2 pt-1">
                <span className="h-3 rounded-full bg-gray-200" />
                <NodusBars widths={[90, 70, 80]} />
                <NodusBars widths={[60, 75]} />
              </div>
              <div className="flex w-24 flex-col items-center gap-2 rounded-md border border-brand/25 bg-brand/[0.06] p-2">
                <NodusHub size={36} />
                <NodusBars widths={[90, 60]} className="w-full" />
                <NodusBadge tone="brand" className="px-1.5 text-[10px]">Approve</NodusBadge>
              </div>
            </div>
          </NodusWindow>
        </At>
      </NodusStage>
    )
  }
  if (kind === "agent") {
    return (
      <NodusStage width={320} height={180}>
        <At x={24} y={66}>
          <NodusTile>
            <Bot className="text-charcoal-700" />
          </NodusTile>
        </At>
        <NodusPath points={[[72, 90], [128, 90]]} tone="brand" />
        <At x={128} y={58}>
          <NodusHub />
        </At>
        <NodusPath points={[[192, 90], [214, 90]]} delay={0.6} />
        <At x={214} y={79}>
          <NodusBadge tone="brand">Agent ready</NodusBadge>
        </At>
      </NodusStage>
    )
  }
  if (kind === "capabilities") {
    const caps = [Eye, PenLine, ShieldCheck, Clock3]
    return (
      <NodusStage width={320} height={180}>
        {caps.map((Icon, i) => (
          <At key={i} x={24 + i * 74} y={52}>
            <NodusTile className={i === 2 ? "border-brand/30 bg-[color:color-mix(in_srgb,var(--brand)_6%,var(--card))]" : undefined}>
              <Icon className={i === 2 ? "text-brand" : "text-charcoal-700"} />
            </NodusTile>
          </At>
        ))}
        {[0, 1, 2].map((i) => (
          <NodusPath key={i} points={[[72 + i * 74, 76], [98 + i * 74, 76]]} tone={i === 1 ? "brand" : "info"} delay={i * 0.4} />
        ))}
        <At x={127} y={122}>
          <NodusBadge>Connected</NodusBadge>
        </At>
      </NodusStage>
    )
  }
  if (kind === "workflows") {
    return (
      <NodusStage width={320} height={180}>
        <At x={28} y={64}>
          <NodusTile>
            <Zap className="text-charcoal-700" />
          </NodusTile>
        </At>
        <NodusPath points={[[76, 88], [128, 88]]} tone="brand" />
        <At x={128} y={56}>
          <NodusHub />
        </At>
        <NodusPath points={[[192, 88], [244, 88]]} tone="warning" delay={0.6} />
        <At x={244} y={64}>
          <NodusTile>
            <CheckCircle2 className="text-brand" />
          </NodusTile>
        </At>
        <At x={113} y={134}>
          <NodusBadge tone="warning">Needs approval</NodusBadge>
        </At>
      </NodusStage>
    )
  }
  return (
    <NodusStage width={320} height={180}>
      <At x={40} y={22} w={240}>
        <NodusWindow title="Reports" className="p-2.5">
          {[
            ["Runs", 82],
            ["Approved", 64],
            ["Time saved", 48],
          ].map(([label, w]) => (
            <div key={label as string} className="mt-1.5">
              <div className="text-charcoal-700 mb-1 text-[11px] font-medium">{label}</div>
              <div className="h-1.5 rounded-full bg-gray-200">
                <div className="h-full rounded-full bg-brand" style={{ width: `${w}%` }} />
              </div>
            </div>
          ))}
        </NodusWindow>
      </At>
    </NodusStage>
  )
}

/* ------------------------------------------------------------------ */
/* Home · Use cases network                                            */
/* ------------------------------------------------------------------ */

const DEPTS = [
  { label: "Engineering", icon: Code2, side: "l", y: 40 },
  { label: "Sales", icon: TrendingUp, side: "l", y: 124 },
  { label: "Marketing", icon: Megaphone, side: "l", y: 208 },
  { label: "Support", icon: Headphones, side: "r", y: 40 },
  { label: "Finance", icon: Wallet, side: "r", y: 124 },
  { label: "Operations", icon: Settings2, side: "r", y: 208 },
] as const

export function UseCasesScene({ className }: { className?: string }) {
  const hub = { x: 448, y: 118 }
  const cy = hub.y + 32
  const tones = ["brand", "info", "warning"] as const
  return (
    <NodusStage width={960} height={300} className={className}>
      {DEPTS.map((d, i) => {
        const left = d.side === "l"
        const cardX = left ? 96 : 704
        const rowY = d.y + 26
        const edge = left ? cardX + 160 : cardX
        const elbow = left ? 380 : 580
        const hubEdge = left ? hub.x : hub.x + 64
        const points: [number, number][] =
          rowY === cy ? [[edge, rowY], [hubEdge, rowY]] : [[edge, rowY], [elbow, rowY], [elbow, cy], [hubEdge, cy]]
        return (
          <div key={d.label}>
            <NodusPath points={points} tone={tones[i % 3]} delay={(i % 3) * 0.35 + (left ? 0 : 0.2)} />
            <At x={cardX} y={d.y} w={160}>
              <div className="shadow-aceternity flex items-center gap-3 rounded-md bg-card p-2.5">
                <span className="flex size-8 items-center justify-center rounded-md border border-border bg-card">
                  <d.icon className="size-4 text-gray-600" />
                </span>
                <span className="text-charcoal-700 text-sm font-medium">{d.label}</span>
              </div>
            </At>
          </div>
        )
      })}
      <At x={hub.x} y={hub.y}>
        <NodusHub />
      </At>
      <At x={hub.x - 9} y={hub.y + 84}>
        <NodusBadge>Connected</NodusBadge>
      </At>
      <At x={hub.x + 8} y={24}>
        <NodusTile>
          <LayoutGrid className="text-charcoal-700" />
        </NodusTile>
      </At>
      <NodusPath points={[[hub.x + 32, 72], [hub.x + 32, hub.y]]} tone="brand" delay={0.5} />
    </NodusStage>
  )
}

/* ------------------------------------------------------------------ */
/* Technology · orchestration core (replaces the wireframe tesseract)  */
/* ------------------------------------------------------------------ */

export function OrchestrationCoreScene({ settled = false, className }: { settled?: boolean; className?: string }) {
  const hub = { x: 128, y: 78 }
  const cy = hub.y + 32
  const tiles = [
    { icon: Bot, x: 16, y: 24, tone: "brand" as const },
    { icon: Plug, x: 256, y: 24, tone: "info" as const },
    { icon: ShieldCheck, x: 16, y: 148, tone: "warning" as const },
    { icon: FileText, x: 256, y: 148, tone: "info" as const },
  ]
  return (
    <div className={className}>
      <NodusStage width={320} height={230}>
        {tiles.map((t, i) => {
          const left = t.x < hub.x
          const ty = t.y + 24
          const tx = left ? t.x + 48 : t.x
          const ex = left ? 100 : 220
          return (
            <NodusPath
              key={i}
              points={[[tx, ty], [ex, ty], [ex, cy], [left ? hub.x : hub.x + 64, cy]]}
              tone={t.tone}
              delay={i * 0.35}
            />
          )
        })}
        {tiles.map((t, i) => (
          <At key={`t${i}`} x={t.x} y={t.y}>
            <NodusTile className={settled && i === 3 ? "border-brand/30 bg-[color:color-mix(in_srgb,var(--brand)_6%,var(--card))]" : undefined}>
              <t.icon className={settled && i === 3 ? "text-brand" : "text-charcoal-700"} />
            </NodusTile>
          </At>
        ))}
        <At x={hub.x} y={hub.y}>
          <NodusHub />
        </At>
        <At x={hub.x + 32} y={hub.y + 80} className="-translate-x-1/2">
          <NodusBadge tone={settled ? "brand" : "info"}>{settled ? "Verified" : "Coordinating"}</NodusBadge>
        </At>
      </NodusStage>
    </div>
  )
}
