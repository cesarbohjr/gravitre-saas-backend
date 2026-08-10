"use client"

/**
 * Design-review comp for the shared stateful assistant avatar.
 *
 * Proves every avatar state renders, and that main `/ai` vs department agent
 * chats share the SAME Gravitre mark disc — only the label (persona / agent
 * name) differs. Capture-only: parent /e2e/shots layout 404s this in production.
 */

import type { UIMessage } from "ai"

import { ChatTranscript } from "@/components/gravitre/assistant/chat-transcript"
import { GravitreChatAvatar } from "@/components/gravitre/assistant/gravitre-chat-avatar"

const MARKETING_LABEL = "Marketing Analyst"
const FINANCE_LABEL = "Finance Controller"

function textMessage(id: string, role: "user" | "assistant", text: string): UIMessage {
  return {
    id,
    role,
    parts: [{ type: "text", text }],
  } as UIMessage
}

function searchingMessage(id: string): UIMessage {
  return {
    id,
    role: "assistant",
    parts: [
      { type: "text", text: "Looking that up…" },
      {
        type: "tool-invocation",
        toolInvocation: {
          state: "call",
          toolCallId: "t1",
          toolName: "search",
          args: {},
        },
      },
    ],
  } as UIMessage
}

const THREAD: UIMessage[] = [
  textMessage("u1", "user", "Can you help with this?"),
  textMessage("a1", "assistant", "Of course — what do you need?"),
]

function StateRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-1.5">
      <span className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</span>
      {children}
    </div>
  )
}

function Surface({
  title,
  note,
  children,
}: {
  title: string
  note?: string
  children: React.ReactNode
}) {
  return (
    <div className="min-w-0 flex-1 rounded-lg border border-border bg-card p-3">
      <h3 className="text-xs font-semibold text-foreground">{title}</h3>
      {note ? <p className="mb-2 text-[11px] text-muted-foreground">{note}</p> : null}
      {children}
    </div>
  )
}

export default function AvatarStatesShot() {
  return (
    <main className="min-h-screen bg-background px-8 py-10">
      <header className="mb-8 flex flex-col gap-1">
        <h1 className="text-lg font-semibold tracking-tight text-foreground">
          Assistant avatar — design review
        </h1>
        <p className="text-sm text-muted-foreground">
          One Gravitre mark + processing states on every chat. Labels carry the
          persona / agent name.
        </p>
      </header>

      <section className="mb-10 flex flex-col gap-3" data-testid="avatar-state-matrix">
        <h2 className="text-sm font-semibold text-foreground">All four states</h2>
        <div className="flex flex-wrap gap-6" data-testid="states-default">
          <StateRow label="idle">
            <GravitreChatAvatar state="idle" />
          </StateRow>
          <StateRow label="thinking">
            <GravitreChatAvatar state="thinking" title="Gravitre is thinking" />
          </StateRow>
          <StateRow label="searching">
            <GravitreChatAvatar state="searching" title="Gravitre is searching" />
          </StateRow>
          <StateRow label="speaking">
            <GravitreChatAvatar state="speaking" />
          </StateRow>
        </div>
      </section>

      <section className="mb-10 flex flex-col gap-3">
        <h2 className="text-sm font-semibold text-foreground">
          Three chat surfaces — same mark, different labels
        </h2>
        <div className="flex flex-col gap-6 lg:flex-row" data-testid="surface-comparison">
          <Surface title="Main chat" note="Friendly Assistant label + Gravitre mark">
            <ChatTranscript messages={THREAD} showWaiting assistantLabel="Friendly Assistant" />
          </Surface>
          <Surface title="Marketing agent" note="Same mark; marketing name only">
            <ChatTranscript
              messages={THREAD}
              showWaiting
              assistantLabel={MARKETING_LABEL}
              waitingLabel={`${MARKETING_LABEL} is thinking…`}
            />
          </Surface>
          <Surface title="Finance agent" note="Same mark; finance name only">
            <ChatTranscript
              messages={THREAD}
              showWaiting
              assistantLabel={FINANCE_LABEL}
              waitingLabel={`${FINANCE_LABEL} is thinking…`}
            />
          </Surface>
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold text-foreground">
          Searching — from a real in-flight tool call
        </h2>
        <div className="rounded-lg border border-border bg-card p-3" data-testid="searching-surface">
          <ChatTranscript
            messages={[textMessage("u2", "user", "What is our Q3 pipeline?"), searchingMessage("a2")]}
            assistantLabel={FINANCE_LABEL}
          />
        </div>
      </section>
    </main>
  )
}
