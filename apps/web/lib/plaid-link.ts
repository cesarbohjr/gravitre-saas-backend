/** Load Plaid Link JS (CDN) and open the Link modal with a link_token. */

const PLAID_SCRIPT_SRC = "https://cdn.plaid.com/link/v2/stable/link-initialize.js"

type PlaidHandler = {
  open: () => void
  exit: (options?: { force?: boolean }) => void
  destroy: () => void
}

type PlaidCreateConfig = {
  token: string
  onSuccess: (publicToken: string, metadata: Record<string, unknown>) => void
  onExit?: (err: unknown, metadata: Record<string, unknown>) => void
  onEvent?: (eventName: string, metadata: Record<string, unknown>) => void
}

declare global {
  interface Window {
    Plaid?: {
      create: (config: PlaidCreateConfig) => PlaidHandler
    }
  }
}

let scriptPromise: Promise<void> | null = null

export function loadPlaidLinkScript(): Promise<void> {
  if (typeof window === "undefined") {
    return Promise.reject(new Error("Plaid Link requires a browser"))
  }
  if (window.Plaid) return Promise.resolve()
  if (scriptPromise) return scriptPromise
  scriptPromise = new Promise((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${PLAID_SCRIPT_SRC}"]`)
    if (existing) {
      existing.addEventListener("load", () => resolve())
      existing.addEventListener("error", () => reject(new Error("Failed to load Plaid Link")))
      if (window.Plaid) resolve()
      return
    }
    const script = document.createElement("script")
    script.src = PLAID_SCRIPT_SRC
    script.async = true
    script.onload = () => resolve()
    script.onerror = () => reject(new Error("Failed to load Plaid Link"))
    document.body.appendChild(script)
  })
  return scriptPromise
}

export async function openPlaidLink(opts: {
  linkToken: string
  onSuccess: (publicToken: string, metadata: Record<string, unknown>) => void
  onExit?: (err: unknown) => void
}): Promise<PlaidHandler> {
  await loadPlaidLinkScript()
  if (!window.Plaid) {
    throw new Error("Plaid Link failed to initialize")
  }
  const handler = window.Plaid.create({
    token: opts.linkToken,
    onSuccess: opts.onSuccess,
    onExit: (err) => {
      opts.onExit?.(err)
    },
  })
  handler.open()
  return handler
}
