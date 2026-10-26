"use client"

import { useEffect, useState, type ReactNode } from "react"
import * as AlertDialogPrimitive from "@radix-ui/react-alert-dialog"
import { AlertTriangle, HelpCircle } from "lucide-react"

export type IntelligenceConfirmOptions = {
  title: string
  description?: ReactNode
  confirmLabel?: string
  cancelLabel?: string
  /** "danger" (the default) puts the red tile and a red confirm on it, for forgetting or deleting. */
  tone?: "danger" | "default"
}

type Pending = IntelligenceConfirmOptions & { resolve: (ok: boolean) => void }

let open: ((request: Pending) => void) | null = null

/**
 * Ask before doing something on an Intelligence page ("Forget this fact?").
 * Resolves true when the person confirms. Off the Intelligence pages it falls
 * back to the browser's confirm, like the Agents confirm does off its surface.
 */
export function confirmIntelligence(options: IntelligenceConfirmOptions): Promise<boolean> {
  if (!open) {
    const text = [options.title, typeof options.description === "string" ? options.description : ""]
      .filter(Boolean)
      .join("\n\n")
    return Promise.resolve(typeof window !== "undefined" && window.confirm(text))
  }
  const show = open
  return new Promise((resolve) => show({ ...options, resolve }))
}

/** Centered on a 48% ink scrim on desktop and iPad; a bottom sheet on phones. */
export function IntelligenceConfirmHost() {
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
          <AlertDialogPrimitive.Overlay className="ig-scrim" />
          <AlertDialogPrimitive.Content className="ig-dialog ig-confirm" data-tone={danger ? "danger" : "default"}>
            <div className="ig-confirm-body">
              <span className="ig-tile" aria-hidden>
                {danger ? <AlertTriangle size={18} strokeWidth={2.2} /> : <HelpCircle size={18} strokeWidth={2.2} />}
              </span>
              <div className="ig-confirm-copy">
                <AlertDialogPrimitive.Title className="ig-dialog-title">{request.title}</AlertDialogPrimitive.Title>
                {request.description ? (
                  <AlertDialogPrimitive.Description className="ig-dialog-desc">
                    {request.description}
                  </AlertDialogPrimitive.Description>
                ) : (
                  <AlertDialogPrimitive.Description className="sr-only">{request.title}</AlertDialogPrimitive.Description>
                )}
              </div>
            </div>
            <div className="ig-dialog-foot plain">
              <AlertDialogPrimitive.Cancel className="ig-btn ghost" onClick={() => settle(false)}>
                {request.cancelLabel ?? "Cancel"}
              </AlertDialogPrimitive.Cancel>
              <AlertDialogPrimitive.Action
                className={`ig-btn ${danger ? "danger" : "dark"}`}
                onClick={() => settle(true)}
              >
                {request.confirmLabel ?? (danger ? "Delete" : "Continue")}
              </AlertDialogPrimitive.Action>
            </div>
          </AlertDialogPrimitive.Content>
        </AlertDialogPrimitive.Portal>
      ) : null}
    </AlertDialogPrimitive.Root>
  )
}
