"use client"

/**
 * Design-review comp for the shared stateful assistant avatar.
 *
 * Two things this proves, both of which CI cannot:
 *
 *  1. Every avatar state renders. The four states cannot coexist in one live
 *     conversation, so they are driven directly here.
 *  2. Part C consistency — three distinct chat surfaces (default Gravitre, and
 *     two different named agents) render through the SAME real ChatTranscript,
 *     side by side, so any difference beyond identity is visible rather than
 *     asserted. That side-by-side is the whole point: the regression this fixes
 *     was invisible until the two surfaces were put next to each other.
 *
 * The transcript is the real shipped component with real message shapes, so this
 * judges production code. Capture-only: the parent /e2e/shots layout 404s this
 * in production.
 */

import type { UIMessage } from "ai"

import { ChatTranscript } from "@/components/gravitre/assistant/chat-transcript"
import { GravitreChatAvatar } from "@/components/gravitre/assistant/gravitre-chat-avatar"
import type { AgentIdentityInput } from "@/lib/agent-identity"

/**
 * Two deliberately different identities, to prove color/icon really vary.
 *
 * `icon` and `avatarColor` MUST be members of AGENT_ICON_IDS /
 * AGENT_AVATAR_COLOR_IDS — an unrecognised value silently falls back to a
 * suggested default, which would render two near-identical avatars and make this
 * comparison prove nothing. The colors are full Tailwind classes, not bare names.
 */
const MARKETING_AGENT: AgentIdentityInput = {
  name: "Marketing Analyst",
  role: "Marketing Analyst",
  department: "Marketing",
  icon: "megaphone",
  avatarColor: "bg-purple-500",
}

const FINANCE_AGENT: AgentIdentityInput = {
  name: "Finance Controller",
  role: "Finance Controller",
  department: "Finance",
  icon: "pie-chart",
  avatarColor: "bg-amber-500",
}

function textMessage(id: string, role: "user" | "assistant", text: string): UIMessage {
  return { id, role, parts: [{ type: "text", text }] } as UIMessage
}

/**
 * An assistant message with a tool call still in flight (no output), which is the
 * real signal the transcript maps to the `searching` state. Built as the real
 * part shape rather than a flag, so the harness exercises the same code path a
 * live tool call does.
 */
function searchingMessage(id: string): UIMessage {
  return {
    id,
    role: "assistant",
    parts: [
      { type: "text", text: "Checking the latest figures for you." },
      {
        type: "tool-web_search",
        toolCallId: `${id}-call`,
        toolName: "web_search",
        state: "input-available",
        input: { query: "q3 pipeline" },
      },
    ],
  } as unknown as UIMessage
}

const THREAD: UIMessage[] = [
  textMessage("u1", "user", "How did we do last quarter?"),
  textMessage("a1", "assistant", "Revenue came in at $2.4M, up 12% quarter over quarter."),
]

function Surface({
  title,
  note,
  children,
}: {
  title: string
  note: string
  children: React.ReactNode
}) {
  return (
    <section className="flex min-w-0 flex-1 flex-col gap-2">
      <header className="flex flex-col gap-0.5">
        <h2 className="text-sm font-semibold text-foreground">{title}</h2>
        <p className="text-xs text-muted-foreground">{note}</p>
      </header>
      <div className="rounded-lg border border-border bg-card p-3">{children}</div>
    </section>
  )
}

function StateRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2">
      {children}
      <span className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</span>
    </div>
  )
}

export default function AvatarStatesShotPage() {
  return (
    <main className="flex flex-col gap-8 p-6" data-testid="avatar-states-root">
      <header className="flex flex-col gap-1">
        <h1 className="text-base font-semibold text-foreground">Assistant avatar — states and surfaces</h1>
        <p className="text-xs text-muted-foreground">
          One shared component. Identity varies; structure and motion do not.
        </p>
      </header>

      {/* ── Every state, default identity and named identity ─────────────── */}
      <section className="flex flex-col gap-3" data-testid="avatar-state-matrix">
        <h2 className="text-sm font-semibold text-foreground">All four states</h2>
        <div className="flex flex-col gap-5">
          <div className="flex flex-col gap-2">
            <p className="text-xs text-muted-foreground">Default Gravitre assistant (main chat)</p>
            <div className="flex flex-wrap gap-6" data-testid="states-default">
              <StateRow label="idle">
                <GravitreChatAvatar state="idle" />
              </StateRow>
              <StateRow label="thinking">
                <GravitreChatAvatar state="thinking" />
              </StateRow>
              <StateRow label="searching">
                <GravitreChatAvatar state="searching" />
              </StateRow>
              <StateRow label="speaking">
                <GravitreChatAvatar state="speaking" />
              </StateRow>
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <p className="text-xs text-muted-foreground">
              Named agent — same states, agent&apos;s own icon and color retained
            </p>
            <div className="flex flex-wrap gap-6" data-testid="states-named">
              <StateRow label="idle">
                <GravitreChatAvatar state="idle" agent={MARKETING_AGENT} />
              </StateRow>
              <StateRow label="thinking">
                <GravitreChatAvatar state="thinking" agent={MARKETING_AGENT} />
              </StateRow>
              <StateRow label="searching">
                <GravitreChatAvatar state="searching" agent={MARKETING_AGENT} />
              </StateRow>
              <StateRow label="speaking">
                <GravitreChatAvatar state="speaking" agent={MARKETING_AGENT} />
              </StateRow>
            </div>
          </div>
        </div>
      </section>

      {/* ── Part C: three real surfaces, side by side ────────────────────── */}
      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold text-foreground">
          Three chat surfaces — real ChatTranscript, thinking state
        </h2>
        <div className="flex flex-col gap-6 lg:flex-row" data-testid="surface-comparison">
          <Surface title="Main chat" note="No agent — base Gravitre mark">
            <ChatTranscript messages={THREAD} showWaiting />
          </Surface>
          <Surface title="Marketing agent" note="Purple identity + megaphone icon">
            <ChatTranscript
              messages={THREAD}
              showWaiting
              assistantLabel={MARKETING_AGENT.name!}
              assistantAgent={MARKETING_AGENT}
            />
          </Surface>
          <Surface title="Finance agent" note="Amber identity + pie-chart icon">
            <ChatTranscript
              messages={THREAD}
              showWaiting
              assistantLabel={FINANCE_AGENT.name!}
              assistantAgent={FINANCE_AGENT}
            />
          </Surface>
        </div>
      </section>

      {/* ── Searching driven by a real in-flight tool call ───────────────── */}
      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold text-foreground">
          Searching — from a real in-flight tool call, not a flag
        </h2>
        <div className="rounded-lg border border-border bg-card p-3" data-testid="searching-surface">
          <ChatTranscript
            messages={[textMessage("u2", "user", "What is our Q3 pipeline?"), searchingMessage("a2")]}
            assistantLabel={FINANCE_AGENT.name!}
            assistantAgent={FINANCE_AGENT}
          />
        </div>
      </section>
    </main>
  )
}
