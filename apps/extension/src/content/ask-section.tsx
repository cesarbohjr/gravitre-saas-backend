import { ArrowUpRight } from "lucide-react"

import { BrandLoader } from "@/components/brand-loader"
import { Button, SectionLabel } from "@/components/ui"
import { cn } from "@/lib/cn"

/**
 * Quick question box (Part D).
 *
 * Deliberately framed as a shortcut, not a replacement for the main chat: short
 * answers land here, and anything larger hands off to the full thread rather
 * than pretending a 380px panel is a good place to hold a conversation.
 */
export function AskSection({
  value,
  onChange,
  onAsk,
  onHandoff,
  busy,
  answer,
  needsHandoff,
  canHandoff,
}: {
  value: string
  onChange: (v: string) => void
  onAsk: () => void
  onHandoff: () => void
  busy: boolean
  answer?: string
  needsHandoff?: boolean
  canHandoff: boolean
}) {
  return (
    <div>
      <SectionLabel>Ask about this page</SectionLabel>

      <textarea
        rows={2}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          // Enter submits, Shift+Enter newlines. `isComposing` (and Safari's
          // unreliable 229) guard CJK IME confirmation from firing a request.
          if (
            e.key === "Enter" &&
            !e.shiftKey &&
            !e.nativeEvent.isComposing &&
            e.keyCode !== 229
          ) {
            e.preventDefault()
            if (value.trim() && !busy) onAsk()
          }
        }}
        placeholder="Quick question — this page is included as context"
        className={cn(
          "mt-1.5 w-full resize-none rounded-lg border border-border bg-background px-2.5 py-2",
          "text-[12px] leading-relaxed text-foreground placeholder:text-muted-foreground",
          "outline-none focus-visible:ring-2 focus-visible:ring-ring",
        )}
      />

      {busy && (
        <div className="mt-2 flex items-center gap-2">
          <BrandLoader size={14} />
          <span className="text-[12px] text-muted-foreground">Thinking…</span>
        </div>
      )}

      {!busy && answer && (
        <p className="gvt-animate-row mt-2 whitespace-pre-wrap rounded-lg border border-border bg-secondary/40 px-2.5 py-2 text-[12px] leading-relaxed text-foreground">
          {answer}
        </p>
      )}

      {!busy && needsHandoff && (
        <p className="mt-1.5 text-[11px] leading-relaxed text-muted-foreground">
          This needs the full chat — continuing keeps the same thread.
        </p>
      )}

      <div className="mt-2 flex items-center gap-2">
        <Button
          variant="secondary"
          size="sm"
          onClick={onAsk}
          disabled={!value.trim() || busy}
          className="flex-1"
        >
          Ask
        </Button>
        {canHandoff && (
          <Button
            variant={needsHandoff ? "primary" : "ghost"}
            size="sm"
            onClick={onHandoff}
          >
            Continue in Gravitre
            <ArrowUpRight aria-hidden="true" className="h-3 w-3" />
          </Button>
        )}
      </div>
    </div>
  )
}
