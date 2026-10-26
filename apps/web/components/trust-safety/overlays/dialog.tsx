"use client"

import type { ReactNode } from "react"
import * as DialogPrimitive from "@radix-ui/react-dialog"
import { X } from "lucide-react"
import "./overlays.css"

/**
 * A form dialog in the Trust & Safety shell ("Edit rule" in the design): title
 * and one line of help beside a close button, labelled fields, then a footer
 * with Cancel and the primary action. Centered on a 48% ink scrim; a bottom
 * sheet on phones. Only the Trust & Safety page opens these.
 */
export function TrustSafetyDialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: ReactNode
  children: ReactNode
  footer: ReactNode
}) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="tso-scrim" />
        <DialogPrimitive.Content className="tso-dialog form">
          <div className="tso-dialog-head">
            <div>
              <DialogPrimitive.Title className="tso-dialog-title">{title}</DialogPrimitive.Title>
              {description ? (
                <DialogPrimitive.Description className="tso-dialog-desc">{description}</DialogPrimitive.Description>
              ) : (
                <DialogPrimitive.Description className="sr-only">{title}</DialogPrimitive.Description>
              )}
            </div>
            <DialogPrimitive.Close className="tso-x" aria-label="Close">
              <X size={14} strokeWidth={2.4} aria-hidden />
            </DialogPrimitive.Close>
          </div>
          <div className="tso-dialog-body">{children}</div>
          <div className="tso-dialog-foot">{footer}</div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}

/** One labelled field in a Trust & Safety dialog. */
export function TrustSafetyField({ label, htmlFor, children }: { label: string; htmlFor?: string; children: ReactNode }) {
  return (
    <div className="tso-field">
      {htmlFor ? <label htmlFor={htmlFor}>{label}</label> : <span className="tso-field-label">{label}</span>}
      {children}
    </div>
  )
}
