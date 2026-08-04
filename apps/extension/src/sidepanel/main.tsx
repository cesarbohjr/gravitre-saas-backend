import { createRoot } from "react-dom/client"
import "../styles/theme.css"
import { SidePanelApp } from "./app"

const el = document.getElementById("root")
if (el) {
  createRoot(el).render(<SidePanelApp />)
}
