"use client"

import { useRef, type ReactNode, type RefObject } from "react"
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"

/**
 * Shared drawer / inspector (3.0 Plus Slice 1).
 *
 * One chrome for contextual detail across the product: entity, evidence,
 * artifact, approval, task status, error, and advanced configuration. Built on
 * the Radix Dialog sheet, which provides the focus trap, Escape to close and
 * focus return to the opener. Props only — the caller owns every value shown and
 * every action taken; this component holds no business state.
 */

export const GRAVITRE_INSPECTOR_KINDS = [
  "entity",
  "evidence",
  "artifact",
  "approval",
  "task",
  "error",
  "configuration",
] as const
export type GravitreInspectorKind = (typeof GRAVITRE_INSPECTOR_KINDS)[number]

export const GRAVITRE_INSPECTOR_KIND_LABEL: Record<GravitreInspectorKind, string> = {
  entity: "Details",
  evidence: "Evidence",
  artifact: "Artifact",
  approval: "Approval",
  task: "Task status",
  error: "Error",
  configuration: "Advanced configuration",
}

export function GravitreInspector({
  open,
  onOpenChange,
  kind,
  title,
  description,
  children,
  footer,
  returnFocusRef,
  side = "right",
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  kind: GravitreInspectorKind
  title: string
  description?: string
  children: ReactNode
  footer?: ReactNode
  /** Where focus lands on close when the opener is not the element that had focus. */
  returnFocusRef?: RefObject<HTMLElement | null>
  side?: "right" | "bottom"
}) {
  // Radix only restores focus to a <SheetTrigger>; controlled inspectors opened
  // from arbitrary buttons would otherwise drop focus to <body> on close.
  const openerRef = useRef<HTMLElement | null>(null)
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side={side}
        data-gravitre-inspector={kind}
        className={cn(
          "gap-0 bg-[color:var(--g-surface-1)] p-0",
          side === "right" ? "w-full sm:max-w-md" : "max-h-[85dvh]",
        )}
        onOpenAutoFocus={() => {
          const active = document.activeElement
          openerRef.current = active instanceof HTMLElement && active !== document.body ? active : null
        }}
        onCloseAutoFocus={(event) => {
          const target = returnFocusRef?.current ?? openerRef.current
          if (!target || !target.isConnected) return
          event.preventDefault()
          target.focus()
        }}
      >
        <SheetHeader className="border-b border-divide px-4 py-3 pr-10">
          <p className={TYPE.eyebrow}>{GRAVITRE_INSPECTOR_KIND_LABEL[kind]}</p>
          <SheetTitle className="text-sm font-semibold text-[color:var(--g-text-primary)]">{title}</SheetTitle>
          {description ? (
            <SheetDescription className="text-xs text-[color:var(--g-text-muted)]">{description}</SheetDescription>
          ) : (
            <SheetDescription className="sr-only">{GRAVITRE_INSPECTOR_KIND_LABEL[kind]} for {title}</SheetDescription>
          )}
        </SheetHeader>
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-4">{children}</div>
        {footer ? <SheetFooter className="border-t border-divide px-4 py-3">{footer}</SheetFooter> : null}
      </SheetContent>
    </Sheet>
  )
}

export function GravitreInspectorSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-2">
      <h3 className="text-[11px] font-semibold uppercase tracking-wide text-[color:var(--g-text-muted)]">{title}</h3>
      {children}
    </section>
  )
}

export function GravitreInspectorFields({
  fields,
}: {
  fields: ReadonlyArray<{ label: string; value: ReactNode; mono?: boolean }>
}) {
  return (
    <dl className="grid grid-cols-[minmax(96px,auto)_1fr] gap-x-3 gap-y-1.5 text-xs">
      {fields.map((field) => (
        <div key={field.label} className="contents">
          <dt className="text-[color:var(--g-text-muted)]">{field.label}</dt>
          <dd className={cn("min-w-0 break-words text-[color:var(--g-text-primary)]", field.mono && "font-mono text-[11px]")}>
            {field.value}
          </dd>
        </div>
      ))}
    </dl>
  )
}

const NOTICE_TONE = {
  info: "border-[color:var(--g-border-default)] bg-[color:var(--g-surface-2)]",
  approval: "border-[color:var(--g-warning)]/40 bg-[color:var(--g-warning)]/5",
  error: "border-[color:var(--g-danger)]/40 bg-[color:var(--g-danger)]/5",
} as const

export function GravitreInspectorNotice({
  tone,
  title,
  children,
}: {
  tone: keyof typeof NOTICE_TONE
  title: string
  children?: ReactNode
}) {
  return (
    <div role={tone === "error" ? "alert" : undefined} className={cn("rounded-[var(--g-radius-card)] border px-3 py-2.5 text-xs", NOTICE_TONE[tone])}>
      <p className="font-medium text-[color:var(--g-text-primary)]">{title}</p>
      {children ? <div className="mt-1 text-[color:var(--g-text-secondary)]">{children}</div> : null}
    </div>
  )
}
