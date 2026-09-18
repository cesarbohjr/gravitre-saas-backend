"use client"

import {
  NucleoChat,
  NucleoCommand,
  NucleoHistory,
  NucleoMic,
  NucleoMinimize,
  NucleoRun,
  NucleoSend,
  NucleoSuccess,
  NucleoVoice,
} from "@/components/icons/nucleo/semantic"
import { cn } from "@/lib/utils"
import { TYPE } from "@/lib/design-system"

export type AiScene =
  | "empty"
  | "loading"
  | "error"
  | "compact-conversation"
  | "compact-voice-listen"
  | "compact-voice-speak"
  | "expanded-conversation"
  | "expanded-history"
  | "expanded-work"
  | "expanded-tool"
  | "fullscreen-work"
  | "fullscreen-inspect"
  | "mobile-conversation"
  | "mobile-work"
  | "mobile-inspect"

export function SelectedAiCommandOs({ scene }: { scene: AiScene }) {

  if (scene === "empty") {
    return (
      <Frame testId="ai-empty" className="mx-auto max-w-[420px]">
        <Header compact />
        <div className="flex flex-1 flex-col items-center justify-center px-6 text-center">
          <NucleoCommand size={20} className="text-[color:var(--g-text-muted)]" />
          <p className={cn(TYPE.pageLead, "mt-3")}>What should Gravitre do?</p>
        </div>
        <Composer />
      </Frame>
    )
  }

  if (scene === "loading") {
    return (
      <Frame testId="ai-loading" className="mx-auto max-w-[420px]">
        <Header compact />
        <div className="flex flex-1 items-center justify-center">
          <p className={TYPE.meta}>Retrieving connector health…</p>
        </div>
        <Composer />
      </Frame>
    )
  }

  if (scene === "error") {
    return (
      <Frame testId="ai-error" className="mx-auto max-w-[420px]">
        <Header compact />
        <div className="flex flex-1 flex-col justify-center px-4">
          <p className="text-sm text-[color:var(--g-danger)]">HubSpot health check failed.</p>
          <p className={TYPE.meta}>Retry from the composer. Conversation is still here.</p>
        </div>
        <Composer />
      </Frame>
    )
  }

  if (scene.startsWith("compact") || scene === "mobile-conversation") {
    const voice =
      scene === "compact-voice-listen" ? "listening" : scene === "compact-voice-speak" ? "speaking" : null
    return (
      <Frame
        testId={scene}
        className={cn("mx-auto", scene.startsWith("mobile") ? "max-w-[390px]" : "max-w-[420px]")}
      >
        <Header compact />
        <Thread tool={false} />
        {voice && (
          <p className={cn(TYPE.meta, "px-3 py-1")} data-voice={voice}>
            <NucleoVoice size={16} className="mr-1 inline" />
            {voice === "listening" ? "Listening" : "Speaking"}
          </p>
        )}
        <Composer voice={voice} />
      </Frame>
    )
  }

  if (scene === "mobile-work" || scene === "mobile-inspect") {
    return (
      <Frame testId={scene} className="relative mx-auto max-h-[720px] max-w-[390px]">
        <Header compact />
        <Thread tool={false} />
        <Composer />
        <div
          className="absolute inset-x-0 bottom-0 top-12 border-t border-[color:var(--g-border-default)] bg-[color:var(--g-canvas)] p-4"
          style={{ boxShadow: "var(--g-shadow-elevated)" }}
        >
          <button type="button" className="text-xs text-[color:var(--g-text-muted)]">
            Back to conversation
          </button>
          {scene === "mobile-work" ? <WorkCanvas /> : <Inspector />}
        </div>
      </Frame>
    )
  }

  const history = scene === "expanded-history"
  const work = scene.includes("work") || scene.includes("tool") || scene.includes("inspect")
  const inspect = scene.includes("inspect")
  const tool = scene.includes("tool")
  const full = scene.startsWith("fullscreen")

  return (
    <Frame testId={scene} className={cn("mx-auto", full ? "max-w-[1100px]" : "max-w-[960px]")}>
      <Header />
      <p className={cn(TYPE.eyebrow, "border-b border-[color:var(--g-border-subtle)] px-3 py-1.5")}>
        Conversation → Command → Work → Inspect
      </p>
      <div className={cn("grid min-h-[420px] flex-1", work && "md:grid-cols-[minmax(260px,1fr)_1.4fr]", inspect && full && "lg:grid-cols-[minmax(240px,0.9fr)_1.4fr_280px]")}>
        <div className="flex min-h-0 flex-col border-[color:var(--g-border-default)] md:border-r">
          {history && (
            <aside className="border-b border-[color:var(--g-border-default)] px-3 py-2">
              <p className={TYPE.eyebrow}>History</p>
              <p className={TYPE.meta}>Connector health check</p>
            </aside>
          )}
          <Thread tool={tool} />
          <Composer />
        </div>
        {work && (
          <div className="min-h-[200px] border-l border-[color:var(--g-border-default)] p-4">
            <WorkCanvas executing={tool} />
          </div>
        )}
        {inspect && <Inspector />}
      </div>
    </Frame>
  )
}

function Frame({
  children,
  className,
  testId,
}: {
  children: React.ReactNode
  className?: string
  testId: string
}) {
  return (
    <div
      data-review-surface="ai"
      data-review-scene={testId}
      className={cn(
        "flex min-h-[520px] flex-col overflow-hidden border border-[color:var(--g-border-default)] bg-[color:var(--g-canvas)]",
        className,
      )}
    >
      {children}
    </div>
  )
}

function Header({ compact }: { compact?: boolean }) {
  return (
    <header className="flex items-center justify-between border-b border-[color:var(--g-border-default)] px-3 py-2">
      <span className="inline-flex items-center gap-2 text-sm font-medium">
        <NucleoChat size={compact ? 16 : 16} />
        Gravitre
      </span>
      <span className="inline-flex items-center gap-2 text-[color:var(--g-text-muted)]">
        <NucleoHistory size={14} />
        <NucleoMinimize size={14} />
      </span>
    </header>
  )
}

function Thread({ tool }: { tool: boolean }) {
  return (
    <div className="min-h-0 flex-1 space-y-3 overflow-auto px-3 py-3 text-sm">
      <p className="text-[color:var(--g-text-muted)]">Which connectors need attention?</p>
      <p>Checking connector health across the org.</p>
      {tool && (
        <p className="inline-flex items-center gap-2 text-[color:var(--g-signal)]">
          <NucleoRun size={14} />
          connectors.list_health · running
        </p>
      )}
      {!tool && <p>HubSpot token expires in 2 days. The rest are healthy.</p>}
    </div>
  )
}

function Composer({ voice }: { voice?: "listening" | "speaking" | null }) {
  return (
    <div className="flex items-center gap-2 border-t border-[color:var(--g-border-default)] px-3 py-2">
      <NucleoMic
        size={20}
        className={voice ? "text-[color:var(--g-brand)]" : "text-[color:var(--g-text-muted)]"}
      />
      <span className="flex-1 text-sm text-[color:var(--g-text-muted)]">
        {voice === "listening" ? "Listening…" : voice === "speaking" ? "Speaking…" : "Ask Gravitre"}
      </span>
      <NucleoSend size={20} />
    </div>
  )
}

function WorkCanvas({ executing }: { executing?: boolean }) {
  return (
    <div>
      <p className={TYPE.eyebrow}>{executing ? "EXECUTE" : "Artifact"}</p>
      <h3 className={cn(TYPE.sectionTitle, "mt-2")}>Connector health</h3>
      <ul className="mt-3 space-y-2 text-sm">
        <li className="flex justify-between border-b border-[color:var(--g-border-subtle)] py-2">
          HubSpot <span className="text-[color:var(--g-approval)]">token 2d</span>
        </li>
        <li className="flex justify-between border-b border-[color:var(--g-border-subtle)] py-2">
          Slack <span className="text-[color:var(--g-brand)]">healthy</span>
        </li>
      </ul>
    </div>
  )
}

function Inspector() {
  return (
    <aside className="border-t border-[color:var(--g-border-default)] p-3 text-sm lg:border-t-0 lg:border-l">
      <p className={TYPE.eyebrow}>Inspect</p>
      <p className="mt-2">HubSpot OAuth · last refresh 4m ago</p>
      <p className={cn(TYPE.meta, "mt-2")}>Provenance: live connector status. Not a guess.</p>
      <p className="mt-3 inline-flex items-center gap-1 text-[color:var(--g-brand)]">
        <NucleoSuccess size={14} />
        Evidence attached
      </p>
    </aside>
  )
}
