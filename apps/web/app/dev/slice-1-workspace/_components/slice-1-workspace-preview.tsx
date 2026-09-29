"use client"

/**
 * Slice 1 preview — the production bridges, shells, provider, runtime status,
 * composition switch and inspector, driven by FIXTURE props.
 *
 * Internal /dev route (public, noindex). There is no useChat here and nothing is
 * sent anywhere: the composer is disabled and approve/reject only append to the
 * on-page event log. The mode routing below is a copy of AiWorkspace's switch so
 * the real bridges can be exercised without the core runtime; AiWorkspace itself
 * is unchanged.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { PageIntro } from "@/components/gravitre/page-intro"
import { GravitreAIFloatBridge } from "@/app/ai/_components/ai-workspace-float-bridge"
import { GravitreAIWorkspaceShellBridge } from "@/app/ai/_components/ai-workspace-shell-bridge"
import { GravitreAIMobileSheetBridge } from "@/app/ai/_components/ai-mobile-sheet-bridge"
import {
  GravitreAIWorkspaceProvider,
  useGravitreAIWorkspace,
} from "@/components/gravitre/ai-workspace-provider"
import { GravitreAIRuntimeStatus } from "@/components/gravitre/ai-runtime-status"
import {
  GravitreInspector,
  GravitreInspectorFields,
  GravitreInspectorNotice,
  GravitreInspectorSection,
  GRAVITRE_INSPECTOR_KINDS,
  GRAVITRE_INSPECTOR_KIND_LABEL,
  type GravitreInspectorKind,
} from "@/components/gravitre/inspector"
import { useGravitreMobileViewport } from "@/hooks/use-gravitre-mobile-viewport"
import { useWindowManagerPreference } from "@/hooks/use-window-manager-preference"
import { deriveGravitreHelperPresence } from "@/lib/gravitre-ai-presence"
import { toLegacyPresentationMode } from "@/lib/gravitre-ai-presentation"
import { deriveAiRuntimeState } from "@/lib/gravitre-ai-runtime-state"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { FIXTURE_PROPS, FIXTURE_SCENARIOS, type FixtureScenario } from "./slice-1-fixtures"

const FIXTURE_CONVERSATION_ID = "fixture-conv-slice1"
const noop = () => {}

function FixtureBanner() {
  return (
    <div
      role="note"
      className="sticky top-0 z-[60] border-b border-dashed border-[color:var(--g-warning)] bg-[color:var(--g-surface-1)] px-4 py-1.5 text-center font-mono text-[11px] uppercase tracking-wide text-[color:var(--g-warning)]"
    >
      Fixture preview · production components with fixture data · sending disabled · not a live conversation
    </div>
  )
}

function PreviewHost({
  scenario,
  onEvent,
}: {
  scenario: FixtureScenario
  onEvent: (row: string) => void
}) {
  const ws = useGravitreAIWorkspace()
  const isMobile = useGravitreMobileViewport()
  const fx = FIXTURE_PROPS[scenario]
  const [input, setInput] = useState("")

  const common = {
    presence: deriveGravitreHelperPresence({
      conversation: ws.conversation,
      approval: ws.approval,
      voice: ws.voice,
    }),
    messages: fx.messages,
    status: fx.status,
    isStreaming: fx.isStreaming,
    isBusy: fx.isBusy,
    showWaiting: fx.showWaiting,
    dialogueMode: fx.dialogueMode,
    pendingTask: fx.pendingTask,
    executionResult: fx.executionResult,
    canApprove: fx.canApprove,
    canContinueAfterStop: fx.canContinueAfterStop,
    onConfirmExecution: () => onEvent("fixture: Approve clicked — nothing executed"),
    onRejectExecution: () => onEvent("fixture: Reject clicked — nothing executed"),
    conversationId: FIXTURE_CONVERSATION_ID,
    conversationTitle: "Fixture conversation",
    input,
    onInputChange: setInput,
    onSubmit: noop,
    canSubmit: false,
    disabled: true,
    placeholder: "Fixture preview — sending disabled",
    voiceEntitled: false,
  }

  if (!ws.floatWorkspaceOpen) {
    return (
      <button
        type="button"
        onClick={ws.restoreFromHelper}
        data-slice1-preview-launcher=""
        className="fixed bottom-5 right-5 z-[85] flex items-center gap-2 rounded-full border border-dashed border-[color:var(--g-warning)] bg-[color:var(--g-surface-1)] px-3 py-2 text-xs shadow-[var(--np-shadow)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--g-brand)]/40"
        aria-label="Open AI Chat (fixture launcher)"
      >
        <span className="font-medium">Open AI Chat</span>
        <span className="font-mono text-[9px] uppercase text-[color:var(--g-warning)]">fixture launcher</span>
      </button>
    )
  }

  const legacy = toLegacyPresentationMode(ws.presentationMode)

  if (isMobile) {
    return (
      <GravitreAIMobileSheetBridge
        {...common}
        mode={legacy === "helper" ? "float" : legacy}
        onModeChange={(mode) => ws.setPresentationMode(mode)}
        onClose={ws.minimizeToHelper}
      />
    )
  }

  if (legacy === "expanded" || legacy === "fullscreen") {
    return (
      <GravitreAIWorkspaceShellBridge
        {...common}
        mode={legacy}
        onMinimizeToFloat={() => ws.setPresentationMode("float")}
        onEnterFullscreen={() => ws.setPresentationMode("fullscreen")}
        onExitFullscreen={() => ws.setPresentationMode("expanded")}
        onClose={ws.minimizeToHelper}
        leftPanelProps={{
          conversations: [],
          activeConversationId: FIXTURE_CONVERSATION_ID,
          onSelect: noop,
          onNew: noop,
          onDelete: noop,
          onArchive: noop,
          onRename: noop,
          onBulkDelete: noop,
          isOpen: false,
          onToggle: noop,
        }}
        leftCollapsed
        onToggleLeft={noop}
        rightPanelProps={{ pendingTask: fx.pendingTask ?? null, conversationId: FIXTURE_CONVERSATION_ID }}
        rightCollapsed
        onToggleRight={noop}
        liveActivityOpen={false}
        onToggleLiveActivity={noop}
      />
    )
  }

  return (
    <GravitreAIFloatBridge
      {...common}
      onClose={ws.minimizeToHelper}
      onExpand={() => ws.setPresentationMode("expanded")}
      onEnterFullscreen={() => ws.setPresentationMode("fullscreen")}
    />
  )
}

/** Proof panel: provider instance, messages reference and mode history. */
function IdentityPanel({ scenario, log }: { scenario: FixtureScenario; log: string[] }) {
  const ws = useGravitreAIWorkspace()
  const preference = useWindowManagerPreference()
  const firstInstance = useRef(ws.instanceId)
  const firstMessages = useRef(FIXTURE_PROPS[scenario].messages)
  const [modes, setModes] = useState<string[]>([])
  const mode = ws.floatWorkspaceOpen ? toLegacyPresentationMode(ws.presentationMode) : "helper"

  useEffect(() => {
    firstMessages.current = FIXTURE_PROPS[scenario].messages
  }, [scenario])
  useEffect(() => {
    setModes((rows) => (rows[0] === mode ? rows : [mode, ...rows].slice(0, 12)))
  }, [mode])

  const runtime = deriveAiRuntimeState(FIXTURE_PROPS[scenario])
  return (
    <section aria-label="Identity evidence" className="space-y-2 rounded-[var(--g-radius-card)] border border-[color:var(--g-border-default)] p-3 text-xs">
      <h2 className={TYPE.sectionTitle}>Identity across transitions</h2>
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 font-mono text-[11px]" data-slice1-identity="">
        <dt>provider instance</dt>
        {/* The id itself is random per render environment, so only the comparison is shown. */}
        <dd data-slice1-instance-stable={String(firstInstance.current === ws.instanceId)}>
          {firstInstance.current === ws.instanceId ? "unchanged since load" : "CHANGED"}
        </dd>
        <dt>conversation</dt>
        <dd>{FIXTURE_CONVERSATION_ID}</dd>
        <dt>messages ref</dt>
        <dd data-slice1-messages-stable={String(firstMessages.current === FIXTURE_PROPS[scenario].messages)}>
          {firstMessages.current === FIXTURE_PROPS[scenario].messages ? "same array" : "DIFFERENT"}
        </dd>
        <dt>window mode</dt>
        <dd data-slice1-mode={mode}>{mode}</dd>
        <dt>remembered</dt>
        <dd>{preference ?? "none (contextual default applies)"}</dd>
        <dt>derived runtime</dt>
        <dd>{runtime}</dd>
      </dl>
      <p className={TYPE.meta}>Mode history: {modes.join(" ← ")}</p>
      {log.length ? (
        <ol className="font-mono text-[10px] text-[color:var(--g-text-muted)]" aria-label="Fixture event log">
          {log.map((row, i) => (
            <li key={`${i}-${row}`}>{row}</li>
          ))}
        </ol>
      ) : null}
    </section>
  )
}

function InspectorDemo() {
  const [kind, setKind] = useState<GravitreInspectorKind | null>(null)
  return (
    <section className="space-y-2" aria-label="Shared inspector">
      <h2 className={TYPE.sectionTitle}>Shared inspector</h2>
      <div className="flex flex-wrap gap-1.5">
        {GRAVITRE_INSPECTOR_KINDS.map((k) => (
          <Button key={k} type="button" size="sm" variant="outline" onClick={() => setKind(k)}>
            {GRAVITRE_INSPECTOR_KIND_LABEL[k]}
          </Button>
        ))}
      </div>
      <GravitreInspector
        open={kind !== null}
        onOpenChange={(open) => !open && setKind(null)}
        kind={kind ?? "entity"}
        title="Acme renewal (fixture)"
        description="Fixture content — the inspector renders whatever its caller passes."
      >
        {kind === "error" ? (
          <GravitreInspectorNotice tone="error" title="Contact was not created (fixture)">
            Fixture failure detail.
          </GravitreInspectorNotice>
        ) : kind === "approval" ? (
          <GravitreInspectorNotice tone="approval" title="Waiting on an approver (fixture)">
            Approval happens in the conversation; this drawer only explains it.
          </GravitreInspectorNotice>
        ) : null}
        <GravitreInspectorSection title="Fields">
          <GravitreInspectorFields
            fields={[
              { label: "Source", value: "Fixture" },
              { label: "Reference", value: "fixture-ref-001", mono: true },
            ]}
          />
        </GravitreInspectorSection>
      </GravitreInspector>
    </section>
  )
}

export function Slice1WorkspacePreview() {
  const [dark, setDark] = useState(false)
  const [scenario, setScenario] = useState<FixtureScenario>("idle")
  const [log, setLog] = useState<string[]>([])
  const onEvent = useCallback((row: string) => setLog((rows) => [row, ...rows].slice(0, 6)), [])

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark)
    return () => document.documentElement.classList.remove("dark")
  }, [dark])

  const scenarioButtons = useMemo(
    () =>
      FIXTURE_SCENARIOS.map((s) => (
        <Button
          key={s}
          type="button"
          size="sm"
          variant={scenario === s ? "secondary" : "ghost"}
          aria-pressed={scenario === s}
          onClick={() => setScenario(s)}
        >
          {s.replace("_", " ")}
        </Button>
      )),
    [scenario],
  )

  return (
    <GravitreAIWorkspaceProvider>
      <FixtureBanner />
      <div className="min-h-screen bg-[color:var(--g-canvas)] text-[color:var(--g-text-primary)]">
        <div className="mx-auto max-w-5xl space-y-6 px-4 py-6 sm:px-6">
          <PageIntro
            family="operating"
            eyebrow="Phase 8 · Slice 1 · internal"
            title="AI workspace presentation"
            lead="Real bridges, shells and provider with fixture props. Open the chat, then dock, expand, go fullscreen, minimize and restore."
            actions={
              <Button type="button" size="sm" variant="outline" aria-pressed={dark} onClick={() => setDark((v) => !v)}>
                {dark ? "Dark" : "Light"}
              </Button>
            }
          />

          <section className="space-y-2" aria-label="Runtime scenario">
            <h2 className={TYPE.sectionTitle}>Runtime scenario (fixture props)</h2>
            <div className="flex flex-wrap gap-1" role="group" aria-label="Runtime scenario">
              {scenarioButtons}
            </div>
            {scenario === "resumed" ? (
              <div className="rounded-[var(--g-radius-card)] border border-dashed border-[color:var(--g-warning)]">
                <GravitreAIRuntimeStatus state="resumed" fixture className="border-b-0" />
                <p className={cn(TYPE.meta, "px-3 pb-2")}>
                  No production signal reports a resumed run, so the live workspace never shows this state. Rendered here
                  as fixture vocabulary only.
                </p>
              </div>
            ) : null}
          </section>

          <section className="space-y-2" aria-label="Page content">
            <h2 className={TYPE.sectionTitle}>Page content (must stay usable beside the dock)</h2>
            <label className="block max-w-sm space-y-1 text-xs">
              <span className={TYPE.meta}>Page field</span>
              <Input placeholder="Type here while the workspace is docked" />
            </label>
          </section>

          <IdentityPanel scenario={scenario} log={log} />
          <InspectorDemo />
        </div>
      </div>
      <PreviewHost scenario={scenario} onEvent={onEvent} />
    </GravitreAIWorkspaceProvider>
  )
}
