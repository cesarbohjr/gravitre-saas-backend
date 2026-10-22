/* Shared helpers for the popup and side panel. Elements are built with the DOM API, never innerHTML. */
const GV_ICONS = {
  ask: "M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z",
  appr: "M20 13c0 5-3.5 7.5-7.7 9a1 1 0 0 1-.6 0C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.2-2.7a1.2 1.2 0 0 1 1.6 0C14.5 3.8 17 5 19 5a1 1 0 0 1 1 1z M9 12l2 2 4-4",
  act: "M22 12h-4l-3 9L9 3l-3 9H2",
  ext: "M7 17 17 7 M7 7h10v10",
  plus: "M5 12h14 M12 5v14",
  check: "M20 6 9 17l-5-5",
  alert: "M2 12a10 10 0 1 0 20 0a10 10 0 1 0 -20 0 M12 8v4 M12 16h.01",
  spark: "M12 2v4 M12 18v4 M4.9 4.9l2.8 2.8 M16.3 16.3l2.8 2.8 M2 12h4 M18 12h4 M4.9 19.1l2.8-2.8 M16.3 7.7l2.8-2.8",
  panel: "M3 5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z M15 3v18",
  logout: "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4 M16 17l5-5-5-5 M21 12H9",
  page: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6",
}

const SVG_NS = "http://www.w3.org/2000/svg"

function gvIcon(name, size) {
  const svg = document.createElementNS(SVG_NS, "svg")
  svg.setAttribute("class", "ic")
  svg.setAttribute("viewBox", "0 0 24 24")
  svg.setAttribute("aria-hidden", "true")
  if (size) {
    svg.style.width = `${size}px`
    svg.style.height = `${size}px`
  }
  const path = document.createElementNS(SVG_NS, "path")
  path.setAttribute("d", GV_ICONS[name] || "")
  svg.appendChild(path)
  return svg
}

const GV_MARK_BAR = "M6 160C1 160-2 156 1 152L59 72C91 27 138 0 186 0H628C636 0 640 6 635 13L576 94C543 137 498 160 450 160Z"

/** The Gravitre two-bar mark, the same one the web app's sidebar shows. */
function gvMark(w = 24, h = 14) {
  const svg = document.createElementNS(SVG_NS, "svg")
  svg.setAttribute("width", String(w))
  svg.setAttribute("height", String(h))
  svg.setAttribute("viewBox", "0 0 640 367")
  svg.setAttribute("aria-hidden", "true")
  svg.setAttribute("fill", "currentColor")
  svg.style.color = "var(--br)"
  svg.style.flex = "none"
  for (const y of [0, 207]) {
    const path = document.createElementNS(SVG_NS, "path")
    path.setAttribute("d", GV_MARK_BAR)
    if (y) path.setAttribute("transform", `translate(0 ${y})`)
    svg.appendChild(path)
  }
  return svg
}

/** h("div", { class: "row", onclick }, child, "text") */
function h(tag, attrs, ...children) {
  const el = document.createElement(tag)
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue
    if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v)
    else if (k === "style" && typeof v === "object") Object.assign(el.style, v)
    else if (k === "class") el.className = v
    else el.setAttribute(k, v === true ? "" : String(v))
  }
  for (const c of children.flat()) {
    if (c == null || c === false) continue
    el.appendChild(typeof c === "string" || typeof c === "number" ? document.createTextNode(String(c)) : c)
  }
  return el
}

function gvSend(message) {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage(message, (res) => {
      if (chrome.runtime.lastError) resolve({ ok: false, error: chrome.runtime.lastError.message })
      else resolve(res || { ok: false, error: "No response" })
    })
  })
}

const GV_COLORS = ["#5b5bd6", "#2b59e0", "#0b8a5c", "#c0533a", "#8a5a06", "#4a6a8e", "#2f7d6d", "#9a4fb5"]

function gvAvatar(name, size = 26) {
  let hash = 0
  for (let i = 0; i < name.length; i++) hash = (hash * 31 + name.charCodeAt(i)) >>> 0
  const words = name.trim().split(/\s+/).filter(Boolean)
  const ini = words.length > 1 ? words[0][0] + words[words.length - 1][0] : (words[0] || "G")[0]
  return h(
    "span",
    { class: "av", "aria-hidden": "true", style: { width: `${size}px`, height: `${size}px`, background: GV_COLORS[hash % GV_COLORS.length] } },
    ini.toUpperCase(),
  )
}

let gvAppBase = "https://gravitre.app"

function gvSetAppBase(base) {
  if (typeof base === "string" && /^https?:\/\//.test(base)) gvAppBase = base.replace(/\/$/, "")
}

/** The web app's registry entry for a connector type, vendor key or name (see providers.js). */
function gvProvider(slug) {
  if (typeof GV_PROVIDERS === "undefined") return null
  const id = GV_PROVIDERS.lookup[String(slug || "").toLowerCase().replace(/[^a-z0-9]/g, "")]
  const e = id && GV_PROVIDERS.entries[id]
  return e ? { id, name: e[0], src: e[1], srcDark: e[2], lightPlate: Boolean(e[3]), darkPlate: Boolean(e[4]) } : null
}

function gvInitials(slug) {
  const s = String(slug || "").toLowerCase()
  const known = { hubspot: "HS", salesforce: "SF", slack: "SL", gmail: "GM", google: "G", apollo: "AP", linear: "LN", notion: "NO", zendesk: "ZD", stripe: "ST" }
  return known[s.split(/[._\s-]/)[0]] || s.slice(0, 2).toUpperCase()
}

/** Vendor logo served by gravitre.app, the same mark the web app shows; initials if it can't load. */
function gvBadge(slug, size = 20) {
  if (!String(slug || "").trim()) return null
  const p = gvProvider(slug)
  const box = { width: `${size}px`, height: `${size}px` }
  if (!p) return h("span", { class: "logo", style: box, title: gvAppName(slug) }, gvInitials(slug))
  const dark = window.matchMedia?.("(prefers-color-scheme: dark)").matches
  const plate = (!dark && p.lightPlate) ? " plate-ink" : (dark && p.darkPlate) ? " plate-bone" : ""
  const img = h("img", { src: `${gvAppBase}${dark ? p.srcDark : p.src}`, alt: "", draggable: "false" })
  const wrap = h("span", { class: `vlogo${plate}`, style: box, title: p.name, role: "img", "aria-label": p.name }, img)
  img.addEventListener("error", () => wrap.replaceWith(h("span", { class: "logo", style: box, title: p.name }, gvInitials(slug))))
  return wrap
}

function gvAgo(iso) {
  if (!iso) return ""
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return ""
  const m = Math.floor((Date.now() - t) / 60000)
  if (m < 1) return "now"
  if (m < 60) return `${m}m`
  const hr = Math.floor(m / 60)
  if (hr < 24) return `${hr}h`
  return `${Math.floor(hr / 24)}d`
}

function gvClock(iso) {
  const d = new Date(iso || "")
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })
}

function gvDay(iso) {
  const d = new Date(iso || "")
  if (Number.isNaN(d.getTime())) return "Earlier"
  const start = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime()
  const diff = Math.round((start(new Date()) - start(d)) / 86400000)
  if (diff === 0) return "Today"
  if (diff === 1) return "Yesterday"
  return d.toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" })
}

function gvStatus(status) {
  const s = String(status || "").toLowerCase()
  if (["success", "succeeded", "completed", "done", "approved", "ok", "sent", "created", "updated"].includes(s)) return ["st-done", s === "approved" ? "Approved" : "Done"]
  if (["failed", "error", "rejected", "cancelled", "blocked"].includes(s)) return ["st-fail", s === "rejected" ? "Rejected" : "Failed"]
  if (["pending", "waiting", "pending_approval", "awaiting_approval"].includes(s)) return ["st-wait", "Waiting"]
  if (["running", "in_progress", "started"].includes(s)) return ["st-run", "Running"]
  return ["st-q", s ? s.charAt(0).toUpperCase() + s.slice(1).replace(/_/g, " ") : "Event"]
}

function gvPill(status) {
  const [cls, label] = gvStatus(status)
  return h("span", { class: `pill ${cls}` }, h("span", { class: "dot" }), label)
}

function gvHumanize(key) {
  const t = String(key).replace(/[_.-]+/g, " ").trim().toLowerCase()
  return t.charAt(0).toUpperCase() + t.slice(1)
}

const GV_APP_NAMES = { hubspot: "HubSpot", salesforce: "Salesforce", gmail: "Gmail", slack: "Slack", linkedin: "LinkedIn", zendesk: "Zendesk", notion: "Notion", linear: "Linear", stripe: "Stripe", apollo: "Apollo", outlook: "Outlook" }

function gvAppName(slug) {
  return GV_APP_NAMES[String(slug).toLowerCase()] || gvProvider(slug)?.name || gvHumanize(slug)
}

function gvValue(v) {
  if (v == null) return null
  if (typeof v === "string") return v.trim() || null
  if (typeof v === "number") return String(v)
  if (typeof v === "boolean") return v ? "Yes" : "No"
  if (Array.isArray(v)) return v.map(gvValue).filter(Boolean).join(", ") || null
  try {
    const j = JSON.stringify(v)
    return j.length > 100 ? `${j.slice(0, 97)}...` : j
  } catch {
    return null
  }
}

/** The fields an approval card shows, from what GET /api/approvals returned. */
function gvApproval(raw) {
  const ctx = raw.context && typeof raw.context === "object" ? raw.context : {}
  const requester = String(raw.requested_by_name || raw.requested_by || raw.requestedBy || "System")
  const rows = []
  const action = ctx.label || ctx.action
  if (action) rows.push(["Action", String(action)])
  if (ctx.integration || ctx.entity) rows.push(["App", gvAppName(ctx.integration || ctx.entity)])
  const hidden = new Set(["page_url", "extension_page_url", "org_id", "user_id", "conversation_id"])
  for (const [k, v] of Object.entries(ctx.args && typeof ctx.args === "object" ? ctx.args : {})) {
    if (hidden.has(k)) continue
    const shown = gvValue(v)
    if (shown) rows.push([gvHumanize(k), shown])
    if (rows.length >= 6) break
  }
  if (ctx.impact) rows.push(["Impact", String(ctx.impact)])
  return {
    id: String(raw.id || raw.run_id || ""),
    title: String(raw.title || raw.summary || "Approval request"),
    requester: /^[0-9a-f-]{36}$/i.test(requester) ? "Team member" : requester.includes("@") ? requester.split("@")[0] : requester,
    requestedAt: raw.requested_at || raw.created_at || null,
    integration: ctx.integration || null,
    rows,
  }
}
