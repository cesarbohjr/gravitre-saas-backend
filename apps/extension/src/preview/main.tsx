import "./stub"
import { createRoot } from "react-dom/client"
import "../styles/theme.css"
import { PopupApp } from "../popup/app"
import { SidePanelApp } from "../sidepanel/app"

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
    </div>
  )
}

const el = document.getElementById("root")
if (el) createRoot(el).render(<Harness />)
