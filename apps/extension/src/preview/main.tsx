import "./stub"
import { createRoot } from "react-dom/client"
import "../styles/theme.css"
import { PopupApp } from "../popup/app"
import { SidePanelApp } from "../sidepanel/app"
import { Overlay } from "../content/overlay"

const PAGE_URL = "https://www.linkedin.com/in/jane-doe-cto/"
// Hoisted so identity is stable across renders; Overlay's enrich effect keys
// off this object and a fresh literal would re-request in a loop.
const PAGE_CONTEXT = {
  fullName: "Jane Doe",
  title: "Chief Technology Officer",
  company: "Northwind Logistics",
  linkedinUrl: PAGE_URL,
  source: "linkedin",
}

/**
 * Visual harness: renders each extension surface at its real size, in light and
 * dark, side by side. Not part of the extension build.
 */
function Frame({
  label,
  width,
  dark,
  children,
}: {
  label: string
  width: number
  dark?: boolean
  children: React.ReactNode
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <span
        style={{
          font: "600 11px ui-sans-serif, system-ui",
          letterSpacing: "0.06em",
          textTransform: "uppercase",
          color: dark ? "#9aa4b2" : "#64748b",
        }}
      >
        {label}
      </span>
      <div
        className={dark ? "gvt-dark" : undefined}
        style={{
          width,
          border: "1px solid",
          borderColor: dark ? "#22303f" : "#e2e8f0",
          borderRadius: 12,
          overflow: "hidden",
        }}
      >
        {children}
      </div>
    </div>
  )
}

/**
 * Renders the overlay inline for review. The `[&>[role=dialog]]` overrides undo
 * only the viewport-anchoring (`fixed`/`inset`/`max-height`) so the card's own
 * sizing, borders and elevation are still exactly what ships.
 */
function OverlayFrame({ label, dark }: { label: string; dark?: boolean }) {
  return (
    <Frame label={label} width={380} dark={dark}>
      <div className="[&>[role=dialog]]:static [&>[role=dialog]]:max-h-none [&>[role=dialog]]:w-full [&>[role=dialog]]:rounded-none [&>[role=dialog]]:border-0">
        <Overlay pageUrl={PAGE_URL} pageContext={PAGE_CONTEXT} onClose={() => {}} />
      </div>
    </Frame>
  )
}

function Harness() {
  return (
    <div style={{ display: "flex", gap: 28, padding: 24, alignItems: "flex-start", flexWrap: "wrap" }}>
      <Frame label="Popup — light" width={360}>
        <PopupApp />
      </Frame>
      <Frame label="Popup — dark" width={360} dark>
        <PopupApp />
      </Frame>
      <Frame label="Side panel — light" width={400}>
        <SidePanelApp />
      </Frame>
      <Frame label="Side panel — dark" width={400} dark>
        <SidePanelApp />
      </Frame>
      {/* The overlay is the surface users actually spend time in, so it is
          reviewed at its real width in both themes. In the extension it lives
          in a shadow root; here it renders inline, which is fine because the
          harness page has no competing CSS.

          `OverlayFrame` neutralises the overlay's own `position: fixed` (correct
          in production, where it floats over LinkedIn) so both copies sit in the
          page flow instead of stacking in the viewport corner. Review-only. */}
      <OverlayFrame label="Overlay — light" />
      <OverlayFrame label="Overlay — dark" dark />
    </div>
  )
}

/**
 * Marketing capture mode: `?shot=<surface>&dark=1`.
 *
 * Renders exactly one surface at its real device width with no harness label or
 * padding, so a full-page screenshot is the product surface and nothing else.
 * This exists so marketing uses real screenshots of the shipping UI instead of
 * redrawn mockups that drift from what users actually get.
 */
function Shot({ surface, dark }: { surface: string; dark: boolean }) {
  const width = surface === "popup" ? 360 : surface === "sidepanel" ? 400 : 380
  const isOverlay = surface.startsWith("overlay")

  return (
    <div
      className={dark ? "gvt-dark" : undefined}
      style={{
        width,
        // Matches the harness frame so the captured edge looks intentional
        // rather than clipped.
        border: "1px solid",
        borderColor: dark ? "#22303f" : "#e2e8f0",
        borderRadius: 12,
        overflow: "hidden",
        background: dark ? "#0b0f14" : "#ffffff",
      }}
    >
      {surface === "popup" ? (
        <PopupApp />
      ) : surface === "sidepanel" ? (
        <SidePanelApp />
      ) : isOverlay ? (
        <div className="[&>[role=dialog]]:static [&>[role=dialog]]:max-h-none [&>[role=dialog]]:w-full [&>[role=dialog]]:rounded-none [&>[role=dialog]]:border-0">
          <Overlay pageUrl={PAGE_URL} pageContext={PAGE_CONTEXT} onClose={() => {}} />
        </div>
      ) : null}
    </div>
  )
}

const el = document.getElementById("root")
const q = new URLSearchParams(location.search)
const shot = q.get("shot")

if (el) {
  if (shot) {
    // Collapse the page to the surface itself so a full-page capture has no
    // surrounding whitespace to crop.
    document.documentElement.style.background = "transparent"
    document.body.style.cssText = "margin:0;padding:0;display:inline-block;background:transparent"
    el.style.cssText = "display:inline-block"
    createRoot(el).render(<Shot surface={shot} dark={q.get("dark") === "1"} />)
  } else {
    createRoot(el).render(<Harness />)
  }
}
