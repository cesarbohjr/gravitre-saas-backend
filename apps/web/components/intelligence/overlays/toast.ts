import type { ReactNode } from "react"
import { toast as agentsToast } from "@/components/agents/overlays/toast"

/**
 * Toasts for the Intelligence pages (Intelligence-ToastsPopups design), shaped
 * like the Agents toast API so call sites read the same
 * (`toast.success(title, { description, action })`).
 *
 * While the Intelligence toaster is mounted (inside the Intelligence and Models
 * layouts) toasts render in the Intelligence shell: bottom left, three at most,
 * hidden after six seconds with a progress bar. Anywhere else they hand off to
 * the Agents toast, which keeps its own design and fallbacks.
 *
 * Two tones only exist here: `approval` (something waits on a person; green
 * primary action, amber shield) and `progress` (work in flight, with a real
 * fraction done and a Cancel instead of a timer).
 */

export type IntelligenceToastTone =
  | "success"
  | "error"
  | "warning"
  | "info"
  | "message"
  | "loading"
  | "approval"
  | "progress"

export type IntelligenceToastAction = {
  label: ReactNode
  onClick: (event: React.MouseEvent<HTMLButtonElement>) => void
}

export type IntelligenceToastOptions = {
  id?: string | number
  description?: ReactNode
  /** Mono label above the title: what the toast is about ("SWEEP COMPLETE", "HUBSPOT"). */
  eyebrow?: string
  action?: IntelligenceToastAction
  cancel?: IntelligenceToastAction
  /** Milliseconds before it hides; Infinity keeps it until dismissed. */
  duration?: number
  /** Progress toasts only: fraction done, 0 to 1. */
  progress?: number
  onDismiss?: () => void
  onAutoClose?: () => void
}

export type IntelligenceToast = {
  id: string | number
  tone: IntelligenceToastTone
  title: ReactNode
  description?: ReactNode
  eyebrow?: string
  action?: IntelligenceToastAction
  cancel?: IntelligenceToastAction
  duration: number
  progress?: number
  createdAt: number
  onDismiss?: () => void
  onAutoClose?: () => void
}

export const INTELLIGENCE_TOAST_DURATION_MS = 6000
export const MAX_VISIBLE_INTELLIGENCE_TOASTS = 3

type Listener = (toasts: IntelligenceToast[]) => void

let toasts: IntelligenceToast[] = []
let seq = 0
let hosts = 0
const listeners = new Set<Listener>()

function emit() {
  for (const listener of listeners) listener(toasts)
}

/** The Intelligence toaster calls this while it is mounted. */
export function registerIntelligenceToaster(listener: Listener): () => void {
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

export function intelligenceToasterActive(): boolean {
  return hosts > 0
}

const UNTIMED: ReadonlySet<IntelligenceToastTone> = new Set(["loading", "progress"])

function push(tone: IntelligenceToastTone, title: ReactNode, options: IntelligenceToastOptions = {}): string | number {
  const id = options.id ?? `it${Date.now().toString(36)}${(seq += 1)}`
  const next: IntelligenceToast = {
    id,
    tone,
    title,
    description: options.description,
    eyebrow: options.eyebrow,
    action: options.action,
    cancel: options.cancel,
    duration: options.duration ?? (UNTIMED.has(tone) ? Number.POSITIVE_INFINITY : INTELLIGENCE_TOAST_DURATION_MS),
    progress: options.progress,
    createdAt: Date.now(),
    onDismiss: options.onDismiss,
    onAutoClose: options.onAutoClose,
  }
  const existing = toasts.findIndex((row) => row.id === id)
  if (existing >= 0) {
    // Same id updates in place (a progress toast advancing, or turning into its result).
    toasts = toasts.map((row, index) => (index === existing ? next : row))
  } else {
    toasts = [...toasts, next].slice(-MAX_VISIBLE_INTELLIGENCE_TOASTS)
  }
  emit()
  return id
}

/** Remove one toast (or all). `reason` decides which callback runs. */
export function removeIntelligenceToast(id?: string | number, reason: "dismiss" | "auto" = "dismiss") {
  const gone = id == null ? toasts : toasts.filter((row) => row.id === id)
  if (gone.length === 0) return
  toasts = id == null ? [] : toasts.filter((row) => row.id !== id)
  emit()
  for (const row of gone) (reason === "auto" ? row.onAutoClose : row.onDismiss)?.()
}

/** Off the Intelligence pages: the nearest Agents tone, without the Intelligence-only options. */
function handOff(tone: IntelligenceToastTone, title: ReactNode, options?: IntelligenceToastOptions): string | number {
  if (!options) {
    if (tone === "approval") return agentsToast.warning(title)
    if (tone === "progress") return agentsToast.loading(title)
    return agentsToast[tone](title)
  }
  const { progress: _progress, ...rest } = options
  if (tone === "approval") return agentsToast.warning(title, rest)
  if (tone === "progress") return agentsToast.loading(title, rest)
  return agentsToast[tone](title, rest)
}

function show(tone: IntelligenceToastTone, title: ReactNode, options?: IntelligenceToastOptions): string | number {
  if (intelligenceToasterActive()) return push(tone, title, options)
  return handOff(tone, title, options)
}

type PromiseMessages<T> = {
  loading: ReactNode
  success: ReactNode | ((data: T) => ReactNode)
  error: ReactNode | ((error: unknown) => ReactNode)
  description?: ReactNode
  eyebrow?: string
}

function promiseToast<T>(promise: Promise<T> | (() => Promise<T>), messages: PromiseMessages<T>) {
  const run = typeof promise === "function" ? promise() : promise
  const id = show("loading", messages.loading, { description: messages.description, eyebrow: messages.eyebrow })
  run.then(
    (data) => {
      const title =
        typeof messages.success === "function" ? (messages.success as (d: T) => ReactNode)(data) : messages.success
      show("success", title, { id, eyebrow: messages.eyebrow })
    },
    (error: unknown) => {
      const title =
        typeof messages.error === "function" ? (messages.error as (e: unknown) => ReactNode)(error) : messages.error
      show("error", title, { id, eyebrow: messages.eyebrow })
    },
  )
  return id
}

type Show = (title: ReactNode, options?: IntelligenceToastOptions) => string | number

type ToastFn = Show & {
  success: Show
  error: Show
  warning: Show
  info: Show
  message: Show
  loading: Show
  approval: Show
  progress: Show
  promise: typeof promiseToast
  dismiss: (id?: string | number) => void
}

export const toast: ToastFn = Object.assign((title: ReactNode, options?: IntelligenceToastOptions) => show("message", title, options), {
  success: (title: ReactNode, options?: IntelligenceToastOptions) => show("success", title, options),
  error: (title: ReactNode, options?: IntelligenceToastOptions) => show("error", title, options),
  warning: (title: ReactNode, options?: IntelligenceToastOptions) => show("warning", title, options),
  info: (title: ReactNode, options?: IntelligenceToastOptions) => show("info", title, options),
  message: (title: ReactNode, options?: IntelligenceToastOptions) => show("message", title, options),
  loading: (title: ReactNode, options?: IntelligenceToastOptions) => show("loading", title, options),
  approval: (title: ReactNode, options?: IntelligenceToastOptions) => show("approval", title, options),
  progress: (title: ReactNode, options?: IntelligenceToastOptions) => show("progress", title, options),
  promise: promiseToast,
  dismiss: (id?: string | number) => {
    if (intelligenceToasterActive()) removeIntelligenceToast(id)
    else agentsToast.dismiss(id)
  },
})
