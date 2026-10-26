/**
 * Gravitre on the page: the floating button, the "In CRM" chip and the card next to a person or company.
 * Site adapters register what they can read; the side panel asks for it with GV_PAGE_CONTEXT.
 * Nothing is read or sent on a site the person turned off.
 */
(function () {
  if (window.__gravitre) return

  const SITE_IDS = [
    [/(^|\.)linkedin\.com$/, "linkedin.com"],
    [/^mail\.google\.com$/, "mail.google.com"],
    [/^outlook\.(office|office365|live)\.com$/, "outlook"],
    [/(force|salesforce)\.com$/, "salesforce"],
    [/^app\.slack\.com$/, "app.slack.com"],
  ]
  const host = location.hostname.replace(/^www\./, "")
  let adapter = null
  let prefs = null
  let lastUrl = ""
  let found = null
  let root = null
  let chipEl = null
  let cardEl = null
  let menuEl = null
  let fabEl = null

  function siteId() {
    for (const [re, id] of SITE_IDS) if (re.test(host)) return id
    return prefs && (prefs.added || []).includes(host) ? host : null
  }

  function allowed() {
    const id = siteId()
    return Boolean(prefs && prefs.consentAt && id && (prefs.sites || {})[id] !== false)
  }

  function send(message) {
    return new Promise((resolve) => {
      try {
        chrome.runtime.sendMessage(message, (res) => resolve(chrome.runtime.lastError ? { ok: false } : res || { ok: false }))
      } catch {
        resolve({ ok: false })
      }
    })
  }

  function el(tag, cls, ...children) {
    const node = document.createElement(tag)
    if (cls) node.className = cls
    for (const c of children) if (c != null) node.append(c)
    return node
  }

  function initials(name) {
    const w = String(name || "").trim().split(/\s+/).filter(Boolean)
    return (w.length > 1 ? w[0][0] + w[w.length - 1][0] : (w[0] || "?").slice(0, 2)).toUpperCase()
  }

  /** The Gravitre two-bar mark (same geometry as ui.js), so it needs nothing from the page. */
  function mark(size) {
    const ns = "http://www.w3.org/2000/svg"
    const svg = document.createElementNS(ns, "svg")
    svg.setAttribute("viewBox", "0 0 640 367")
    svg.setAttribute("width", String(size))
    svg.setAttribute("height", String(Math.round(size * 0.57)))
    svg.setAttribute("aria-hidden", "true")
    svg.setAttribute("fill", "currentColor")
    for (const y of [0, 207]) {
      const p = document.createElementNS(ns, "path")
      p.setAttribute("d", "M6 160C1 160-2 156 1 152L59 72C91 27 138 0 186 0H628C636 0 640 6 635 13L576 94C543 137 498 160 450 160Z")
      if (y) p.setAttribute("transform", `translate(0 ${y})`)
      svg.appendChild(p)
    }
    return svg
  }

  function dark() {
    if (prefs?.theme === "dark") return true
    if (prefs?.theme === "light") return false
    return Boolean(window.matchMedia?.("(prefers-color-scheme: dark)").matches)
  }

  function ensureRoot() {
    if (root && root.isConnected) return root
    root = el("div", "gvx-root")
    root.id = "gravitre-root"
    document.documentElement.appendChild(root)
    return root
  }

  function applyTheme() {
    if (root) root.classList.toggle("gvx-dark", dark())
  }

  /** Text the person can see, leaving out anything typed into forms or editors. */
  function visibleText(limit = 6000) {
    const out = []
    let size = 0
    const walker = document.createTreeWalker(document.body || document.documentElement, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        const p = node.parentElement
        if (!p || p.closest("script,style,noscript,input,textarea,select,[contenteditable=''],[contenteditable='true'],[aria-hidden='true'],#gravitre-root,.gvx-chip")) return NodeFilter.FILTER_REJECT
        if (!node.nodeValue.trim()) return NodeFilter.FILTER_SKIP
        return NodeFilter.FILTER_ACCEPT
      },
    })
    while (walker.nextNode() && size < limit) {
      const node = walker.currentNode
      const p = node.parentElement
      if (p.offsetParent === null && getComputedStyle(p).position !== "fixed") continue
      const t = node.nodeValue.replace(/\s+/g, " ").trim()
      out.push(t)
      size += t.length + 1
    }
    return out.join(" ").slice(0, limit)
  }

  function context() {
    let ctx = {}
    try {
      ctx = (adapter && adapter.extract()) || {}
    } catch {
      ctx = {}
    }
    return { ...ctx, pageTitle: document.title }
  }

  function kind() {
    return (adapter && adapter.kind) || "page"
  }

  /* -------------------------------------------------------------- */
  /* Card                                                            */
  /* -------------------------------------------------------------- */

  function closeCard() {
    cardEl?.remove()
    cardEl = null
  }

  function openPanel(draft) {
    closeCard()
    closeMenu()
    void send({ type: "OPEN_SIDE_PANEL", draft: draft || null })
  }

  function showCard(anchor) {
    closeMenu()
    if (cardEl) return closeCard()
    const c = context()
    const name = c.fullName || c.company || ""
    if (!name) return openPanel()
    const line = [c.title, c.fullName ? c.company : null].filter(Boolean).join(" · ")
    const rows = el("div", "gvx-rows")
    const fill = () => {
      rows.replaceChildren()
      if (!found) return rows.append(el("div", "gvx-sub", "Checking your connected apps…"))
      if (found.error) return rows.append(el("div", "gvx-sub", "Couldn't check your connected apps"))
      if (!found.items.length) return rows.append(el("div", "gvx-sub", "Not in your connected apps yet"))
      for (const it of found.items) rows.append(el("div", "gvx-row", el("span", "gvx-logo", it.short), el("span", "gvx-grow", it.label)))
    }
    fill()
    const ask = el("button", "gvx-btn gvx-btn-p", "Ask about this")
    ask.addEventListener("click", () => openPanel(c.fullName ? `What do we know about ${c.fullName}?` : `What do we know about ${name}?`))
    const panel = el("button", "gvx-btn", "Open in side panel")
    panel.addEventListener("click", () => openPanel())
    cardEl = el(
      "div",
      "gvx-card",
      el("div", "gvx-head", el("span", "gvx-av", initials(name)), el("div", "gvx-grow", el("div", "gvx-name", name), line ? el("div", "gvx-sub", line) : null)),
      rows,
      el("div", "gvx-actions", ask, panel),
      el("div", "gvx-foot", "Only you see this. Gravitre reads this page when you ask."),
    )
    cardEl.setAttribute("role", "dialog")
    cardEl.setAttribute("aria-label", `Gravitre: ${name}`)
    ensureRoot().appendChild(cardEl)
    const r = (anchor || fabEl)?.getBoundingClientRect()
    if (r) {
      const w = 260
      const left = Math.min(window.innerWidth - w - 12, Math.max(12, anchor ? r.right + 8 : r.right - w))
      const top = anchor ? Math.min(window.innerHeight - 200, Math.max(12, r.top - 12)) : Math.max(12, r.top - 190)
      cardEl.style.left = `${left}px`
      cardEl.style.top = `${top}px`
    }
    cardEl.__fill = fill
    if (!found) void lookup()
  }

  /* -------------------------------------------------------------- */
  /* Lookup in connected apps (only with "Detect automatically" on)   */
  /* -------------------------------------------------------------- */

  const SHORT = { hubspot: "HS", apollo: "AP", salesforce: "SF", gmail: "GM", slack: "SL" }
  const APP = { hubspot: "HubSpot", apollo: "Apollo", salesforce: "Salesforce" }

  async function lookup() {
    const c = context()
    if (!(c.fullName || c.email || c.company)) return
    const url = location.href
    const res = await send({ type: "ENRICH", pageUrl: url, pageContext: c })
    if (location.href !== url) return
    if (!res.ok) found = { error: true, items: [] }
    else {
      const items = []
      for (const m of res.result?.matches || []) {
        if (!m?.success || m.confidenceLabel !== "matched") continue
        const app = String(m.action || "").split(".")[0]
        if (items.some((i) => i.app === app)) continue
        const what = String(m.action).includes("organizations") ? "company" : "contact"
        items.push({ app, short: SHORT[app] || app.slice(0, 2).toUpperCase(), label: `${APP[app] || app} ${what}` })
      }
      found = { items }
    }
    cardEl?.__fill?.()
    placeChip()
  }

  /** "In CRM" next to the name once a connected app has this person or company. */
  function placeChip() {
    chipEl?.remove()
    chipEl = null
    if (!found || !found.items.length || !adapter?.anchor) return
    let anchor = null
    try {
      anchor = adapter.anchor()
    } catch {
      anchor = null
    }
    if (!anchor) return
    chipEl = el("button", "gvx-chip", mark(10), "In CRM")
    chipEl.type = "button"
    chipEl.title = found.items.map((i) => i.label).join(", ")
    chipEl.addEventListener("click", (e) => {
      e.preventDefault()
      e.stopPropagation()
      showCard(chipEl)
    })
    anchor.insertAdjacentElement("afterend", chipEl)
  }

  /* -------------------------------------------------------------- */
  /* Floating button                                                  */
  /* -------------------------------------------------------------- */

  function closeMenu() {
    menuEl?.remove()
    menuEl = null
  }

  async function savePrefs(patch) {
    const { gvPrefs } = await chrome.storage.local.get("gvPrefs")
    await chrome.storage.local.set({ gvPrefs: { ...(gvPrefs || {}), ...patch } })
  }

  function showMenu() {
    if (menuEl) return closeMenu()
    closeCard()
    const item = (label, run, hint) => {
      const b = el("button", "gvx-mi", el("span", "gvx-grow", label), hint ? el("span", "gvx-kbd", hint) : null)
      b.addEventListener("click", () => {
        closeMenu()
        run()
      })
      return b
    }
    const c = context()
    const name = c.fullName || c.company
    menuEl = el(
      "div",
      "gvx-menu",
      item("Open side panel", () => openPanel(), "Alt G"),
      name ? item(`About ${name}`, () => showCard(null)) : null,
      item(`Hide on ${host}`, () => void savePrefs({ hiddenHosts: [...new Set([...(prefs.hiddenHosts || []), host])] })),
      item("Hide everywhere", () => void savePrefs({ floating: false })),
      el("div", "gvx-hint", "Drag the button to move it"),
    )
    menuEl.setAttribute("role", "menu")
    ensureRoot().appendChild(menuEl)
    const r = fabEl.getBoundingClientRect()
    menuEl.style.left = `${Math.max(12, Math.min(window.innerWidth - 232, r.right - 220))}px`
    menuEl.style.top = `${Math.max(12, r.top - menuEl.offsetHeight - 8)}px`
  }

  async function placeFab() {
    const show = allowed() && prefs.floating !== false && !(prefs.hiddenHosts || []).includes(host)
    if (!show) {
      fabEl?.remove()
      fabEl = null
      closeMenu()
      return
    }
    if (fabEl && fabEl.isConnected) return
    fabEl = el("button", "gvx-fab", mark(16))
    fabEl.type = "button"
    fabEl.setAttribute("aria-label", "Gravitre")
    fabEl.title = "Gravitre"
    const { gvFab } = await chrome.storage.local.get("gvFab")
    const pos = gvFab && gvFab[host]
    if (pos) {
      fabEl.style.right = `${pos.right}px`
      fabEl.style.bottom = `${pos.bottom}px`
    }
    let drag = null
    fabEl.addEventListener("pointerdown", (e) => {
      drag = { x: e.clientX, y: e.clientY, right: parseFloat(getComputedStyle(fabEl).right), bottom: parseFloat(getComputedStyle(fabEl).bottom), moved: false }
      fabEl.setPointerCapture(e.pointerId)
    })
    fabEl.addEventListener("pointermove", (e) => {
      if (!drag) return
      const dx = e.clientX - drag.x
      const dy = e.clientY - drag.y
      if (!drag.moved && Math.abs(dx) + Math.abs(dy) < 4) return
      drag.moved = true
      closeMenu()
      fabEl.style.right = `${Math.max(4, Math.min(window.innerWidth - 40, drag.right - dx))}px`
      fabEl.style.bottom = `${Math.max(4, Math.min(window.innerHeight - 40, drag.bottom - dy))}px`
    })
    fabEl.addEventListener("pointerup", async () => {
      const d = drag
      drag = null
      if (!d) return
      if (!d.moved) return showMenu()
      const stored = (await chrome.storage.local.get("gvFab")).gvFab || {}
      stored[host] = { right: parseFloat(fabEl.style.right), bottom: parseFloat(fabEl.style.bottom) }
      await chrome.storage.local.set({ gvFab: stored })
    })
    fabEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault()
        showMenu()
      }
    })
    ensureRoot().appendChild(fabEl)
  }

  /* -------------------------------------------------------------- */
  /* Lifecycle                                                        */
  /* -------------------------------------------------------------- */

  async function refresh() {
    const stored = (await chrome.storage.local.get("gvPrefs")).gvPrefs || {}
    prefs = { floating: true, hiddenHosts: [], detect: {}, sites: {}, added: [], ...stored }
    applyTheme()
    if (!allowed()) {
      fabEl?.remove()
      chipEl?.remove()
      closeCard()
      closeMenu()
      fabEl = chipEl = null
      return
    }
    await placeFab()
    applyTheme()
  }

  /** Called on load and whenever a single-page app changes the address. */
  function onPage() {
    if (location.href === lastUrl) return
    lastUrl = location.href
    found = null
    chipEl?.remove()
    chipEl = null
    closeCard()
    if (!allowed() || !adapter || (prefs.detect || {})[kind()] === false) return
    if (adapter.auto && adapter.auto()) setTimeout(() => void lookup(), 1200)
  }

  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== "local" || !changes.gvPrefs) return
    void refresh().then(() => {
      if (found) return
      lastUrl = ""
      onPage()
    })
  })

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg?.type === "GV_PAGE_CONTEXT") {
      if (!allowed()) sendResponse({ ok: false, off: true })
      else sendResponse({ ok: true, kind: kind(), context: context(), text: visibleText(), title: document.title, url: location.href })
      return
    }
    if (msg?.type === "GV_SELECTION") {
      if (!allowed()) return sendResponse({ ok: false, off: true })
      const sel = window.getSelection()
      const node = sel && sel.anchorNode && (sel.anchorNode.nodeType === 1 ? sel.anchorNode : sel.anchorNode.parentElement)
      const inForm = node && node.closest("input,textarea,[contenteditable=''],[contenteditable='true']")
      sendResponse({ ok: true, text: inForm ? "" : String(sel || "").slice(0, 4000) })
      return
    }
    if (msg?.type === "OPEN_OVERLAY" && allowed()) showCard(null)
  })

  document.addEventListener(
    "mousedown",
    (e) => {
      if (root && !root.contains(e.target) && e.target !== chipEl) {
        closeCard()
        closeMenu()
      }
    },
    true,
  )
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeCard()
      closeMenu()
    }
  })
  window.matchMedia?.("(prefers-color-scheme: dark)").addEventListener?.("change", applyTheme)

  window.__gravitre = {
    /** { kind: "people"|"company"|"crm"|"email", extract(): {...}, anchor?(): Element, auto?(): boolean } */
    register(def) {
      adapter = def
      lastUrl = ""
      void refresh().then(onPage)
    },
  }

  void refresh().then(onPage)
  setInterval(onPage, 1000)
})()
