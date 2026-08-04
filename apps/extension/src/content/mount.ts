import { createRoot, type Root } from "react-dom/client"

// `?inline` hands us Tailwind's compiled output as a string instead of letting
// Vite inject a <style> into the host document. That distinction is the whole
// ballgame for a content script: injecting Tailwind's preflight globally would
// reset typography and box-sizing on LinkedIn, Gmail and Salesforce. Instead we
// adopt the sheet into a shadow root, so our styles cannot escape and the host
// page's styles cannot reach in.
import css from "@/styles/theme.css?inline"

const HOST_ID = "gravitre-overlay-root"

let root: Root | null = null
let host: HTMLElement | null = null

/**
 * Create (or reuse) the shadow host and return a React root rendering into it.
 *
 * The host is `position: fixed` and appended to <html>, so it never
 * participates in the host page's layout — no reflow, no scrollbar shift, no
 * content jump when the overlay opens (Part B.5).
 */
export function mountOverlay(render: () => React.ReactNode): void {
  if (!host) {
    host = document.getElementById(HOST_ID) as HTMLElement | null
  }

  if (!host) {
    host = document.createElement("div")
    host.id = HOST_ID

    // Inline styles on the host itself: these must survive even if the host
    // page has aggressive `div { ... }` rules, and they can't live in the
    // adopted sheet because the sheet applies inside the shadow tree.
    host.style.cssText = [
      "position: fixed",
      "top: 0",
      "left: 0",
      "width: 0",
      "height: 0",
      "margin: 0",
      "padding: 0",
      "border: 0",
      "z-index: 2147483646",
      // The host is a zero-size anchor; the panel inside positions itself.
      // `visible` lets the panel paint outside those zero bounds.
      "overflow: visible",
      // Belt and braces against host pages that set `all: revert` or similar.
      "color-scheme: light dark",
    ].join(";")

    const shadow = host.attachShadow({ mode: "open" })

    // Prefer constructable stylesheets (cheap to share, no FOUC). Fall back to
    // a <style> node inside the shadow root for older engines.
    if ("adoptedStyleSheets" in Document.prototype && "replaceSync" in CSSStyleSheet.prototype) {
      const sheet = new CSSStyleSheet()
      sheet.replaceSync(css)
      shadow.adoptedStyleSheets = [sheet]
    } else {
      const style = document.createElement("style")
      style.textContent = css
      shadow.appendChild(style)
    }

    const mountPoint = document.createElement("div")
    shadow.appendChild(mountPoint)

    document.documentElement.appendChild(host)
    root = createRoot(mountPoint)
  }

  root?.render(render() as never)
}

/** Tear the overlay down completely so re-opening starts from a clean state. */
export function unmountOverlay(): void {
  root?.unmount()
  root = null
  host?.remove()
  host = null
}

export function isOverlayMounted(): boolean {
  return Boolean(host?.isConnected)
}
