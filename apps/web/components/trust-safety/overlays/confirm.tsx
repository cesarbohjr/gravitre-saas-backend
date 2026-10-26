"use client"

import { useEffect, useState, type ReactNode } from "react"
import * as AlertDialogPrimitive from "@radix-ui/react-alert-dialog"
import { AlertTriangle, HelpCircle } from "lucide-react"
import { confirmDialog } from "@/components/agents/overlays/confirm"

export type TrustSafetyConfirmOptions = {
  title: string
  description?: ReactNode
  confirmLabel?: string
  cancelLabel?: string
  /** "danger" (the default) puts the red tile and a red confirm on it, for deleting or blocking. */
  tone?: "danger" | "default"
}

type Pending = TrustSafetyConfirmOptions & { resolve: (ok: boolean) => void }

let open: ((request: Pending) => void) | null = null

/**
 * Ask before doing something on the Trust & Safety page ("Delete this policy?").
 * Resolves true when the person confirms. Off the page (the Settings pages that
 * reuse these panels) it hands off to the Agents confirm.
 */
export function confirmTrustSafety(options: TrustSafetyConfirmOptions): Promise<boolean> {
  if (!open) return confirmDialog({ ...options, tone: options.tone ?? "danger" })
  const show = open
  return new Promise((resolve) => show({ ...options, resolve }))
}

/** Centered on a 48% ink scrim on desktop and iPad; a bottom sheet on phones. */
export function TrustSafetyConfirmHost() {
  const [request, setRequest] = useState<Pending | null>(null)

  useEffect(() => {
    open = (next) =>
      setRequest((current) => {
        current?.resolve(false)
        return next
      })
    return () => {
      open = null
    }
  }, [])

  const settle = (ok: boolean) => {
    setRequest((current) => {
      current?.resolve(ok)
      return null
    })
  }

  const danger = request?.tone !== "default"
  return (
    <AlertDialogPrimitive.Root open={request != null} onOpenChange={(next) => (next ? null : settle(false))}>
      {request ? (
        <AlertDialogPrimitive.Portal>
          <AlertDialogPrimitive.Overlay className="tso-scrim" />
          <AlertDialogPrimitive.Content className="tso-dialog tso-confirm" data-tone={danger ? "danger" : "default"}>
            <div className="tso-confirm-body">
              <span className="tso-tile" aria-hidden>
                {danger ? <AlertTriangle size={18} strokeWidth={2.2} /> : <HelpCircle size={18} strokeWidth={2.2} />}
              </span>
              <div className="tso-confirm-copy">
                <AlertDialogPrimitive.Title className="tso-dialog-title">{request.title}</AlertDialogPrimitive.Title>
                {request.description ? (
                  <AlertDialogPrimitive.Description className="tso-dialog-desc">{request.description}</AlertDialogPrimitive.Description>
                ) : (
                  <AlertDialogPrimitive.Description className="sr-only">{request.title}</AlertDialogPrimitive.Description>
                )}
              </div>
            </div>
            <div className="tso-dialog-foot plain">
              <AlertDialogPrimitive.Cancel className="tso-btn ghost" onClick={() => settle(false)}>
                {request.cancelLabel ?? "Cancel"}
              </AlertDialogPrimitive.Cancel>
              <AlertDialogPrimitive.Action className={`tso-btn ${danger ? "danger" : "dark"}`} onClick={() => settle(true)}>
                {request.confirmLabel ?? (danger ? "Delete" : "Continue")}
              </AlertDialogPrimitive.Action>
            </div>
          </AlertDialogPrimitive.Content>
        </AlertDialogPrimitive.Portal>
      ) : null}
    </AlertDialogPrimitive.Root>
  )
}
