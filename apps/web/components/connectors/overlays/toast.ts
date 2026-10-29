import type { ReactNode } from "react"
import { toast as agentsToast } from "@/components/agents/overlays/toast"

/**
 * Toasts for the Connectors pages ("Connector toasts and dialogs" design),
 * shaped like the Agents toast API so call sites read the same
 * (`toast.success(title, { description, action })`), plus `vendor` and `topic`
 * so the toast can say which system it is about ("QUICKBOOKS · CONNECTED")
 * and show that system's mono tile.
 *
 * While the Connectors toaster is mounted (/connectors, a connector's page and
 * /marketplace/connectors) toasts render in the Connectors shell: bottom left,
 * three at most, hidden after six seconds with a progress bar. Anywhere else
 * (shared components used on other pages) they hand off to the Agents toast.
 */

export type ConnectorsToastTone = "success" | "error" | "warning" | "info" | "message" | "loading"

export type ConnectorsToastAction = {
  label: ReactNode
  onClick: (event: React.MouseEvent<HTMLButtonElement>) => void
}

export type ConnectorsToastOptions = {
  id?: string | number
  description?: ReactNode
  /** The system the toast is about (a connector name or vendor key). */
  vendor?: string
  /** What happened to it, for the eyebrow ("Connected", "Authorization", "Sync"). */
  topic?: string
  action?: ConnectorsToastAction
  cancel?: ConnectorsToastAction
  /** Milliseconds before it hides; Infinity keeps it until dismissed. */
  duration?: number
  onDismiss?: () => void
  onAutoClose?: () => void
}

export type ConnectorsToast = {
  id: string | number
  tone: ConnectorsToastTone
  title: ReactNode
  description?: ReactNode
  vendor?: string
  topic?: string
  action?: ConnectorsToastAction
  cancel?: ConnectorsToastAction
  duration: number
  createdAt: number
  onDismiss?: () => void
  onAutoClose?: () => void
}

export const CONNECTORS_TOAST_DURATION_MS = 6000
export const MAX_VISIBLE_CONNECTORS_TOASTS = 3

type Listener = (toasts: ConnectorsToast[]) => void

let toasts: ConnectorsToast[] = []
let seq = 0
let hosts = 0
const listeners = new Set<Listener>()

function emit() {
  for (const listener of listeners) listener(toasts)
}

/** The Connectors toaster calls this while it is mounted. */
export function registerConnectorsToaster(listener: Listener): () => void {
  hosts += 1
  listeners.add(listener)
  listener(toasts)
  return () => {
    hosts -= 1
    listeners.delete(listener)
    if (hosts <= 0) {
      hosts = 0
      toasts = []
    }
  }
}

export function connectorsToasterActive(): boolean {
  return hosts > 0
}

function push(tone: ConnectorsToastTone, title: ReactNode, options: ConnectorsToastOptions = {}): string | number {
  const id = options.id ?? `cn${Date.now().toString(36)}${(seq += 1)}`
  const next: ConnectorsToast = {
    id,
    tone,
    title,
    description: options.description,
    vendor: options.vendor,
    topic: options.topic,
    action: options.action,
    cancel: options.cancel,
    duration: options.duration ?? (tone === "loading" ? Number.POSITIVE_INFINITY : CONNECTORS_TOAST_DURATION_MS),
    createdAt: Date.now(),
    onDismiss: options.onDismiss,
    onAutoClose: options.onAutoClose,
  }
  const existing = toasts.findIndex((row) => row.id === id)
  if (existing >= 0) {
    // Same id updates in place (a loading toast turning into its result).
    toasts = toasts.map((row, index) => (index === existing ? next : row))
  } else {
    toasts = [...toasts, next].slice(-MAX_VISIBLE_CONNECTORS_TOASTS)
  }
  emit()
  return id
}

/** Remove one toast (or all). `reason` decides which callback runs. */
export function removeConnectorsToast(id?: string | number, reason: "dismiss" | "auto" = "dismiss") {
  const gone = id == null ? toasts : toasts.filter((row) => row.id === id)
  if (gone.length === 0) return
  toasts = id == null ? [] : toasts.filter((row) => row.id !== id)
  emit()
  for (const row of gone) (reason === "auto" ? row.onAutoClose : row.onDismiss)?.()
}

/** Off the Connectors pages: the same tone in the Agents shell, without the vendor tile. */
function handOff(tone: ConnectorsToastTone, title: ReactNode, options?: ConnectorsToastOptions): string | number {
  if (!options) return agentsToast[tone](title)
  const { vendor: _vendor, topic: _topic, ...rest } = options
  return agentsToast[tone](title, rest)
}

function show(tone: ConnectorsToastTone, title: ReactNode, options?: ConnectorsToastOptions): string | number {
  if (connectorsToasterActive()) return push(tone, title, options)
  return handOff(tone, title, options)
}

type PromiseMessages<T> = {
  loading: ReactNode
  success: ReactNode | ((data: T) => ReactNode)
  error: ReactNode | ((error: unknown) => ReactNode)
  description?: ReactNode
  vendor?: string
  topic?: string
}

function promiseToast<T>(promise: Promise<T> | (() => Promise<T>), messages: PromiseMessages<T>) {
  const run = typeof promise === "function" ? promise() : promise
  const base = { vendor: messages.vendor, topic: messages.topic }
  const id = show("loading", messages.loading, { ...base, description: messages.description })
  run.then(
    (data) => {
      const title =
        typeof messages.success === "function" ? (messages.success as (d: T) => ReactNode)(data) : messages.success
      show("success", title, { ...base, id })
    },
    (error: unknown) => {
      const title =
        typeof messages.error === "function" ? (messages.error as (e: unknown) => ReactNode)(error) : messages.error
      show("error", title, { ...base, id })
    },
  )
  return id
}

type Show = (title: ReactNode, options?: ConnectorsToastOptions) => string | number

type ToastFn = Show & {
  success: Show
  error: Show
  warning: Show
  info: Show
  message: Show
  loading: Show
  promise: typeof promiseToast
  dismiss: (id?: string | number) => void
}

export const toast: ToastFn = Object.assign((title: ReactNode, options?: ConnectorsToastOptions) => show("message", title, options), {
  success: (title: ReactNode, options?: ConnectorsToastOptions) => show("success", title, options),
  error: (title: ReactNode, options?: ConnectorsToastOptions) => show("error", title, options),
  warning: (title: ReactNode, options?: ConnectorsToastOptions) => show("warning", title, options),
  info: (title: ReactNode, options?: ConnectorsToastOptions) => show("info", title, options),
  message: (title: ReactNode, options?: ConnectorsToastOptions) => show("message", title, options),
  loading: (title: ReactNode, options?: ConnectorsToastOptions) => show("loading", title, options),
  promise: promiseToast,
  dismiss: (id?: string | number) => {
    if (connectorsToasterActive()) removeConnectorsToast(id)
    else agentsToast.dismiss(id)
  },
})
