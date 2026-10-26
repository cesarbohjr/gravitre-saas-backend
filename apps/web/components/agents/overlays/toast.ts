import type { ReactNode } from "react"
import { toast as sonnerToast } from "sonner"

/**
 * One toast API for the whole web app, shaped like sonner's so call sites stay
 * the same (`toast.success(title, { description, action })`).
 *
 * On the Agents surface (the signed-in app, mounted by `AgentsToaster`) toasts
 * render in the Agents shell: bottom left, three at most, hidden after six
 * seconds with a progress bar. Anywhere the Agents toaster is not mounted (Lite,
 * marketing, onboarding) they go to the existing sonner toaster unchanged, until
 * those surfaces get their own design.
 */

export type ToastTone = "success" | "error" | "warning" | "info" | "message" | "loading"

export type ToastAction = { label: ReactNode; onClick: (event: React.MouseEvent<HTMLButtonElement>) => void }

export type ToastOptions = {
  id?: string | number
  description?: ReactNode
  /** Small mono label above the title, for example the app or page it came from. */
  eyebrow?: string
  action?: ToastAction
  cancel?: ToastAction
  /** Milliseconds before it hides; Infinity keeps it until dismissed. */
  duration?: number
  onDismiss?: () => void
  onAutoClose?: () => void
}

export type AgentsToast = {
  id: string | number
  tone: ToastTone
  title: ReactNode
  description?: ReactNode
  eyebrow?: string
  action?: ToastAction
  cancel?: ToastAction
  duration: number
  createdAt: number
  onDismiss?: () => void
  onAutoClose?: () => void
}

export const TOAST_DURATION_MS = 6000
export const MAX_VISIBLE_TOASTS = 3

type Listener = (toasts: AgentsToast[]) => void

let toasts: AgentsToast[] = []
let seq = 0
let hosts = 0
const listeners = new Set<Listener>()

function emit() {
  for (const listener of listeners) listener(toasts)
}

/** The Agents toaster calls this while it is mounted and active. */
export function registerAgentsToaster(listener: Listener): () => void {
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

export function agentsToasterActive(): boolean {
  return hosts > 0
}

function push(tone: ToastTone, title: ReactNode, options: ToastOptions = {}): string | number {
  const id = options.id ?? `t${Date.now().toString(36)}${(seq += 1)}`
  const next: AgentsToast = {
    id,
    tone,
    title,
    description: options.description,
    eyebrow: options.eyebrow,
    action: options.action,
    cancel: options.cancel,
    duration: options.duration ?? (tone === "loading" ? Number.POSITIVE_INFINITY : TOAST_DURATION_MS),
    createdAt: Date.now(),
    onDismiss: options.onDismiss,
    onAutoClose: options.onAutoClose,
  }
  const existing = toasts.findIndex((row) => row.id === id)
  if (existing >= 0) {
    // Same id updates in place (a loading toast turning into its result), restarting its timer.
    toasts = toasts.map((row, index) => (index === existing ? next : row))
  } else {
    toasts = [...toasts, next].slice(-MAX_VISIBLE_TOASTS)
  }
  emit()
  return id
}

/** Remove one toast (or all). `reason` decides which callback runs. */
export function removeToast(id?: string | number, reason: "dismiss" | "auto" = "dismiss") {
  const gone = id == null ? toasts : toasts.filter((row) => row.id === id)
  if (gone.length === 0) return
  toasts = id == null ? [] : toasts.filter((row) => row.id !== id)
  emit()
  for (const row of gone) (reason === "auto" ? row.onAutoClose : row.onDismiss)?.()
}

function sonnerOptions(options: ToastOptions) {
  const { eyebrow: _eyebrow, ...rest } = options
  return rest
}

const SONNER: Record<ToastTone, (title: ReactNode, options?: object) => string | number> = {
  success: (...args) => sonnerToast.success(...args),
  error: (...args) => sonnerToast.error(...args),
  warning: (...args) => sonnerToast.warning(...args),
  info: (...args) => sonnerToast.info(...args),
  loading: (...args) => sonnerToast.loading(...args),
  message: (...args) => sonnerToast.message(...args),
}

function show(tone: ToastTone, title: ReactNode, options?: ToastOptions): string | number {
  if (agentsToasterActive()) return push(tone, title, options)
  return options ? SONNER[tone](title, sonnerOptions(options)) : SONNER[tone](title)
}

type PromiseMessages<T> = {
  loading: ReactNode
  success: ReactNode | ((data: T) => ReactNode)
  error: ReactNode | ((error: unknown) => ReactNode)
  description?: ReactNode
}

function promiseToast<T>(promise: Promise<T> | (() => Promise<T>), messages: PromiseMessages<T>) {
  const run = typeof promise === "function" ? promise() : promise
  const id = show("loading", messages.loading, { description: messages.description })
  run.then(
    (data) => {
      const title = typeof messages.success === "function" ? (messages.success as (d: T) => ReactNode)(data) : messages.success
      show("success", title, { id })
    },
    (error: unknown) => {
      const title = typeof messages.error === "function" ? (messages.error as (e: unknown) => ReactNode)(error) : messages.error
      show("error", title, { id })
    },
  )
  return id
}

type ToastFn = ((title: ReactNode, options?: ToastOptions) => string | number) & {
  success: (title: ReactNode, options?: ToastOptions) => string | number
  error: (title: ReactNode, options?: ToastOptions) => string | number
  warning: (title: ReactNode, options?: ToastOptions) => string | number
  info: (title: ReactNode, options?: ToastOptions) => string | number
  message: (title: ReactNode, options?: ToastOptions) => string | number
  loading: (title: ReactNode, options?: ToastOptions) => string | number
  promise: typeof promiseToast
  dismiss: (id?: string | number) => void
}

export const toast: ToastFn = Object.assign((title: ReactNode, options?: ToastOptions) => show("message", title, options), {
  success: (title: ReactNode, options?: ToastOptions) => show("success", title, options),
  error: (title: ReactNode, options?: ToastOptions) => show("error", title, options),
  warning: (title: ReactNode, options?: ToastOptions) => show("warning", title, options),
  info: (title: ReactNode, options?: ToastOptions) => show("info", title, options),
  message: (title: ReactNode, options?: ToastOptions) => show("message", title, options),
  loading: (title: ReactNode, options?: ToastOptions) => show("loading", title, options),
  promise: promiseToast,
  dismiss: (id?: string | number) => {
    if (agentsToasterActive()) removeToast(id)
    else sonnerToast.dismiss(id)
  },
})
