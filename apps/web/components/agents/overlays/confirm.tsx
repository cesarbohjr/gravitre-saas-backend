"use client"

import { useEffect, useState, type ReactNode } from "react"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"

export type ConfirmOptions = {
  title: string
  description?: ReactNode
  confirmLabel?: string
  cancelLabel?: string
  /** "danger" puts the red tile and a red confirm button on it, for deletes and disconnects. */
  tone?: "danger" | "default"
}

type Pending = ConfirmOptions & { resolve: (ok: boolean) => void }

let show: ((request: Pending) => void) | null = null

/**
 * Ask before doing something. Resolves true when the person confirms.
 * On the Agents surface it opens the Agents confirm (a bottom sheet on phones);
 * elsewhere it falls back to the browser's confirm.
 */
export function confirmDialog(options: ConfirmOptions): Promise<boolean> {
  if (!show) {
    const text = [options.title, typeof options.description === "string" ? options.description : ""].filter(Boolean).join("\n\n")
    return Promise.resolve(typeof window !== "undefined" && window.confirm(text))
  }
  const open = show
  return new Promise((resolve) => open({ ...options, resolve }))
}

export function AgentsConfirmHost() {
  const [request, setRequest] = useState<Pending | null>(null)

  useEffect(() => {
    show = (next) =>
      setRequest((current) => {
        current?.resolve(false)
        return next
      })
    return () => {
      show = null
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
    <AlertDialog open={request != null} onOpenChange={(open) => (open ? null : settle(false))}>
      {request ? (
        <AlertDialogContent tone={danger ? "danger" : undefined}>
          <AlertDialogHeader>
            <AlertDialogTitle>{request.title}</AlertDialogTitle>
            {request.description ? <AlertDialogDescription>{request.description}</AlertDialogDescription> : null}
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => settle(false)}>{request.cancelLabel ?? "Cancel"}</AlertDialogCancel>
            <AlertDialogAction tone={danger ? "danger" : undefined} onClick={() => settle(true)}>
              {request.confirmLabel ?? (danger ? "Delete" : "Continue")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      ) : null}
    </AlertDialog>
  )
}
