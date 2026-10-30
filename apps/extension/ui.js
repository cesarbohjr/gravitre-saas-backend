/* Shared helpers for the popup and side panel. Elements are built with the DOM API, never innerHTML. */
const GV_ICONS = {
  ask: "M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z",
  appr: "M20 13c0 5-3.5 7.5-7.7 9a1 1 0 0 1-.6 0C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.2-2.7a1.2 1.2 0 0 1 1.6 0C14.5 3.8 17 5 19 5a1 1 0 0 1 1 1z",
  shieldok: "M20 13c0 5-3.5 7.5-7.7 9a1 1 0 0 1-.6 0C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.2-2.7a1.2 1.2 0 0 1 1.6 0C14.5 3.8 17 5 19 5a1 1 0 0 1 1 1z M9 12l2 2 4-4",
  act: "M22 12h-4l-3 9L9 3l-3 9H2",
  ext: "M7 17 17 7 M7 7h10v10",
  plus: "M5 12h14 M12 5v14",
  check: "M20 6 9 17l-5-5",
  x: "M18 6 6 18 M6 6l12 12",
  alert: "M2 12a10 10 0 1 0 20 0a10 10 0 1 0 -20 0 M12 8v4 M12 16h.01",
  panel: "M3 5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z M15 3v18",
  logout: "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4 M16 17l5-5-5-5 M21 12H9",
  page: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6",
  sel: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M8 13h8 M8 17h5",
  chev: "M6 9l6 6 6-6",
  chevr: "M9 6l6 6-6 6",
  updown: "m7 15 5 5 5-5 M7 9l5-5 5 5",
  more: "M5 12h.01 M12 12h.01 M19 12h.01",
  edit: "M12 20h9 M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z",
  voice: "M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z M19 10v2a7 7 0 0 1-14 0v-2 M12 19v3",
  text: "M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z",
  stop: "M6 6h12v12H6z",
  up: "M12 19V5 M5 12l7-7 7 7",
  play: "M7 4l12 8-12 8z",
  lock: "M5 11h14v10H5z M8 11V7a4 4 0 0 1 8 0v4",
  user: "M12 12a4 4 0 1 0 0-8a4 4 0 1 0 0 8z M4 21c0-4 4-6 8-6s8 2 8 6",
  wifioff: "M2 2l20 20 M8.5 16.4a5 5 0 0 1 7 0 M5 12.9a10 10 0 0 1 5.2-2.8 M19 12.9a10 10 0 0 0-2-1.5 M2 8.8a15 15 0 0 1 4.2-2.6 M22 8.8A15 15 0 0 0 10.7 5 M12 20h.01",
  clock: "M12 7v5l3 2 M2 12a10 10 0 1 0 20 0a10 10 0 1 0 -20 0",
  back: "M19 12H5 M12 19l-7-7 7-7",
  gear: "M12 15a3 3 0 1 0 0-6a3 3 0 1 0 0 6z M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z",
  globe: "M2 12a10 10 0 1 0 20 0a10 10 0 1 0 -20 0 M2 12h20 M12 2a15 15 0 0 1 0 20 M12 2a15 15 0 0 0 0 20",
  search: "M21 21l-4.3-4.3 M3 11a8 8 0 1 0 16 0a8 8 0 1 0 -16 0",
  swap: "M7 16V4 M3 8l4-4 4 4 M17 8v12 M21 16l-4 4-4-4",
  dot: "M12 12h.01",
}

const SVG_NS = "http://www.w3.org/2000/svg"

function gvPath(d, size) {
  const svg = document.createElementNS(SVG_NS, "svg")
  svg.setAttribute("class", "ic")
  svg.setAttribute("viewBox", "0 0 24 24")
  svg.setAttribute("aria-hidden", "true")
  if (size) {
    svg.style.width = `${size}px`
    svg.style.height = `${size}px`
  }
  const path = document.createElementNS(SVG_NS, "path")
  path.setAttribute("d", d || "")
  svg.appendChild(path)
  return svg
}

function gvIcon(name, size) {
  return gvPath(GV_ICONS[name] || "", size)
}

const GV_MARK_BAR = "M6 160C1 160-2 156 1 152L59 72C91 27 138 0 186 0H628C636 0 640 6 635 13L576 94C543 137 498 160 450 160Z"

/** The Gravitre two-bar mark. */
function gvMark(w = 24, h = 14, color = "var(--br)") {
  const svg = document.createElementNS(SVG_NS, "svg")
  svg.setAttribute("width", String(w))
  svg.setAttribute("height", String(h))
  svg.setAttribute("viewBox", "0 0 640 367")
  svg.setAttribute("aria-hidden", "true")
  svg.setAttribute("fill", "currentColor")
  svg.style.color = color
  svg.style.flex = "none"
  for (const y of [0, 207]) {
    const path = document.createElementNS(SVG_NS, "path")
    path.setAttribute("d", GV_MARK_BAR)
    if (y) path.setAttribute("transform", `translate(0 ${y})`)
    svg.appendChild(path)
  }
  return svg
}

/** The real app icon: mint mark on the brand-green tile (matches icons/icon128.png). */
function gvMarkTile(size = 22) {
  return h("span", { class: "mark", title: "Gravitre", style: { width: `${size}px`, height: `${size}px` } }, gvMark(Math.round(size * 0.62), Math.round(size * 0.36), "#e0f3ec"))
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

/** replaceChildren/append that skip null and false, which the DOM would print as text. */
function gvSet(el, ...kids) {
  el.replaceChildren(...kids.flat().filter((k) => k != null && k !== false))
}

function gvAdd(el, ...kids) {
  el.append(...kids.flat().filter((k) => k != null && k !== false))
}

function gvSend(message) {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage(message, (res) => {
      if (chrome.runtime.lastError) resolve({ ok: false, error: chrome.runtime.lastError.message })
      else resolve(res || { ok: false, error: "No response" })
    })
  })
}

/* ------------------------------------------------------------------ */
/* Preferences (this browser only)                                      */
/* ------------------------------------------------------------------ */

/** The sites Gravitre ships with. Added sites are stored as their host. */
const GV_SITES = [
  { id: "linkedin.com", label: "linkedin.com", kind: "people" },
  { id: "mail.google.com", label: "mail.google.com", kind: "email" },
  { id: "outlook", label: "Outlook on the web", kind: "email" },
  { id: "salesforce", label: "Salesforce", kind: "crm" },
  { id: "app.slack.com", label: "app.slack.com", kind: "people" },
]

const GV_DETECT = [
  { id: "people", label: "People profiles" },
  { id: "company", label: "Company pages" },
  { id: "crm", label: "CRM records" },
  { id: "email", label: "Email threads" },
]

const GV_DEFAULT_PREFS = {
  consentAt: null,
  sites: {},
  added: [],
  detect: { people: true, company: true, crm: true, email: true },
  floating: true,
  hiddenHosts: [],
  theme: "system",
  agentId: "",
}

async function gvPrefs() {
  const { gvPrefs: stored } = await chrome.storage.local.get("gvPrefs")
  const p = { ...GV_DEFAULT_PREFS, ...(stored || {}) }
  p.detect = { ...GV_DEFAULT_PREFS.detect, ...(stored?.detect || {}) }
  return p
}

async function gvSavePrefs(patch) {
  const next = { ...(await gvPrefs()), ...patch }
  await chrome.storage.local.set({ gvPrefs: next })
  return next
}

function gvSiteOn(prefs, id) {
  return prefs.sites[id] !== false
}

function gvApplyTheme(theme) {
  if (theme === "light" || theme === "dark") document.documentElement.setAttribute("data-theme", theme)
  else document.documentElement.removeAttribute("data-theme")
}

function gvIsDark() {
  const t = document.documentElement.getAttribute("data-theme")
  if (t) return t === "dark"
  return Boolean(window.matchMedia?.("(prefers-color-scheme: dark)").matches)
}

/* ------------------------------------------------------------------ */
/* Identity                                                            */
/* ------------------------------------------------------------------ */

const GV_COLORS = ["#5b5bd6", "#2b59e0", "#0b8a5c", "#a5563c", "#8a5a06", "#4a6a8e", "#2f7d6d", "#9a4fb5"]

function gvColor(seed) {
  let hash = 0
  for (let i = 0; i < seed.length; i++) hash = (hash * 31 + seed.charCodeAt(i)) >>> 0
  return GV_COLORS[hash % GV_COLORS.length]
}

function gvInitialsOf(name) {
  const words = String(name || "").trim().split(/\s+/).filter(Boolean)
  return (words.length > 1 ? words[0][0] + words[words.length - 1][0] : (words[0] || "G").slice(0, 2)).toUpperCase()
}

/** A person: initials on a neutral disc. */
function gvPersonAvatar(name, size = 26) {
  return h("span", { class: "av pav", "aria-hidden": "true", style: { width: `${size}px`, height: `${size}px`, fontSize: `${Math.round(size * 0.4)}px` } }, gvInitialsOf(name))
}

/** A member of the workspace: initials on a stable color. */
function gvAvatar(name, size = 26) {
  return h("span", { class: "av", "aria-hidden": "true", style: { width: `${size}px`, height: `${size}px`, background: gvColor(String(name || "")), fontSize: `${Math.round(size * 0.4)}px` } }, gvInitialsOf(name))
}

function gvWsTile(name, size = 20) {
  return h("span", { class: "wstile", "aria-hidden": "true", style: { width: `${size}px`, height: `${size}px`, background: gvColor(`ws:${name}`), fontSize: `${Math.round(size * 0.5)}px` } }, (String(name || "W").trim()[0] || "W").toUpperCase())
}

/* Agent identity: the department color and icon the web app and desktop use (apps/web/lib/listing-identity.ts). */
const GV_SHIELD = "M12 3l7 3v5c0 4.4-3 8.3-7 10-4-1.7-7-5.6-7-10V6z M9 12l2 2 4-4"
const GV_BOT = "M8 8h8a3 3 0 0 1 3 3v5a3 3 0 0 1-3 3H8a3 3 0 0 1-3-3v-5a3 3 0 0 1 3-3z M12 5.5v2.5 M12 2.6v.01 M9.5 13.5h.01 M14.5 13.5h.01"
const GV_DEPTS = {
  sales: ["Sales", "#5B5BD6", "M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18z M12 7a5 5 0 1 0 0 10a5 5 0 1 0 0-10z M12 11a1 1 0 1 0 0 2a1 1 0 1 0 0-2z"],
  marketing: ["Marketing", "#A5563C", "M3 10v4h3l7 4V6L6 10z M16 9a4 4 0 0 1 0 6 M18.5 6.5a7.5 7.5 0 0 1 0 11"],
  support: ["Support", "#4D6472", "M4 5h16v11H9l-5 4z M8 9h8 M8 12h5"],
  customer_success: ["Customer success", "#1F7A6E", "M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"],
  finance: ["Finance", "#4E7350", "M7 3h10a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z M8 6h8v3.5H8z M8.5 13h1 M11.5 13h1 M14.5 13h1 M8.5 16.5h1 M11.5 16.5h1 M14.5 16.5h1"],
  operations: ["Operations", "#8A5A06", "M12 8a4 4 0 1 0 0 8a4 4 0 1 0 0-8z M12 2v3 M12 19v3 M2 12h3 M19 12h3 M4.9 4.9l2.1 2.1 M17 17l2.1 2.1 M4.9 19.1l2.1-2.1 M17 7l2.1-2.1"],
  hr: ["HR", "#9C4668", "M9 11a3 3 0 1 0 0-6a3 3 0 1 0 0 6z M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6 M16 11a3 3 0 1 0 0-6 M21 20c0-3-2-5.5-5-6"],
  engineering: ["Engineering", "#33342F", "M8 7l-5 5 5 5 M16 7l5 5-5 5 M14 4l-4 16"],
  security: ["Security", "#A3333D", GV_SHIELD],
  general: ["General", "#55564F", GV_BOT],
}

function gvDept(value) {
  const key = String(value ?? "").trim().toLowerCase().replace(/[_-]+/g, " ").replace(/\s+/g, " ")
  let id = "general"
  if (!key) id = "general"
  else if (key.includes("customer success") || key === "cs" || key.includes("renewal") || key.includes("account manag")) id = "customer_success"
  else if (key.includes("support") || key.includes("helpdesk") || key.includes("service desk")) id = "support"
  else if (key.includes("sales") || key.includes("revenue") || key.includes("sdr") || key.includes("bdr")) id = "sales"
  else if (key.includes("market") || key.includes("growth") || key.includes("content")) id = "marketing"
  else if (key.includes("financ") || key.includes("account") || key.includes("billing")) id = "finance"
  else if (key.includes("security") || key.includes("compliance")) id = "security"
  else if (key.includes("engineer") || key.includes("devops") || key.includes("developer")) id = "engineering"
  else if (key === "hr" || key.includes("human resource") || key.includes("people") || key.includes("recruit") || key.includes("talent")) id = "hr"
  else if (key.includes("operation") || key === "ops" || key === "it" || key.includes("revops")) id = "operations"
  const [label, color, icon] = GV_DEPTS[id]
  return { id, label, color, icon }
}

/** Agents from /api/agents, looked up by id first, then by name. */
function gvIdentity(agents, name, id) {
  const list = agents || []
  const hit = (id && list.find((a) => a.id === id)) || (name && list.find((a) => a.name.toLowerCase() === String(name).trim().toLowerCase())) || null
  if (hit) return { name: hit.name, dept: gvDept(hit.department || hit.role) }
  return { name: String(name || "").trim() || "Gravitre", dept: gvDept("") }
}

function gvAgentAvatar(identity, size = 22) {
  return h(
    "span",
    { class: "av aav", "aria-hidden": "true", title: `${identity.name} · ${identity.dept.label}`, style: { width: `${size}px`, height: `${size}px`, color: identity.dept.color } },
    gvPath(identity.dept.icon, Math.round(size * 0.58)),
  )
}

function gvAgents(raw) {
  const rows = Array.isArray(raw) ? raw : Array.isArray(raw?.agents) ? raw.agents : []
  return rows
    .map((a) => {
      const config = a && typeof a.config === "object" && a.config ? a.config : {}
      return { id: String(a.id || ""), name: String(a.name || "Agent"), role: a.role || null, department: a.department || config.department || null }
    })
    .filter((a) => a.id)
}

/* ------------------------------------------------------------------ */
/* Controls                                                            */
/* ------------------------------------------------------------------ */

function gvToggle(on, label, onChange, disabled) {
  const btn = h("button", { class: `tog${on ? " on" : ""}`, role: "switch", "aria-checked": on ? "true" : "false", "aria-label": label, disabled: Boolean(disabled) })
  btn.addEventListener("click", () => {
    const next = btn.getAttribute("aria-checked") !== "true"
    btn.setAttribute("aria-checked", next ? "true" : "false")
    btn.classList.toggle("on", next)
    onChange(next)
  })
  return btn
}

function gvCheck(on, label, onChange) {
  const btn = h("button", { class: `cbx${on ? " on" : ""}`, role: "checkbox", "aria-checked": on ? "true" : "false", "aria-label": label }, on ? gvIcon("check") : null)
  btn.addEventListener("click", () => {
    const next = btn.getAttribute("aria-checked") !== "true"
    btn.setAttribute("aria-checked", next ? "true" : "false")
    btn.classList.toggle("on", next)
    btn.replaceChildren(...(next ? [gvIcon("check")] : []))
    onChange(next)
  })
  return btn
}

/** A one-line toast; with undo, the action runs only when the window closes without Undo. */
function gvToast(text, opts = {}) {
  document.querySelector(".toast")?.remove()
  const ms = opts.ms || 4000
  let undone = false
  const until = Date.now() + ms
  const left = h("span", { class: "mono", style: { opacity: ".6" } })
  const el = h(
    "div",
    { class: "toast fade", role: "status" },
    h("span", { class: "grow" }, text),
    opts.undo ? left : null,
    opts.undo
      ? h(
          "button",
          {
            class: "tbtn",
            onclick: () => {
              undone = true
              el.remove()
              opts.undo()
            },
          },
          "Undo",
        )
      : null,
  )
  document.body.appendChild(el)
  const tick = () => {
    const s = Math.max(0, Math.ceil((until - Date.now()) / 1000))
    left.textContent = `${s}s`
  }
  tick()
  const iv = setInterval(tick, 250)
  setTimeout(() => {
    clearInterval(iv)
    el.remove()
    if (!undone && opts.commit) opts.commit()
  }, ms)
}

/* ------------------------------------------------------------------ */
/* Vendor logos, time and status                                       */
/* ------------------------------------------------------------------ */

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
  const known = { hubspot: "HS", salesforce: "SF", slack: "SL", gmail: "GM", google: "G", apollo: "AP", linear: "LN", notion: "NO", zendesk: "ZD", stripe: "ST", web: "W" }
  return known[s.split(/[._\s-]/)[0]] || s.slice(0, 2).toUpperCase()
}

/** Vendor logo served by gravitre.app, the same mark the web app shows; initials if it can't load. */
function gvBadge(slug, size = 18) {
  if (!String(slug || "").trim()) return null
  const p = gvProvider(slug)
  const box = { width: `${size}px`, height: `${size}px` }
  if (!p) return h("span", { class: "logo", style: box, title: gvAppName(slug) }, gvInitials(slug))
  const dark = gvIsDark()
  const plate = !dark && p.lightPlate ? " plate-ink" : dark && p.darkPlate ? " plate-bone" : ""
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
  if (m < 60) return `${m} min`
  const hr = Math.floor(m / 60)
  if (hr < 24) return `${hr} h`
  return `${Math.floor(hr / 24)} d`
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

/** "10:42" today, "Yesterday", or the date. */
function gvWhen(iso) {
  const day = gvDay(iso)
  return day === "Today" ? gvClock(iso) : day
}

function gvStatus(status) {
  const s = String(status || "").toLowerCase()
  if (["success", "succeeded", "completed", "done", "approved", "ok", "sent", "created", "updated"].includes(s)) return ["st-done", s === "approved" ? "Approved" : "Done"]
  if (["failed", "error", "rejected", "cancelled", "blocked"].includes(s)) return ["st-fail", s === "rejected" ? "Rejected" : "Failed"]
  if (["pending", "waiting", "pending_approval", "awaiting_approval", "needs_approval"].includes(s)) return ["st-wait", s === "needs_approval" ? "Needs approval" : "Waiting"]
  if (["running", "in_progress", "started"].includes(s)) return ["st-run", "Running"]
  if (["queued", "paused"].includes(s)) return ["st-q", s === "paused" ? "Paused" : "Queued"]
  return ["st-q", s ? s.charAt(0).toUpperCase() + s.slice(1).replace(/_/g, " ") : "Event"]
}

function gvPill(status) {
  const [cls, label] = gvStatus(status)
  return h("span", { class: `pill ${cls}` }, h("span", { class: "dot" }), label)
}

function gvHumanize(key) {
  const t = String(key).replace(/[_.-]+/g, " ").replace(/([a-z])([A-Z])/g, "$1 $2").trim().toLowerCase()
  return t.charAt(0).toUpperCase() + t.slice(1)
}

function gvTitleCase(value) {
  return String(value || "")
    .replace(/[_-]+/g, " ")
    .split(" ")
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ")
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

/* ------------------------------------------------------------------ */
/* Approvals (GET /api/approvals), as the web decision queue reads them */
/* ------------------------------------------------------------------ */

function gvPick(o, ...keys) {
  for (const k of keys) if (o && o[k] != null && o[k] !== "") return o[k]
  return null
}

function gvRequester(raw) {
  const v = String(raw || "").trim()
  if (!v) return "System"
  if (/^[0-9a-f-]{36}$/i.test(v)) return "Team member"
  return v.includes("@") ? v.split("@")[0] : v
}

/** "Contact changes need approval", "Writes need one approval by default"... (web: policyLine). */
function gvPolicyLine(raw, ctx) {
  const p = raw.policy && typeof raw.policy === "object" ? raw.policy : null
  const reason = gvPick(ctx, "approval_reason", "approvalReason")
  if (!p) return reason ? String(reason) : null
  const req = Number(gvPick(p, "required_approvals", "requiredApprovals")) || 1
  const n = req > 1 ? `${req} approvals` : "one approval"
  const gate = String(gvPick(raw, "gate_type", "gateType") || ctx.gate_type || "")
  if (p.source === "hitl") return p.missing ? "A policy that no longer exists" : p.name || `Human-in-the-loop: ${n}`
  if (p.source === "hitl_default") return `Writes need ${n} by default`
  if (p.source === "extension_confirm") return "Extension writes need a confirmation"
  if (gate === "chat_orchestration_plan") return `Chat plans need ${n}`
  if (p.scope === "workflow") return `This workflow needs ${n}`
  if (p.scope === "org") return `Workflow runs need ${n}`
  return `Workflow runs need ${n} by default`
}

/** CRM property keys people know by another name. */
const GV_FIELD_LABELS = {
  lifecyclestage: "Lifecycle stage",
  hs_lead_status: "Lead status",
  hubspot_owner_id: "Contact owner",
  dealstage: "Deal stage",
  dealname: "Deal name",
  firstname: "First name",
  lastname: "Last name",
  jobtitle: "Job title",
  OwnerId: "Owner",
  StageName: "Stage",
}

/** The fields an approval card shows. Only "after approval" values: the API doesn't send what a field holds now. */
function gvApproval(raw) {
  const ctx = raw.context && typeof raw.context === "object" ? raw.context : {}
  const rows = []
  const hidden = new Set(["page_url", "extension_page_url", "org_id", "user_id", "conversation_id"])
  const args = ctx.args && typeof ctx.args === "object" ? ctx.args : {}
  const flat = args.properties && typeof args.properties === "object" ? { ...args, ...args.properties } : args
  for (const [k, v] of Object.entries(flat)) {
    if (hidden.has(k) || k === "properties") continue
    const shown = gvValue(v)
    if (shown) rows.push([GV_FIELD_LABELS[k] || gvHumanize(k), shown])
    if (rows.length >= 8) break
  }
  const p = raw.policy && typeof raw.policy === "object" ? raw.policy : null
  const roles = p && Array.isArray(p.approver_roles || p.approverRoles) ? (p.approver_roles || p.approverRoles).map(String) : []
  const steps = Array.isArray(raw.steps) ? raw.steps.filter((s) => s && typeof s === "object").map((s) => ({ text: String(s.text || s.action || "Step"), app: s.app || null, write: s.access === "write" })) : []
  return {
    id: String(raw.id || raw.run_id || ""),
    title: String(raw.title || raw.summary || "Approval request"),
    description: String(raw.description || ""),
    requester: gvRequester(gvPick(raw, "requestedByName", "requested_by_name", "requestedBy", "requested_by")),
    requestedAt: gvPick(raw, "requestedAt", "requested_at", "created_at"),
    integration: ctx.integration || null,
    action: ctx.label || ctx.action || null,
    policy: gvPolicyLine(raw, ctx),
    roles,
    conversationId: gvPick(ctx, "conversation_id", "conversationId"),
    impact: gvPick(ctx, "impact", "estimated_impact", "estimatedImpact"),
    steps,
    rows,
  }
}

/** Who can approve: "Admins", "Admins, Owners". */
function gvApprovers(a) {
  return a.roles.length ? a.roles.map((r) => `${gvTitleCase(r)}s`).join(", ") : "Admins"
}

/* ------------------------------------------------------------------ */
/* Assignments (GET /api/agent-jobs), the same reading as desktop       */
/* ------------------------------------------------------------------ */

function gvReadable(node) {
  if (typeof node === "string") {
    const t = node.trim()
    if (!t) return null
    const at = t.search(/[[{]/)
    if (at >= 0) {
      try {
        const found = gvReadable(JSON.parse(t.slice(at)))
        if (found) return found
      } catch {
        /* plain text */
      }
    }
    return t
  }
  if (Array.isArray(node)) {
    for (const e of node) {
      const f = gvReadable(e)
      if (f) return f
    }
    return null
  }
  if (node && typeof node === "object") {
    for (const k of ["objective", "title", "goal", "task", "description", "prompt", "message", "summary", "query"]) {
      const f = gvReadable(node[k])
      if (f) return f
    }
  }
  return null
}

function gvJob(job) {
  const r = job.result && typeof job.result === "object" ? job.result : {}
  const task = r.task && typeof r.task === "object" ? r.task : {}
  const objective = gvReadable(task.description) || gvReadable(r.finding_description) || gvReadable(r.summary) || "Agent task"
  const title = (gvReadable(r.action_title) || objective).slice(0, 96)
  let status = "queued"
  if (job.status === "running") status = "running"
  else if (job.status === "paused") status = "paused"
  else if (job.status === "failed" || job.status === "cancelled") status = "failed"
  else if (job.status === "completed") status = r.requires_approval || r.needs_human_input ? "needs_approval" : "done"
  const calls = Array.isArray(r.tool_calls) ? r.tool_calls : []
  const done = calls.filter((c) => c && c.result && c.result.success === true).length
  const pct = typeof r.progress_percent === "number" ? Math.round(r.progress_percent <= 1 ? r.progress_percent * 100 : r.progress_percent) : null
  const summary = gvReadable(r.summary) || gvReadable(r.answer)
  let line = ""
  if (status === "done") line = summary && summary !== title ? summary : "Finished."
  else if (status === "failed") line = String(job.error || r.error || "The run stopped before it finished.")
  else if (status === "needs_approval") line = String(r.human_input_prompt || "Waiting on your approval")
  else if (pct != null) line = `${pct}% done`
  else if (calls.length) line = `${done} of ${calls.length} steps done`
  return {
    id: String(job.jobId || job.job_id || job.id || ""),
    title,
    status,
    agent: String(r.agent_name || "Gravitre"),
    agentId: r.agent_id ? String(r.agent_id) : null,
    line,
    at: job.finishedAt || job.finished_at || job.createdAt || job.created_at || null,
  }
}

/* ------------------------------------------------------------------ */
/* The current page                                                    */
/* ------------------------------------------------------------------ */

function gvHostOf(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, "")
  } catch {
    return ""
  }
}

/** Which allowed-sites entry a host falls under; added sites are their own host. */
function gvSiteIdFor(host, prefs) {
  const hst = String(host || "").toLowerCase()
  if (!hst) return null
  if (hst === "linkedin.com" || hst.endsWith(".linkedin.com")) return "linkedin.com"
  if (hst === "mail.google.com") return "mail.google.com"
  if (/^outlook\.(office|office365|live)\.com$/.test(hst)) return "outlook"
  if (hst.endsWith("force.com") || hst.endsWith("salesforce.com")) return "salesforce"
  if (hst === "app.slack.com") return "app.slack.com"
  if (prefs && prefs.added.includes(hst)) return hst
  return null
}

/** Asks the tab's content script what is on the page. Null when Gravitre isn't on that site. */
function gvPageContext(tabId) {
  return new Promise((resolve) => {
    if (tabId == null) return resolve(null)
    try {
      chrome.tabs.sendMessage(tabId, { type: "GV_PAGE_CONTEXT" }, (res) => {
        if (chrome.runtime.lastError || !res?.ok) resolve(null)
        else resolve(res)
      })
    } catch {
      resolve(null)
    }
  })
}

function gvSelection(tabId) {
  return new Promise((resolve) => {
    if (tabId == null) return resolve("")
    chrome.tabs.sendMessage(tabId, { type: "GV_SELECTION" }, (res) => {
      if (chrome.runtime.lastError || !res?.ok) resolve("")
      else resolve(String(res.text || ""))
    })
  })
}

/** "In HubSpot", "In Apollo" from the enrich reads that found a match. */
function gvMatches(enrich) {
  const out = []
  for (const m of enrich?.matches || []) {
    if (!m?.success || m.confidenceLabel !== "matched") continue
    const app = String(m.action || "").split(".")[0]
    const what = String(m.action || "").includes("organizations") ? "company" : "contact"
    if (!out.some((o) => o.app === app)) out.push({ app, label: `In ${gvAppName(app)} · ${what} found` })
  }
  return out
}

/** A small popover menu under an anchor; closes on outside click or Escape. */
function gvMenu(anchor, items, opts = {}) {
  document.querySelector(".menu")?.remove()
  const menu = h("div", { class: "menu fade", role: "menu" })
  for (const it of items) {
    if (it.header) {
      menu.appendChild(h("div", { class: "mh" }, it.header))
      continue
    }
    menu.appendChild(
      h(
        "button",
        {
          class: `mi${it.on ? " on" : ""}`,
          role: "menuitem",
          onclick: () => {
            menu.remove()
            it.run()
          },
        },
        it.icon || null,
        h("span", { class: "grow ellipsis" }, it.label),
        it.hint ? h("span", { class: "sub xs" }, it.hint) : null,
        it.on ? gvIcon("check", 14) : null,
      ),
    )
  }
  const host = opts.host || anchor.offsetParent || document.body
  const a = anchor.getBoundingClientRect()
  const p = host.getBoundingClientRect()
  menu.style.top = `${a.bottom - p.top + 4}px`
  if (opts.right) menu.style.right = `${p.right - a.right}px`
  else menu.style.left = `${Math.max(4, a.left - p.left)}px`
  host.appendChild(menu)
  const close = (e) => {
    if (e.type === "keydown" && e.key !== "Escape") return
    if (e.type === "mousedown" && menu.contains(e.target)) return
    menu.remove()
    document.removeEventListener("mousedown", close, true)
    document.removeEventListener("keydown", close, true)
  }
  setTimeout(() => {
    document.addEventListener("mousedown", close, true)
    document.addEventListener("keydown", close, true)
  })
  menu.querySelector(".mi")?.focus()
  return menu
}

/** Workspace name with the switcher when the person belongs to more than one. */
function gvWorkspaceButton(orgName, organizations, currentId, onSwitch) {
  const many = (organizations || []).length > 1
  const btn = h(
    "button",
    { class: "hbtn", "aria-haspopup": many ? "menu" : null, disabled: !many, title: orgName, style: many ? null : { cursor: "default" } },
    gvWsTile(orgName || "W", 18),
    h("span", { class: "ellipsis" }, orgName || "Workspace"),
    many ? gvIcon("updown", 12) : null,
  )
  if (many) {
    btn.addEventListener("click", () =>
      gvMenu(
        btn,
        [{ header: "Switch workspace" }].concat(
          organizations.map((o) => ({ label: o.name || "Workspace", icon: gvWsTile(o.name || "W", 16), on: o.id === currentId, run: () => o.id !== currentId && onSwitch(o.id) })),
        ),
      ),
    )
  }
  return btn
}
