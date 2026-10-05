"use client"

import { useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog"

export function WorkDecisionDialog({
  title,
  description,
  actionLabel,
  destructive,
  cancelLabel = "Keep current state",
  busyLabel = "Saving decision…",
  onCancel,
  onConfirm,
}: {
  title: string
  description: string
  actionLabel: string
  cancelLabel?: string
  busyLabel?: string
  destructive?: boolean
  onCancel: () => void
  onConfirm: () => Promise<void>
}) {
  const lock = useRef(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  async function confirm() {
    if (lock.current) return
    lock.current = true
    setBusy(true)
    setError(null)
    try {
      await onConfirm()
      onCancel()
    } catch (err) {
      setError(err instanceof Error ? err.message : "The decision could not be saved. Try again.")
    } finally {
      lock.current = false
      setBusy(false)
    }
  }
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !lock.current) onCancel()
      }}
    >
      <DialogContent className="[&_[data-slot=button]]:min-h-11">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        {error ? (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        ) : null}
        <DialogFooter>
          <Button variant="outline" disabled={busy} onClick={onCancel}>
            {cancelLabel}
          </Button>
          <Button
            variant={destructive ? "destructive" : "default"}
            disabled={busy}
            onClick={() => void confirm()}
          >
            {busy ? busyLabel : actionLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
