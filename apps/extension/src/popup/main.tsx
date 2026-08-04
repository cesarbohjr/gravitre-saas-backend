import { createRoot } from "react-dom/client"
import "../styles/theme.css"
import { PopupApp } from "./app"

const el = document.getElementById("root")
if (el) {
  createRoot(el).render(<PopupApp />)
}
