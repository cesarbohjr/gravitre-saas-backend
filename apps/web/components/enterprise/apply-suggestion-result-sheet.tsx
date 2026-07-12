"use client"

import Link from "next/link"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import type { IntegrationSuggestionApplyResponse } from "@/types/api"
import { ArrowRight, CheckCircle2, ExternalLink, Lightbulb, ShieldAlert } from "lucide-react"

export function ApplySuggestionResultSheet({
  result,
  open,
  onOpenChange,
  onContinue,
  onConfirm,
  confirming = false,
}: {
  result: IntegrationSuggestionApplyResponse | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onContinue: () => void
  onConfirm?: () => void
  confirming?: boolean
}) {
  const summary = result?.applySummary
  const entities = summary?.entities ?? []
  const highlights = summary?.evidenceHighlights ?? []
  const needsApproval = Boolean(result?.requiresApproval)

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="flex w-full flex-col sm:max-w-md">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            {needsApproval ? (
              <ShieldAlert className="h-5 w-5 text-warning" aria-hidden />
            ) : (
              <CheckCircle2 className="h-5 w-5 text-success" aria-hidden />
            )}
            {needsApproval ? "Approval required" : "Recommendation applied"}
          </SheetTitle>
          <SheetDescription>
            {needsApproval
              ? "This write needs confirmation — same gate as chat connector / platform writes."
              : (summary?.title ??
                result?.suggestion.title ??
                "Changes were provisioned in your org.")}
          </SheetDescription>
        </SheetHeader>

        <div className="flex-1 space-y-4 overflow-y-auto px-4">
          {summary?.suggestionType ? (
            <Badge variant="outline" className="capitalize">
              {summary.suggestionType.replace(/_/g, " ")}
            </Badge>
          ) : null}

          {needsApproval && result?.pendingTask ? (
            <div className="space-y-2 rounded-lg border border-warning/30 bg-warning/5 p-3 text-sm">
              <p className="font-medium">
                {String(result.pendingTask.params?.invoke_action ?? result.pendingTask.type ?? "write")}
              </p>
              <p className="text-muted-foreground">
                Reply confirm to run this action. No durable write happens until you approve.
              </p>
            </div>
          ) : null}

          {entities.length > 0 ? (
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Created / updated
              </p>
              <ul className="space-y-2">
                {entities.map((entity) => (
                  <li
                    key={`${entity.type}-${entity.id}`}
                    className="flex items-center justify-between gap-2 rounded-lg border border-border/70 px-3 py-2 text-sm"
                  >
                    <span>
                      <span className="font-medium capitalize">{entity.type}</span>
                      {entity.label ? (
                        <span className="text-muted-foreground"> · {entity.label}</span>
                      ) : null}
                    </span>
                    {entity.type === "workflow" ? (
                      <Button size="sm" variant="ghost" asChild>
                        <Link href={`/workflows/${entity.id}/builder`}>
                          Open
                          <ExternalLink className="ml-1 h-3.5 w-3.5" />
                        </Link>
                      </Button>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {highlights.length > 0 ? (
            <div className="space-y-2 rounded-lg border border-primary/20 bg-primary/5 p-3">
              <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-primary">
                <Lightbulb className="h-3.5 w-3.5" aria-hidden />
                Evidence
              </p>
              <ul className="space-y-1 text-sm text-muted-foreground">
                {highlights.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>

        <SheetFooter className="border-t pt-4">
          {needsApproval ? (
            <>
              <Button variant="outline" onClick={() => onOpenChange(false)} disabled={confirming}>
                Cancel
              </Button>
              <Button onClick={() => onConfirm?.()} disabled={confirming || !onConfirm}>
                {confirming ? "Confirming…" : "Confirm write"}
              </Button>
            </>
          ) : (
            <>
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                Stay here
              </Button>
              <Button onClick={onContinue}>
                Continue
                <ArrowRight className="ml-1.5 h-4 w-4" />
              </Button>
            </>
          )}
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
