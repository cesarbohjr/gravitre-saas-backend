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
          harness page has no competing CSS. */}
      <Frame label="Overlay — light" width={380}>
        <Overlay pageUrl={PAGE_URL} pageContext={PAGE_CONTEXT} onClose={() => {}} />
      </Frame>
      <Frame label="Overlay — dark" width={380} dark>
        <Overlay pageUrl={PAGE_URL} pageContext={PAGE_CONTEXT} onClose={() => {}} />
      </Frame>
    </div>
  )
}

const el = document.getElementById("root")
if (el) createRoot(el).render(<Harness />)
