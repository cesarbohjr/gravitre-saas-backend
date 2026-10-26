"use client"

import type { ReactNode } from "react"
import { TrustSafetyConfirmHost } from "./confirm"
import { TrustSafetyToaster } from "./trust-safety-toaster"
import "./overlays.css"

/**
 * Mounts the Trust & Safety toaster and confirm host on /trust-safety. The
 * Settings pages that reuse these panels don't mount it, so toasts and confirms
 * sent from there go to the Agents shell instead. `eyebrow` names the open tab
 * on toasts that don't set their own.
 */
export function TrustSafetyOverlaysProvider({ eyebrow, children }: { eyebrow: string; children: ReactNode }) {
  return (
    <>
      {children}
      <TrustSafetyToaster eyebrow={eyebrow} />
      <TrustSafetyConfirmHost />
    </>
  )
}
