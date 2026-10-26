/* The side panel: Ask, Approvals, Activity, Settings and the first-run consent. */
const headEl = document.getElementById("head")
const tabsEl = document.getElementById("tabs")
const bandEl = document.getElementById("band")
const bodyEl = document.getElementById("body")
const footEl = document.getElementById("foot")

const state = {
  ready: false,
  signedIn: false,
  expired: false,
  noAccess: false,
  offline: false,
  session: null,
  profile: {},
  orgId: "",
  prefs: { ...GV_DEFAULT_PREFS },
  caps: null,
  agents: [],
  view: "ask",
  back: "ask",
  approvals: [],
  approvalsAt: 0,
  open: null,
  rejecting: null,
  hidden: new Set(),
  jobs: null,
  jobsError: null,
  messages: [],
  conversationId: null,
  sending: false,
  tab: null,
  page: null,
  pageOff: false,
  enrich: null,
  workflows: [],
  draft: "",
  attach: "",
  mode: "text",
  voice: { status: "idle", heard: "", error: "" },
  error: null,
}

const canApprove = () => !state.caps || state.caps.includes("approve_writes")
const agent = () => state.agents.find((a) => a.id === state.prefs.agentId) || state.agents[0] || null
const agentName = () => agent()?.name || "Gravitre"
const agentIdentity = () => (agent() ? gvIdentity(state.agents, agent().name, agent().id) : gvIdentity([], "Gravitre"))
const web = (path) => void gvSend({ type: "OPEN_APP", path })

function errorLine(text, retry) {
  return h("div", { class: "err", role: "alert" }, gvIcon("alert", 14), h("span", { class: "grow" }, text), retry ? h("button", { class: "link", onclick: retry }, "Try again") : null)
}

/* ------------------------------------------------------------------ */
/* Shell                                                               */
/* ------------------------------------------------------------------ */

function renderHead() {
  if (state.view === "settings") {
    gvSet(headEl, 
      h("button", { class: "ib", "aria-label": "Back", onclick: () => setView(state.back || "ask") }, gvIcon("back")),
      h("span", { class: "strong", style: { fontSize: "14px" } }, "Settings"),
      h("span", { class: "grow" }),
      h("span", { class: "sub xs" }, "This browser only"),
    )
    return
  }
  if (state.view === "consent") {
    gvSet(headEl, gvMarkTile(22), h("span", { class: "strong" }, "Gravitre"), h("span", { class: "grow" }), state.signedIn ? null : h("span", { class: "sub xs" }, "Step 1 of 2"))
    return
  }
  if (!state.signedIn || state.noAccess) {
    gvSet(headEl, gvMarkTile(22), state.profile.orgName ? h("span", { class: "row strong", style: { gap: "6px", fontSize: "12px" } }, gvWsTile(state.profile.orgName, 18), state.profile.orgName) : null, h("span", { class: "grow" }))
    return
  }
  const who = agent()
  const agentBtn = h(
    "button",
    { class: "hbtn", "aria-haspopup": "menu", title: "Choose an agent" },
    gvAgentAvatar(agentIdentity(), 18),
    h("span", { class: "ellipsis" }, who ? who.name : "Agent"),
    gvIcon("chev", 12),
  )
  agentBtn.addEventListener("click", () => agentMenu(agentBtn))
  const more = h("button", { class: "ib", "aria-label": "More", "aria-haspopup": "menu" }, gvIcon("more"))
  more.addEventListener("click", () =>
    gvMenu(
      more,
      [
        { label: "Settings", icon: gvIcon("gear", 14), run: () => setView("settings") },
        { label: "Open Gravitre", icon: gvIcon("ext", 14), run: () => web("/home") },
        { label: "Sign out", icon: gvIcon("logout", 14), run: signOut },
      ],
      { right: true },
    ),
  )
  gvSet(headEl, 
    gvWorkspaceButton(state.profile.orgName, state.profile.organizations, state.orgId, switchOrg),
    agentBtn,
    h("span", { class: "grow" }),
    h("button", { class: "ib", "aria-label": "New conversation", title: "New conversation", onclick: newChat }, gvIcon("edit")),
    more,
  )
}

function agentMenu(anchor) {
  if (!state.agents.length) return
  gvMenu(
    anchor,
    [{ header: "Ask an agent" }].concat(
      state.agents.map((a) => {
        const id = gvIdentity(state.agents, a.name, a.id)
        return { label: a.name, hint: id.dept.label, icon: gvAgentAvatar(id, 18), on: a.id === agent()?.id, run: () => void pickAgent(a.id) }
      }),
    ),
  )
}

async function pickAgent(id) {
  state.prefs = await gvSavePrefs({ agentId: id })
  renderAll()
}

function renderTabs() {
  const show = state.signedIn && !state.noAccess && ["ask", "approvals", "activity"].includes(state.view)
  tabsEl.classList.toggle("hidden", !show)
  if (!show) return
  const n = state.approvals.filter((a) => !state.hidden.has(a.id)).length
  const items = [
    ["ask", "Ask"],
    ["approvals", "Approvals"],
    ["activity", "Activity"],
  ]
  gvSet(tabsEl, 
    h(
      "div",
      { class: "seg", role: "tablist" },
      items.map(([key, label]) =>
        h(
          "button",
          { role: "tab", "aria-selected": state.view === key ? "true" : "false", class: state.view === key ? "on" : "", onclick: () => setView(key) },
          label,
          key === "approvals" && n ? h("span", { class: "n" }, String(n)) : null,
        ),
      ),
    ),
  )
}

/** "Using this page" whenever page content goes with the question. */
function renderBand() {
  const show = state.signedIn && state.view === "ask" && state.page && state.mode === "text"
  const showVoice = state.signedIn && state.view === "ask" && state.page && state.mode === "voice"
  bandEl.classList.toggle("hidden", !(show || showVoice))
  if (!(show || showVoice)) return
  if (state.pageOff) {
    bandEl.style.background = "var(--s2)"
    bandEl.style.color = "var(--t3)"
    gvSet(bandEl, h("span", { class: "grow" }, `Not using this page · ${state.page.host}`), h("button", { class: "link", style: { fontSize: "11px" }, onclick: () => usePage(true) }, "Use page"))
    return
  }
  bandEl.style.background = ""
  bandEl.style.color = ""
  gvSet(bandEl, 
    h("span", { class: "dot", style: { background: "var(--ok)" } }),
    h("span", { class: "grow ellipsis" }, `Using this page · ${state.page.host}`),
    h("button", { class: "mlink", style: { fontSize: "11px", color: "inherit" }, onclick: () => usePage(false) }, "Stop"),
  )
}

function usePage(on) {
  state.pageOff = !on
  renderAll()
}

function setView(view) {
  if (view === "settings" && state.view !== "settings") state.back = state.view === "consent" ? "ask" : state.view
  state.view = view
  state.error = null
  if (view !== "ask") stopVoice()
  renderAll()
  if (view === "approvals") void loadApprovals()
  if (view === "activity") void loadJobs()
}

function renderAll() {
  gvApplyTheme(state.prefs.theme)
  renderHead()
  renderTabs()
  renderBand()
  footEl.classList.add("hidden")
  footEl.style.padding = ""
  gvSet(footEl)
  if (!state.ready) return gvSet(bodyEl, h("div", { class: "skel" }), h("div", { class: "skel", style: { height: "120px" } }))
  if (state.view === "consent") return renderConsent()
  if (state.view === "settings") return renderSettings()
  if (state.offline) return renderOffline()
  if (!state.signedIn) return renderSignedOut()
  if (state.noAccess) return renderNoAccess()
  if (state.view === "approvals") return renderApprovals()
  if (state.view === "activity") return renderActivity()
  return state.mode === "voice" ? renderVoice() : renderAsk()
}

/* ------------------------------------------------------------------ */
/* Signed out, expired, no access, offline                              */
/* ------------------------------------------------------------------ */

function stateCard(icon, title, text, ...actions) {
  return h(
    "div",
    { class: "state fade", style: { position: "relative" } },
    h("span", { class: "ibox", style: { background: "var(--s3)", color: "var(--t2)" } }, gvIcon(icon, 15)),
    h("h1", null, title),
    h("span", { class: "sub", style: { color: "var(--t2)" } }, text),
    h("div", { class: "row" }, ...actions),
  )
}

function renderSignedOut() {
  if (state.expired) {
    gvSet(bodyEl, 
      stateCard("lock", "Your session expired", "Sign in again to pick up where you left off. Your conversations are saved.", h("button", { class: "btn btn-p btn-block", onclick: () => void gvSend({ type: "OPEN_CONNECT" }) }, "Sign in again")),
    )
    return
  }
  gvSet(bodyEl, 
    h(
      "div",
      { class: "stack fade", style: { alignItems: "center", textAlign: "center", gap: "12px", padding: "48px 16px" } },
      gvMarkTile(44),
      h("span", { style: { fontSize: "18px", fontWeight: "600" } }, "Gravitre in your browser"),
      h("span", { class: "sub", style: { fontSize: "13px", color: "var(--t2)" } }, "Ask about any page, run Plays and approve requests without switching tabs."),
      h("button", { class: "btn btn-p btn-lg btn-block", onclick: () => void gvSend({ type: "OPEN_CONNECT" }) }, "Connect Gravitre"),
      h("span", { class: "sub xs" }, "Opens gravitre.app to sign in. Works with your company's single sign-on."),
      h("button", { class: "mlink", onclick: () => web("/get-started") }, "New to Gravitre? Create a workspace ↗"),
    ),
  )
}

function renderNoAccess() {
  const others = (state.profile.organizations || []).filter((o) => o.id !== state.orgId)
  const btn = h("button", { class: "btn btn-p btn-sm" }, "Switch workspace")
  btn.addEventListener("click", () => {
    if (!others.length) return void gvSend({ type: "OPEN_CONNECT" })
    gvMenu(btn, others.map((o) => ({ label: o.name || "Workspace", icon: gvWsTile(o.name || "W", 16), run: () => switchOrg(o.id) })))
  })
  gvSet(bodyEl, stateCard("user", `You don't have access to ${(state.profile.orgName || "this workspace").replace(/\.$/, "")}.`, "Your account isn't a member of this workspace. Ask an admin to add you, or switch to another workspace.", btn))
}

function renderOffline() {
  gvSet(bodyEl, 
    h("div", { class: "note fade" }, gvIcon("wifioff", 14), h("span", null, "You're offline. We'll reconnect on our own.")),
    h("span", { class: "sub xs" }, "Asking and approving are paused until you're back online."),
  )
}

/* ------------------------------------------------------------------ */
/* First-run consent                                                    */
/* ------------------------------------------------------------------ */

function list(items, icon, color) {
  return h(
    "div",
    { class: "card rows" },
    items.map((t) => h("div", { class: "srow", style: { fontSize: "12px", minHeight: "34px" } }, h("span", { style: { color, display: "inline-flex" } }, gvIcon(icon, 14)), t)),
  )
}

function siteRows() {
  const p = state.prefs
  const rows = GV_SITES.map((s) => ({ id: s.id, label: s.label, added: false })).concat(p.added.map((host) => ({ id: host, label: host, added: true })))
  return rows.map((s) =>
    h(
      "div",
      { class: "srow" },
      h("span", { class: "ibox", style: { width: "20px", height: "20px", background: "var(--s3)", color: "var(--t2)" } }, gvIcon("globe", 12)),
      h("span", { class: "grow ellipsis" }, s.label),
      s.added ? h("button", { class: "ib", "aria-label": `Remove ${s.label}`, title: "Remove", onclick: () => void removeSite(s.id) }, gvIcon("x", 14)) : null,
      gvToggle(gvSiteOn(p, s.id), `Allow Gravitre on ${s.label}`, (on) => void gvSavePrefs({ sites: { ...state.prefs.sites, [s.id]: on } }).then((np) => (state.prefs = np))),
    ),
  )
}

function renderConsent() {
  gvSet(bodyEl, 
    h(
      "div",
      { class: "stack fade", style: { gap: "12px" } },
      h("span", { style: { fontSize: "18px", fontWeight: "600" } }, "Before you start"),
      h("span", { class: "sub", style: { fontSize: "13px", color: "var(--t2)" } }, "Gravitre reads a page only when you ask about it, and only on sites you allow."),
      h("span", { class: "strong xs" }, "When you ask, Gravitre reads"),
      list(["The current tab's address and title", "The text you can see on the page", "Text you select and choose to attach"], "check", "var(--br)"),
      h("span", { class: "strong xs" }, "Gravitre never reads"),
      list(["Passwords or anything you type into forms", "Other tabs or your browsing history", "Pages on sites you turn off"], "x", "var(--t3)"),
      h("span", { class: "strong xs" }, "Turn on for these sites"),
      h("div", { class: "card rows" }, siteRows()),
      h("span", { class: "sub xs" }, `You'll see "Using this page" whenever page content is sent.`),
    ),
  )
  footEl.classList.remove("hidden")
  gvSet(footEl, 
    h(
      "div",
      { class: "stack", style: { gap: "8px" } },
      h(
        "button",
        {
          class: "btn btn-p btn-block",
          onclick: async () => {
            state.prefs = await gvSavePrefs({ consentAt: new Date().toISOString() })
            setView("ask")
            void readPage()
          },
        },
        "Continue",
      ),
      h("button", { class: "mlink", style: { alignSelf: "center" }, onclick: () => web("/privacy") }, "How Gravitre handles your data ↗"),
    ),
  )
}

/* ------------------------------------------------------------------ */
/* Settings                                                             */
/* ------------------------------------------------------------------ */

async function addSite(raw) {
  const host = gvHostOf(/^https?:\/\//.test(raw) ? raw : `https://${raw.trim()}`)
  if (!/^[a-z0-9.-]+\.[a-z]{2,}$/i.test(host)) throw new Error("Enter a site like app.hubspot.com")
  if (gvSiteIdFor(host, state.prefs)) throw new Error(`${host} is already on the list`)
  // Chrome asks the person here; this has to stay in the click that started it.
  const granted = await chrome.permissions.request({ origins: [`https://${host}/*`] })
  if (!granted) throw new Error("Chrome didn't allow Gravitre on that site")
  const res = await gvSend({ type: "REGISTER_SITE", host })
  if (!res.ok) throw new Error(res.error || "Couldn't add that site")
  state.prefs = await gvSavePrefs({ added: [...state.prefs.added, host], sites: { ...state.prefs.sites, [host]: true } })
}

async function removeSite(host) {
  await gvSend({ type: "REGISTER_SITE", host, remove: true })
  const sites = { ...state.prefs.sites }
  delete sites[host]
  state.prefs = await gvSavePrefs({ added: state.prefs.added.filter((x) => x !== host), sites })
  renderAll()
}

function group(title, ...children) {
  return h("section", { class: "stack", style: { gap: "6px" } }, title ? h("span", { class: "strong xs", style: { padding: "0 2px" } }, title) : null, ...children)
}

function renderSettings() {
  const p = state.prefs
  const adding = h("div", { class: "srow hidden", style: { gap: "6px" } })
  const field = h("input", { class: "field", placeholder: "app.hubspot.com", "aria-label": "Site address", style: { height: "30px" } })
  const msg = h("span", { class: "sub xs" })
  const submit = async () => {
    msg.textContent = ""
    try {
      await addSite(field.value)
      renderAll()
    } catch (err) {
      msg.textContent = err instanceof Error ? err.message : String(err)
    }
  }
  field.addEventListener("keydown", (e) => {
    if (e.key === "Enter") void submit()
  })
  gvAdd(adding, h("div", { class: "stack grow", style: { gap: "4px" } }, field, msg), h("button", { class: "btn btn-sm btn-p", onclick: submit }, "Add"))

  const hiddenList = h(
    "div",
    { class: "hidden rows" },
    p.hiddenHosts.map((host) =>
      h(
        "div",
        { class: "srow" },
        h("span", { class: "grow ellipsis" }, host),
        h(
          "button",
          {
            class: "btn btn-sm",
            onclick: async () => {
              state.prefs = await gvSavePrefs({ hiddenHosts: state.prefs.hiddenHosts.filter((x) => x !== host) })
              renderAll()
            },
          },
          "Show",
        ),
      ),
    ),
  )
  const version = chrome.runtime.getManifest?.().version || ""
  const email = state.profile.email || ""
  const role = state.session?.role ? gvTitleCase(state.session.role) : ""

  gvSet(bodyEl, 
    group(
      "Allowed sites",
      h(
        "div",
        { class: "card rows" },
        siteRows(),
        h(
          "button",
          {
            class: "srow",
            style: { border: 0, background: "transparent", width: "100%", cursor: "pointer", color: "var(--sig)", fontWeight: "500" },
            onclick: () => {
              adding.classList.toggle("hidden")
              field.focus()
            },
          },
          gvIcon("plus", 14),
          "Add a site",
        ),
        adding,
      ),
    ),
    group(
      "Detect automatically",
      h(
        "div",
        { class: "card", style: { padding: "10px 12px", display: "flex", flexWrap: "wrap", gap: "10px 16px" } },
        GV_DETECT.map((d) =>
          h(
            "label",
            { class: "row xs", style: { gap: "6px" } },
            gvCheck(p.detect[d.id] !== false, d.label, (on) => void gvSavePrefs({ detect: { ...state.prefs.detect, [d.id]: on } }).then((np) => (state.prefs = np))),
            d.label,
          ),
        ),
      ),
    ),
    group(
      null,
      h(
        "div",
        { class: "card rows" },
        h(
          "div",
          { class: "srow" },
          h(
            "span",
            { class: "grow stack" },
            "Floating button",
            p.hiddenHosts.length
              ? h(
                  "button",
                  { class: "link", style: { alignSelf: "flex-start", fontSize: "11px" }, onclick: () => hiddenList.classList.toggle("hidden") },
                  `Hidden on ${p.hiddenHosts.length} ${p.hiddenHosts.length === 1 ? "site" : "sites"} · Manage`,
                )
              : null,
          ),
          gvToggle(p.floating, "Floating button", (on) => void gvSavePrefs({ floating: on }).then((np) => (state.prefs = np))),
        ),
        hiddenList,
      ),
    ),
    group(
      "Theme",
      h(
        "div",
        { class: "seg", role: "radiogroup", "aria-label": "Theme" },
        ["system", "light", "dark"].map((t) =>
          h(
            "button",
            {
              class: p.theme === t ? "on" : "",
              role: "radio",
              "aria-checked": p.theme === t ? "true" : "false",
              onclick: async () => {
                state.prefs = await gvSavePrefs({ theme: t })
                renderAll()
              },
            },
            gvTitleCase(t),
          ),
        ),
      ),
    ),
    state.signedIn
      ? h(
          "div",
          { class: "card", style: { padding: "10px 12px" } },
          h(
            "div",
            { class: "row" },
            gvAvatar(state.profile.name || email, 30),
            h("span", { class: "stack grow" }, h("span", { class: "ellipsis" }, email), h("span", { class: "sub xs" }, [state.profile.orgName, role].filter(Boolean).join(" · "))),
            h("button", { class: "btn btn-sm", onclick: signOut }, "Sign out"),
          ),
        )
      : null,
    h("button", { class: "mlink", style: { alignSelf: "flex-start" }, onclick: () => web("/settings") }, "Manage account and workspace on web ↗"),
    h("span", { class: "sub xs" }, version ? `Version ${version}` : ""),
  )
}

/* ------------------------------------------------------------------ */
/* Ask                                                                  */
/* ------------------------------------------------------------------ */

async function readPage() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
  state.tab = tab || null
  const url = tab?.url || ""
  const host = gvHostOf(url)
  const siteId = gvSiteIdFor(host, state.prefs)
  const prevUrl = state.page?.url
  state.page = null
  if (state.prefs.consentAt && siteId && gvSiteOn(state.prefs, siteId) && /^https:/.test(url)) {
    const ctx = await gvPageContext(tab.id)
    if (ctx) state.page = { url, host, title: tab.title || host, kind: ctx.kind || "page", context: ctx.context || {}, text: ctx.text || "" }
  }
  if (state.page?.url !== prevUrl) {
    state.enrich = null
    state.pageOff = false
    if (state.page && state.signedIn) void enrichPage()
  }
  if (state.ready) renderAll()
}

async function enrichPage() {
  const page = state.page
  const c = page?.context || {}
  if (!page || !(c.fullName || c.email || c.company) || state.prefs.detect[page.kind] === false) return
  const res = await gvSend({ type: "ENRICH", pageUrl: page.url, pageContext: c })
  if (state.page?.url !== page.url) return
  state.enrich = res.ok ? res.result : { error: res.error }
  if (state.view === "ask" && state.mode === "text" && !state.messages.length) renderAll()
}

const KIND_LABEL = { people: "Person", company: "Company", crm: "CRM record", email: "Email thread", page: "Page" }

function pageContextCard() {
  const p = state.page
  const c = p.context
  const name = c.fullName || c.company || c.subject || p.title
  const line = [c.title, c.fullName ? c.company : null].filter(Boolean).join(" · ")
  const body = h("div", { class: "stack", style: { gap: "8px", padding: "0 12px 12px" } })
  body.appendChild(
    h(
      "div",
      { class: "row", style: { gap: "10px" } },
      c.fullName ? gvPersonAvatar(c.fullName, 30) : h("span", { class: "ibox", style: { background: "var(--s3)" } }, gvIcon("page", 14)),
      h("span", { class: "stack grow" }, h("span", { class: "strong ellipsis" }, name), line ? h("span", { class: "sub xs" }, line) : null),
    ),
  )
  const found = state.enrich && !state.enrich.error ? gvMatches(state.enrich) : []
  if (found.length) {
    body.appendChild(
      h(
        "div",
        { class: "stack", style: { gap: "6px", background: "var(--s2)", borderRadius: "10px", padding: "8px 10px" } },
        found.map((m) => h("span", { class: "row xs", style: { gap: "8px" } }, gvBadge(m.app, 18), h("span", { class: "strong" }, m.label))),
      ),
    )
  } else if (state.enrich?.error) body.appendChild(h("span", { class: "sub xs" }, "Couldn't check your connected apps"))
  else if (state.enrich) body.appendChild(h("span", { class: "sub xs" }, "Not in your connected apps yet"))
  else if (c.fullName || c.company) body.appendChild(h("span", { class: "sub xs" }, state.prefs.detect[p.kind] === false ? "" : "Checking your connected apps…"))
  const chev = gvIcon("chev", 14)
  chev.style.transform = "rotate(180deg)"
  const toggle = h(
    "button",
    {
      class: "row",
      "aria-expanded": "true",
      style: { width: "100%", border: 0, background: "transparent", padding: "10px 12px", cursor: "pointer", textAlign: "left" },
      onclick: () => {
        const open = body.classList.toggle("hidden") === false
        toggle.setAttribute("aria-expanded", open ? "true" : "false")
        chev.style.transform = open ? "rotate(180deg)" : ""
      },
    },
    h("span", { class: "sub xs grow" }, `Page context · ${KIND_LABEL[p.kind] || "Page"}`),
    chev,
  )
  return h("div", { class: "card fade" }, toggle, body)
}

/** Plays that fit this page: the enrich suggestions plus the workspace's Plays. */
function suggestions() {
  const out = []
  for (const s of (state.enrich && state.enrich.suggestions) || []) {
    out.push({ label: s.label, run: () => void proposeAction(s) })
    if (out.length >= 2) break
  }
  for (const w of state.workflows) {
    out.push({ label: w.name, run: () => void proposePlay(w) })
    if (out.length >= 4) break
  }
  return out
}

function chip(label, run) {
  return h("button", { class: "chip", style: { paddingLeft: "8px" }, onclick: run }, h("span", { style: { color: "var(--br)", display: "inline-flex" } }, gvIcon("play", 11)), label)
}

function sourcesLine(src) {
  if (!src) return null
  const used = Array.isArray(src.used) ? src.used : []
  const skipped = (Array.isArray(src.skipped) ? src.skipped : []).reduce((n, s) => n + (Number(s.count) || 0), 0)
  if (!used.length && !skipped) return null
  const apps = []
  for (const u of used) {
    const k = String(u.kind || u.name || "").toLowerCase()
    if (!apps.includes(k)) apps.push(k)
  }
  const n = Number(src.usedCount) || used.length
  const text = [`${n} ${n === 1 ? "source" : "sources"}`, skipped ? `${skipped} left out` : null].filter(Boolean).join(" · ")
  return h(
    "div",
    { class: "row sub xs", style: { gap: "4px" }, title: used.map((u) => u.name).join(", ") },
    apps.slice(0, 3).map((a) => gvBadge(a, 16)),
    h("span", { style: { marginLeft: "4px" } }, text),
  )
}

function planCard(m) {
  const p = m.plan
  const steps = h(
    "div",
    { class: "plan" },
    p.steps.map((s, i) => {
      const app = String(s.action || "").split(".")[0]
      return h("div", { class: "step" }, h("span", { class: "num" }, String(i + 1)), h("span", { class: "grow" }, s.label), app ? gvBadge(app, 16) : null)
    }),
  )
  const actions = h("div", { class: "row", style: { padding: "8px 12px", borderTop: "1px solid var(--bs)" } })
  const status = p.status
  if (status === "staged") {
    gvAdd(actions, 
      h("span", { class: "sub xs grow ellipsis" }, [p.steps.length ? `${p.steps.length} ${p.steps.length === 1 ? "step" : "steps"}` : null, p.approvalNeeded ? "1 approval" : null].filter(Boolean).join(" · ")),
      p.edit ? h("button", { class: "btn btn-sm btn-q", onclick: p.edit }, p.editLabel || "Edit") : null,
      p.approve ? h("button", { class: "btn btn-sm btn-p", disabled: !p.approve, onclick: () => void p.approve() }, p.approveLabel || "Approve plan") : null,
    )
  } else if (status === "running") gvAdd(actions, h("span", { class: "row sub xs grow" }, h("span", { class: "typing" }, h("span"), h("span"), h("span")), "Starting…"))
  else if (status === "waiting") gvAdd(actions, h("span", { class: "row sub xs grow", style: { gap: "6px" } }, gvIcon("clock", 13), `In approvals · waiting on ${p.waitingOn || "Admins"}`), h("button", { class: "link", onclick: () => setView("approvals") }, "View"))
  else if (status === "done") gvAdd(actions, gvPill("done"), h("span", { class: "sub xs grow" }, p.note || ""), p.url ? h("button", { class: "link", onclick: () => web(p.url) }, "Open ↗") : null)
  else if (status === "failed") gvAdd(actions, gvPill("failed"), h("span", { class: "sub xs grow" }, p.note || ""))
  else if (status === "cancelled") gvAdd(actions, h("span", { class: "sub xs grow" }, "Cancelled. Nothing ran."))
  return h(
    "div",
    { class: "card fade" },
    h("div", { class: "stack", style: { padding: "10px 12px 8px" } }, h("span", { class: "sub xs" }, p.kicker || "Plan"), h("span", { class: "strong" }, p.title)),
    p.steps.length ? steps : null,
    p.rows?.length ? h("div", null, p.rows.map(([k, v]) => h("div", { class: "kv" }, h("span", null, k), h("span", { class: "newv" }, v)))) : null,
    actions,
  )
}

function turn(m) {
  if (m.role === "user") {
    return h("div", { class: "stack", style: { gap: "4px", alignItems: "flex-end" } }, m.attach ? h("span", { class: "attach" }, gvIcon("sel", 12), "Selection") : null, h("div", { class: "ubub" }, m.text))
  }
  const id = m.agent || agentIdentity()
  return h(
    "div",
    { class: "turn fade" },
    gvAgentAvatar(id, 22),
    h(
      "div",
      { class: "stack grow", style: { gap: "8px", minWidth: 0 } },
      h("span", { class: "row xs", style: { gap: "6px" } }, h("span", { class: "strong" }, id.name), h("span", { class: "sub xs" }, id.dept.label)),
      m.thinking ? h("span", { class: "typing" }, h("span"), h("span"), h("span")) : null,
      m.text ? h("div", { class: "prose" }, m.text) : null,
      m.error ? errorLine(m.error) : null,
      m.plan ? planCard(m) : null,
      m.handoffUrl ? h("button", { class: "btn btn-sm", style: { alignSelf: "flex-start" }, onclick: () => web(m.handoffUrl) }, "Continue in Gravitre ↗") : null,
      sourcesLine(m.sources),
    ),
  )
}

function renderAsk() {
  const parts = []
  if (state.page && !state.pageOff && !state.messages.length) {
    parts.push(pageContextCard())
    const sugg = suggestions()
    if (sugg.length) parts.push(h("div", { class: "stack", style: { gap: "6px" } }, h("span", { class: "sub xs" }, "Suggested for this page"), h("div", { class: "row", style: { flexWrap: "wrap", gap: "6px" } }, sugg.map((s) => chip(s.label, s.run)))))
  }
  if (!state.messages.length && !(state.page && !state.pageOff)) {
    parts.push(
      h(
        "div",
        { class: "empty" },
        gvAgentAvatar(agentIdentity(), 36),
        h("b", null, `Ask ${agentName()}`),
        h("span", null, "About this page, your accounts or your agents' work. Plans wait for your approval before anything runs."),
      ),
    )
    if (state.workflows.length) parts.push(h("div", { class: "row", style: { flexWrap: "wrap", gap: "6px", justifyContent: "center" } }, state.workflows.slice(0, 3).map((w) => chip(w.name, () => void proposePlay(w)))))
  }
  parts.push(...state.messages.map(turn))
  if (state.error) parts.push(errorLine(state.error))
  gvSet(bodyEl, ...parts)
  bodyEl.scrollTop = bodyEl.scrollHeight
  renderComposer()
}

function commandItems(q) {
  const query = q.toLowerCase()
  const plays = state.workflows.filter((w) => w.name.toLowerCase().includes(query)).slice(0, 4)
  const items = []
  if (plays.length) {
    items.push({ header: state.page ? "Plays for this page" : "Plays" })
    plays.forEach((w) => items.push({ label: w.name, icon: gvIcon("play", 13), run: () => void proposePlay(w) }))
  }
  const pageCmds = state.page && !state.pageOff ? [{ label: "Summarize page", icon: gvIcon("page", 13), run: () => void send("Summarize this page.") }] : []
  const pc = pageCmds.filter((c) => c.label.toLowerCase().includes(query))
  if (pc.length) items.push({ header: "This page" }, ...pc)
  return items
}

function renderComposer() {
  footEl.classList.remove("hidden")
  const ta = h("textarea", { class: "ta", rows: "1", placeholder: `Ask ${agentName()}, / for commands, @ for agents`, "aria-label": "Message" })
  ta.value = state.draft
  const fit = () => {
    ta.style.height = "auto"
    ta.style.height = `${Math.min(140, ta.scrollHeight)}px`
  }
  let menu = null
  const showMenu = () => {
    menu?.remove()
    menu = null
    const v = ta.value
    if (v.startsWith("/")) {
      const items = commandItems(v.slice(1).trim())
      if (!items.length) return
      menu = gvMenu(composer, items, { host: footEl })
      menu.style.top = "auto"
      menu.style.bottom = `${composer.offsetHeight + 14}px`
      menu.style.left = "10px"
      menu.style.right = "10px"
      ta.focus()
    }
  }
  ta.addEventListener("input", () => {
    state.draft = ta.value
    fit()
    if (ta.value === "@") {
      ta.value = ""
      state.draft = ""
      agentMenu(atBtn)
      return
    }
    showMenu()
  })
  ta.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      if (menu && ta.value.startsWith("/")) {
        menu.querySelector(".mi")?.click()
        ta.value = ""
        state.draft = ""
        return
      }
      void send(ta.value)
    }
  })
  const atBtn = h("button", { class: "ib", "aria-label": "Choose an agent", title: "@ for agents" }, h("span", { class: "mono", style: { fontSize: "13px" } }, "@"))
  atBtn.addEventListener("click", () => agentMenu(atBtn))
  const slash = h(
    "button",
    {
      class: "ib",
      "aria-label": "Commands",
      title: "/ for commands",
      onclick: () => {
        ta.value = "/"
        state.draft = "/"
        ta.focus()
        showMenu()
      },
    },
    h("span", { class: "mono", style: { fontSize: "13px" } }, "/"),
  )
  const selBtn = h(
    "button",
    {
      class: `chip${state.attach ? "" : ""}`,
      style: { height: "26px", paddingLeft: "8px", background: state.attach ? "var(--brs)" : "", color: state.attach ? "var(--brk)" : "", borderColor: state.attach ? "transparent" : "" },
      "aria-pressed": state.attach ? "true" : "false",
      title: state.attach ? state.attach.slice(0, 200) : "Attach the text selected on the page",
      onclick: async () => {
        if (state.attach) state.attach = ""
        else {
          const text = await gvSelection(state.tab?.id)
          if (!text) gvToast("Select some text on the page first.")
          state.attach = text.slice(0, 4000)
        }
        renderComposer()
      },
    },
    gvIcon("sel", 13),
    "Selection",
  )
  const mode = h(
    "div",
    { class: "mode", role: "radiogroup", "aria-label": "Mode" },
    h("button", { class: state.mode === "text" ? "on" : "", role: "radio", "aria-checked": state.mode === "text" ? "true" : "false", onclick: () => setMode("text") }, gvIcon("text", 12), "Text"),
    h("button", { class: state.mode === "voice" ? "on" : "", role: "radio", "aria-checked": state.mode === "voice" ? "true" : "false", onclick: () => setMode("voice") }, gvIcon("voice", 12), "Voice"),
  )
  const sendBtn = h("button", { class: "ib send", "aria-label": "Send", disabled: state.sending, onclick: () => void send(ta.value) }, gvIcon("up", 15))
  const composer = h("div", { class: "composer" }, ta, h("div", { class: "row", style: { gap: "4px" } }, atBtn, slash, state.page && !state.pageOff ? selBtn : null, h("span", { class: "grow" }), mode, sendBtn))
  gvSet(footEl, 
    composer,
    h(
      "div",
      { class: "row sub xs", style: { padding: "6px 2px 0" } },
      h("span", { class: "grow" }, "Saved to your conversations"),
      h("button", { class: "mlink xs", onclick: () => web(state.conversationId ? `/ai?c=${encodeURIComponent(state.conversationId)}` : "/ai") }, "Continue on web ↗"),
    ),
  )
  fit()
  if (state.mode === "text") setTimeout(() => ta.focus())
}

function pageContextForChat() {
  if (!state.page || state.pageOff) return { url: null, context: {} }
  const ctx = { ...state.page.context, pageTitle: state.page.title, visibleText: state.page.text.slice(0, 6000) }
  if (state.attach) ctx.selection = state.attach
  return { url: state.page.url, context: ctx }
}

async function send(raw, opts = {}) {
  const text = String(raw || "").trim()
  if (!text || state.sending) return
  state.sending = true
  state.error = null
  state.draft = ""
  const page = pageContextForChat()
  state.messages.push({ role: "user", text, attach: Boolean(state.attach && !state.pageOff) })
  state.attach = ""
  const reply = { role: "assistant", thinking: true, agent: agentIdentity() }
  state.messages.push(reply)
  if (opts.voice) state.voice = { ...state.voice, status: "thinking", you: text }
  renderAll()
  const res = await gvSend({
    type: "CHAT",
    message: text,
    pageUrl: page.url,
    pageContext: page.context,
    conversationId: state.conversationId,
    agentId: agent()?.id || null,
    spokenMode: Boolean(opts.voice),
  })
  reply.thinking = false
  state.sending = false
  if (!res.ok) {
    reply.error = res.offline ? "You're offline. Try again when you're back online." : res.error || "Couldn't reach Gravitre"
    if (res.code === "not_authenticated") return void load()
  } else {
    const r = res.result || {}
    if (r.conversationId) state.conversationId = r.conversationId
    reply.text = String(r.answer || "")
    reply.sources = r.contextSources || null
    if (r.needsHandoff && r.openInGravitreUrl) reply.handoffUrl = r.openInGravitreUrl
    if (r.pendingTask) reply.plan = chatPlan(r.pendingTask)
    if (r.pendingTask) void linkPlanToApproval(reply)
  }
  if (opts.voice) {
    state.voice = { ...state.voice, status: "idle", agentText: reply.text || reply.error || "" }
    if (reply.text) void speak(reply.text)
  }
  renderAll()
}

/** A plan the chat staged: it waits in the approvals queue under this conversation. */
function chatPlan(task) {
  const params = task.params && typeof task.params === "object" ? task.params : {}
  const raw = Array.isArray(params.steps) ? params.steps : Array.isArray(task.steps) ? task.steps : []
  const steps = raw
    .map((s) => (typeof s === "string" ? { label: s } : { label: String(s?.description || s?.title || s?.text || s?.label || s?.action || ""), action: s?.action || s?.invoke_action || null }))
    .filter((s) => s.label)
  const title = String(task.title || task.summary || params.workflow_name || params.title || "Plan waiting for approval")
  return { kicker: params.workflow_name ? `Play · ${params.workflow_name}` : "Plan", title, steps, status: "staged", approvalNeeded: true, edit: () => web(state.conversationId ? `/ai?c=${encodeURIComponent(state.conversationId)}` : "/ai"), editLabel: "Edit" }
}

async function linkPlanToApproval(reply) {
  const res = await gvSend({ type: "LIST_APPROVALS" })
  if (!res.ok) return
  state.approvals = res.approvals.map(gvApproval)
  const hit = state.approvals.find((a) => a.conversationId && a.conversationId === state.conversationId)
  if (hit && reply.plan) {
    if (canApprove()) {
      reply.plan.approve = async () => {
        reply.plan.status = "running"
        renderAll()
        const out = await gvSend({ type: "DECIDE_APPROVAL", id: hit.id, approve: true })
        reply.plan.status = out.ok ? "done" : "failed"
        reply.plan.note = out.ok ? "Approved. The plan is running." : out.error || "Couldn't approve"
        reply.plan.url = out.ok ? "/activity" : null
        renderAll()
      }
    } else {
      reply.plan.status = "waiting"
      reply.plan.waitingOn = gvApprovers(hit)
    }
  }
  renderTabs()
  renderAll()
}

/** Plays: stage the run, then the person confirms with the server's token. */
async function proposePlay(w) {
  if (state.sending) return
  state.view = "ask"
  if (state.mode === "voice") setMode("text")
  state.messages.push({ role: "user", text: `Run ${w.name}` })
  const reply = { role: "assistant", thinking: true, agent: agentIdentity() }
  state.messages.push(reply)
  renderAll()
  const page = pageContextForChat()
  const res = await gvSend({ type: "EXECUTE_WORKFLOW", workflowId: w.id, pageUrl: page.url, parameters: page.url ? { pageContext: page.context } : {} })
  reply.thinking = false
  if (!res.ok) {
    reply.error = res.error || "Couldn't start that Play"
    return renderAll()
  }
  const r = res.result || {}
  const steps = (r.progressSteps || w.progressSteps || []).map((s) => ({ label: String(s.label || s.name || "Step"), action: s.action || null }))
  reply.text = "Here's the plan. Nothing runs until you approve it."
  reply.plan = { kicker: `Play · ${w.name}`, title: r.workflowName || w.name, steps, status: "staged" }
  reply.plan.edit = () => {
    reply.plan.status = "cancelled"
    renderAll()
  }
  reply.plan.editLabel = "Cancel"
  if (r.confirmationToken) {
    reply.plan.approve = async () => {
      reply.plan.status = "running"
      renderAll()
      const out = await gvSend({ type: "EXECUTE_WORKFLOW", confirmationToken: r.confirmationToken, pageUrl: page.url })
      finishPlan(reply.plan, out)
    }
  } else finishPlan(reply.plan, res)
  renderAll()
}

/** Writes the enrich read suggested (create a contact, add to a list): same confirm step. */
async function proposeAction(s) {
  if (state.sending) return
  state.messages.push({ role: "user", text: s.label })
  const reply = { role: "assistant", thinking: true, agent: agentIdentity() }
  state.messages.push(reply)
  renderAll()
  const pageUrl = state.page?.url || null
  const res = await gvSend({ type: "EXECUTE_ACTION", invokeAction: s.invokeAction, params: s.params || {}, pageUrl })
  reply.thinking = false
  if (!res.ok) {
    reply.error = res.error || "Couldn't prepare that"
    return renderAll()
  }
  const r = res.result || {}
  const app = String(s.invokeAction || "").split(".")[0]
  const props = s.params?.properties && typeof s.params.properties === "object" ? { ...s.params, ...s.params.properties } : s.params || {}
  const rows = Object.entries(props)
    .filter(([k]) => k !== "properties")
    .map(([k, v]) => [gvHumanize(k), gvValue(v)])
    .filter(([, v]) => v)
    .slice(0, 6)
  reply.text = s.requiresApproval ? `This changes ${gvAppName(app)}, so it needs your OK first.` : "Confirm and it runs."
  reply.plan = { kicker: gvAppName(app), title: s.label, steps: [], rows, status: "staged", approvalNeeded: s.requiresApproval }
  if (s.note) reply.text += ` ${s.note}`
  if (r.confirmationToken) {
    reply.plan.edit = () => {
      reply.plan.status = "cancelled"
      renderAll()
    }
    reply.plan.editLabel = "Cancel"
    reply.plan.approveLabel = "Approve"
    reply.plan.approve = async () => {
      reply.plan.status = "running"
      renderAll()
      const out = await gvSend({ type: "EXECUTE_ACTION", confirmationToken: r.confirmationToken, pageUrl })
      finishPlan(reply.plan, out)
    }
  } else finishPlan(reply.plan, res)
  renderAll()
}

function finishPlan(plan, out) {
  const r = out.result || {}
  if (!out.ok || r.success === false) {
    plan.status = "failed"
    plan.note = out.error || r.error || "It didn't run."
  } else if (r.approvalRequired || r.status === "pending_approval") {
    plan.status = "waiting"
  } else {
    plan.status = "done"
    plan.note = r.status === "running" || r.queued ? "Running now." : "Done."
    plan.url = r.outcomeUrl || r.businessOutcomeUrl || null
  }
  renderAll()
  void loadApprovals(true)
}

function newChat() {
  stopVoice()
  state.messages = []
  state.conversationId = null
  state.draft = ""
  state.attach = ""
  state.error = null
  setView("ask")
}

/* ------------------------------------------------------------------ */
/* Voice                                                                */
/* ------------------------------------------------------------------ */

let recognition = null
let audio = null
let voiceEnabled = null

function setMode(mode) {
  if (mode === state.mode) return
  state.mode = mode
  if (mode === "voice") {
    state.voice = { status: "idle", heard: "", error: "" }
    if (voiceEnabled == null) void gvSend({ type: "VOICE_STATUS" }).then((r) => (voiceEnabled = Boolean(r.ok && r.enabled)))
    listen()
  } else stopVoice()
  renderAll()
}

function stopVoice() {
  try {
    recognition?.abort()
  } catch {
    /* already stopped */
  }
  recognition = null
  audio?.pause()
  audio = null
  window.speechSynthesis?.cancel()
  if (state.voice.status !== "idle") state.voice = { ...state.voice, status: "idle" }
}

function listen() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition
  if (!SR) {
    state.voice = { ...state.voice, error: "This browser can't listen. Switch to text." }
    return
  }
  audio?.pause()
  window.speechSynthesis?.cancel()
  recognition = new SR()
  recognition.lang = navigator.language || "en-US"
  recognition.interimResults = true
  recognition.continuous = false
  recognition.onresult = (e) => {
    let text = ""
    for (const r of e.results) text += r[0].transcript
    state.voice = { ...state.voice, heard: text }
    if (e.results[e.results.length - 1].isFinal) {
      recognition = null
      void send(text, { voice: true })
    } else renderAll()
  }
  recognition.onerror = (e) => {
    recognition = null
    const blocked = e.error === "not-allowed" || e.error === "service-not-allowed"
    state.voice = { ...state.voice, status: "idle", error: blocked ? "Chrome blocked the microphone for Gravitre." : e.error === "no-speech" ? "" : "Couldn't hear that. Tap to try again." }
    renderAll()
  }
  recognition.onend = () => {
    if (state.voice.status === "listening") {
      state.voice = { ...state.voice, status: "idle" }
      renderAll()
    }
  }
  state.voice = { ...state.voice, status: "listening", heard: "", error: "" }
  try {
    recognition.start()
  } catch {
    recognition = null
  }
}

async function speak(text) {
  state.voice = { ...state.voice, status: "speaking" }
  renderAll()
  const done = () => {
    if (state.mode !== "voice") return
    state.voice = { ...state.voice, status: "idle" }
    renderAll()
  }
  if (voiceEnabled) {
    const res = await gvSend({ type: "VOICE_TTS", text: text.slice(0, 1200), agentId: agent()?.id || null })
    if (res.ok && res.audioBase64) {
      audio = new Audio(`data:${res.contentType || "audio/mpeg"};base64,${res.audioBase64}`)
      audio.onended = done
      audio.play().catch(done)
      return
    }
  }
  if (window.speechSynthesis) {
    const u = new SpeechSynthesisUtterance(text.slice(0, 1200))
    u.onend = done
    window.speechSynthesis.speak(u)
  } else done()
}

function renderVoice() {
  const v = state.voice
  const name = agentName()
  const title = v.status === "listening" ? `${name} is listening…` : v.status === "thinking" ? `${name} is thinking…` : v.status === "speaking" ? `${name} is speaking…` : "Tap the orb to talk"
  const last = [...state.messages].reverse().find((m) => m.role === "assistant" && (m.text || m.error))
  const you = [...state.messages].reverse().find((m) => m.role === "user")
  const orb = h("button", {
    class: `orb${v.status === "listening" ? " listen" : v.status === "speaking" ? " speak" : ""}`,
    "aria-label": v.status === "listening" ? "Stop listening" : "Talk",
    onclick: () => {
      if (v.status === "listening") stopVoice()
      else listen()
      renderAll()
    },
  })
  gvSet(bodyEl, 
    h("div", { class: "row" }, h("span", { class: "grow", style: { fontSize: "14px" } }, title), h("button", { class: "ib", "aria-label": "Switch to text", onclick: () => setMode("text") }, gvIcon("x"))),
    h("div", { class: "stack", style: { alignItems: "center", gap: "18px", padding: "36px 0 12px" } }, orb, h("button", { class: "mlink", onclick: () => setMode("text") }, "Tap to switch to text")),
    v.error
      ? h(
          "div",
          { class: "err" },
          gvIcon("alert", 14),
          h("span", { class: "grow" }, v.error),
          v.error.includes("microphone") ? h("button", { class: "link", onclick: () => void chrome.tabs.create({ url: `chrome://settings/content/siteDetails?site=${encodeURIComponent(`chrome-extension://${chrome.runtime.id}`)}` }) }, "Allow") : null,
        )
      : null,
    v.heard || you || last
      ? h(
          "div",
          { class: "card", style: { padding: "10px 12px", display: "flex", flexDirection: "column", gap: "8px" } },
          v.heard || you ? h("div", { class: "stack" }, h("span", { class: "sub xs" }, "You"), h("span", null, v.status === "listening" ? v.heard : you?.text || v.heard)) : null,
          last && v.status !== "listening"
            ? h(
                "div",
                { class: "stack", style: { background: "var(--s2)", borderRadius: "10px", padding: "8px 10px" } },
                h("span", { class: "row xs", style: { gap: "6px", color: "var(--br)" } }, h("span", { class: "dot", style: { background: "var(--ok)" } }), `${name}${v.status === "speaking" ? " · speaking" : ""}`),
                h("span", { class: "xs", style: { color: "var(--t2)" } }, (last.text || last.error).slice(0, 280)),
              )
            : null,
          last?.sources || last
            ? h(
                "div",
                { class: "row" },
                h("span", { class: "grow" }, sourcesLine(last?.sources)),
                h("button", { class: "mlink xs", onclick: () => setMode("text") }, "Full transcript"),
              )
            : null,
        )
      : null,
  )
  footEl.classList.remove("hidden")
  gvSet(footEl, h("div", { class: "row sub xs", style: { gap: "8px", padding: "4px 2px" } }, gvIcon("voice", 14), "Speak anytime to interrupt. Saved to this conversation."))
}

/* ------------------------------------------------------------------ */
/* Approvals                                                            */
/* ------------------------------------------------------------------ */

async function loadApprovals(quiet) {
  const res = await gvSend({ type: "LIST_APPROVALS" })
  if (res.ok) {
    state.approvals = res.approvals.map(gvApproval).filter((a) => a.id)
    state.approvalsAt = Date.now()
    state.error = null
  } else if (!quiet) state.error = res.error || "Couldn't load approvals"
  if (state.view === "approvals" || !quiet) renderAll()
  else renderTabs()
}

function visibleApprovals() {
  return state.approvals.filter((a) => !state.hidden.has(a.id))
}

/** Approve or reject with a few seconds to undo; nothing is sent until the window closes. */
function decide(a, approve, comment) {
  state.hidden.add(a.id)
  state.rejecting = null
  const rest = visibleApprovals()
  state.open = rest[0]?.id || null
  renderAll()
  gvToast(`${approve ? "Approved" : "Rejected"}: ${a.title}`, {
    ms: 5000,
    undo: () => {
      state.hidden.delete(a.id)
      state.open = a.id
      renderAll()
    },
    commit: async () => {
      const res = await gvSend({ type: "DECIDE_APPROVAL", id: a.id, approve, comment: comment || null })
      state.hidden.delete(a.id)
      if (!res.ok) {
        gvToast(res.error || "That didn't go through. It's back in the list.")
        renderAll()
        return
      }
      state.approvals = state.approvals.filter((x) => x.id !== a.id)
      renderAll()
    },
  })
}

function approvalCard(a) {
  const open = state.open === a.id
  const rejecting = state.rejecting === a.id
  const meta = [a.requester, a.policy, gvAgo(a.requestedAt)].filter(Boolean).join(" · ")
  const head = h(
    "button",
    {
      class: "row",
      "aria-expanded": open ? "true" : "false",
      style: { width: "100%", border: 0, background: "transparent", padding: "10px 12px", cursor: "pointer", textAlign: "left", alignItems: "flex-start" },
      onclick: () => {
        state.open = open ? null : a.id
        state.rejecting = null
        renderAll()
      },
    },
    h("span", { class: "stack grow" }, h("span", { class: "strong" }, a.title), h("span", { class: "sub xs" }, meta)),
    a.integration ? gvBadge(a.integration, 20) : null,
  )
  const card = h("div", { class: "card fade", "data-id": a.id, style: open ? { borderColor: "var(--bx)" } : null }, head)
  if (!open) return card
  if (a.rows.length) card.appendChild(h("div", null, a.rows.map(([k, v]) => h("div", { class: "kv" }, h("span", null, k), h("span", { class: "newv" }, v)))))
  else if (a.description) card.appendChild(h("div", { class: "xs", style: { padding: "0 12px 10px", color: "var(--t2)" } }, a.description))
  if (a.conversationId) {
    card.appendChild(
      h(
        "div",
        { style: { padding: "6px 12px", borderTop: "1px solid var(--bs)" } },
        h("button", { class: "link xs", onclick: () => void openConversation(a.conversationId) }, "From your conversation"),
      ),
    )
  }
  if (rejecting) {
    const ta = h("textarea", { class: "field", rows: "2", placeholder: `${a.requester} sees your reason and can replan.`, "aria-label": "Why are you rejecting this?", style: { resize: "none" } })
    ta.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        state.rejecting = null
        renderAll()
      }
      e.stopPropagation()
    })
    card.appendChild(
      h(
        "div",
        { class: "stack", style: { gap: "6px", padding: "10px 12px", borderTop: "1px solid var(--bs)" } },
        h("label", { class: "strong xs" }, "Why are you rejecting this?"),
        ta,
        h(
          "div",
          { class: "row", style: { justifyContent: "flex-end" } },
          h(
            "button",
            {
              class: "btn btn-sm btn-q",
              onclick: () => {
                state.rejecting = null
                renderAll()
              },
            },
            "Cancel",
          ),
          h("button", { class: "btn btn-sm btn-dp", onclick: () => decide(a, false, ta.value.trim()) }, "Reject"),
        ),
      ),
    )
    setTimeout(() => ta.focus())
    return card
  }
  card.appendChild(
    h(
      "div",
      { class: "row", style: { padding: "8px 12px", borderTop: "1px solid var(--bs)" } },
      h("span", { class: "sub xs grow" }, canApprove() ? "" : "Your role can't approve changes"),
      h(
        "button",
        {
          class: "btn btn-sm btn-d",
          disabled: !canApprove(),
          onclick: () => {
            state.rejecting = a.id
            renderAll()
          },
        },
        "Reject",
      ),
      h("button", { class: "btn btn-sm btn-p", disabled: !canApprove(), onclick: () => decide(a, true) }, "Approve"),
    ),
  )
  return card
}

function renderApprovals() {
  const rows = visibleApprovals()
  if (state.open && !rows.some((a) => a.id === state.open)) state.open = null
  if (!state.open && rows.length) state.open = rows[0].id
  const parts = [
    h(
      "div",
      { class: "row" },
      h("span", { class: "strong grow" }, state.approvalsAt ? (rows.length ? `${rows.length} waiting for you` : "Nothing waiting for you") : "Approvals"),
      h("button", { class: "link", onclick: () => web("/trust-safety?tab=approvals") }, "Open in Trust & Safety ↗"),
    ),
  ]
  if (state.error) parts.push(errorLine(state.error, () => void loadApprovals()))
  if (!state.approvalsAt && !state.error) parts.push(h("div", { class: "skel" }), h("div", { class: "skel" }))
  else if (!rows.length) parts.push(h("div", { class: "empty" }, h("span", { style: { color: "var(--br)" } }, gvIcon("shieldok", 28)), h("b", null, "You're all caught up"), h("span", null, "When an agent needs your OK, it shows up here.")))
  parts.push(...rows.map(approvalCard))
  gvSet(bodyEl, ...parts)
  bodyEl.querySelector(`[data-id="${CSS.escape(state.open || "")}"]`)?.scrollIntoView({ block: "nearest" })
  if (rows.length) {
    footEl.classList.remove("hidden")
    footEl.style.padding = "0"
    gvSet(footEl, 
      h(
        "div",
        { class: "sp-keys" },
        h("span", { class: "kbd" }, "J"),
        h("span", { class: "kbd" }, "K"),
        "move",
        h("span", { class: "kbd", style: { marginLeft: "8px" } }, "A"),
        "approve",
        h("span", { class: "kbd", style: { marginLeft: "8px" } }, "R"),
        "reject",
      ),
    )
  }
}

document.addEventListener("keydown", (e) => {
  if (state.view !== "approvals" || e.metaKey || e.ctrlKey || e.altKey) return
  if (e.target instanceof HTMLElement && /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName)) return
  const rows = visibleApprovals()
  if (!rows.length) return
  const i = Math.max(0, rows.findIndex((a) => a.id === state.open))
  const key = e.key.toLowerCase()
  if (key === "j" || key === "k") {
    state.open = rows[Math.min(rows.length - 1, Math.max(0, i + (key === "j" ? 1 : -1)))].id
    state.rejecting = null
    renderAll()
  } else if (key === "a" && canApprove()) decide(rows[i], true)
  else if (key === "r" && canApprove()) {
    state.rejecting = rows[i].id
    renderAll()
  } else return
  e.preventDefault()
})

async function openConversation(id) {
  const res = await gvSend({ type: "LOAD_MESSAGES", conversationId: id })
  if (!res.ok) return gvToast(res.error || "Couldn't open that conversation")
  state.conversationId = id
  state.messages = res.messages
    .filter((m) => m && (m.role === "user" || m.role === "assistant"))
    .map((m) => ({ role: m.role, text: String(m.content || ""), agent: m.role === "assistant" ? agentIdentity() : undefined }))
  setView("ask")
}

/* ------------------------------------------------------------------ */
/* Activity                                                             */
/* ------------------------------------------------------------------ */

async function loadJobs() {
  const res = await gvSend({ type: "LIST_JOBS", limit: 20 })
  if (res.ok) {
    state.jobs = res.jobs.map(gvJob).filter((j) => j.id)
    state.jobsError = null
  } else state.jobsError = res.error || "Couldn't load activity"
  if (state.view === "activity") renderAll()
}

function renderActivity() {
  const parts = [h("span", { class: "strong" }, "Recent assignments and runs")]
  if (state.jobsError) parts.push(errorLine(state.jobsError, () => void loadJobs()))
  if (!state.jobs && !state.jobsError) parts.push(h("div", { class: "skel" }), h("div", { class: "skel" }), h("div", { class: "skel" }))
  else if (state.jobs && !state.jobs.length) parts.push(h("div", { class: "empty" }, h("b", null, "No assignments yet"), h("span", null, "Hand an objective to an agent on the web or from Ask.")))
  if (state.jobs?.length) {
    parts.push(
      h(
        "div",
        { class: "card rows" },
        state.jobs.map((j) => {
          const id = gvIdentity(state.agents, j.agent, j.agentId)
          return h(
            "div",
            { class: "stack", style: { gap: "6px", padding: "10px 12px" } },
            h("div", { class: "row", style: { gap: "6px" } }, gvPill(j.status), h("span", { class: "sub xs" }, j.status === "needs_approval" ? "Now" : gvWhen(j.at)), h("span", { class: "grow" }), gvAgentAvatar(id, 18), h("span", { class: "sub xs" }, id.name)),
            h("span", { class: "strong" }, j.title),
            h("div", { class: "row" }, h("span", { class: "sub xs grow" }, j.line), h("button", { class: "link", onclick: () => web(`/assignments/${encodeURIComponent(j.id)}`) }, "Open ↗")),
          )
        }),
      ),
    )
  }
  parts.push(h("button", { class: "mlink", style: { alignSelf: "center", padding: "6px" }, onclick: () => web("/activity") }, "See all activity on web ↗"))
  gvSet(bodyEl, ...parts)
}

/* ------------------------------------------------------------------ */
/* Session                                                              */
/* ------------------------------------------------------------------ */

async function switchOrg(id) {
  await gvSend({ type: "SWITCH_ORG", orgId: id })
  newChat()
  await load()
}

async function signOut() {
  await gvSend({ type: "SIGN_OUT" })
  newChat()
  await load()
}

async function load() {
  state.prefs = await gvPrefs()
  gvApplyTheme(state.prefs.theme)
  const res = await gvSend({ type: "GET_SESSION" })
  if (res.cfg?.appBase) gvSetAppBase(res.cfg.appBase)
  state.offline = Boolean(res.offline || (!res.ok && res.offline))
  state.signedIn = Boolean(res.ok && res.signedIn)
  state.expired = Boolean(res.expired)
  state.noAccess = Boolean(res.noAccess)
  state.session = res.session || null
  state.orgId = res.cfg?.orgId || ""
  state.profile = res.profile || { orgName: res.snapshot?.profile?.orgName || "", organizations: res.organizations || [] }
  if (!state.prefs.consentAt) state.view = "consent"
  state.ready = true
  renderAll()
  if (!state.signedIn || state.noAccess || state.offline) return
  const [caps, agents] = await Promise.all([gvSend({ type: "GET_CAPS" }), gvSend({ type: "LIST_AGENTS" })])
  state.caps = caps.ok ? caps.capabilities : null
  state.agents = agents.ok ? gvAgents(agents.agents) : []
  void gvSend({ type: "LIST_WORKFLOWS" }).then((r) => {
    state.workflows = r.ok && Array.isArray(r.result?.workflows) ? r.result.workflows : []
    if (state.view === "ask") renderAll()
  })
  void loadApprovals(true)
  await readPage()
  await takeHandoff()
  renderAll()
}

/** What the popup or the in-page card asked the panel to do: a view to show, a question to ask. */
async function takeHandoff() {
  const { gvDraft, gvPanelView } = await chrome.storage.local.get(["gvDraft", "gvPanelView"])
  const fresh = (x) => x && Date.now() - Number(x.at || 0) < 15000
  if (fresh(gvPanelView) && state.prefs.consentAt) setView(gvPanelView.view === "consent" ? "consent" : gvPanelView.view)
  if (fresh(gvDraft) && state.signedIn) {
    if (state.view !== "ask") setView("ask")
    void send(gvDraft.text)
  }
  if (gvDraft || gvPanelView) await chrome.storage.local.remove(["gvDraft", "gvPanelView"])
}

chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== "local") return
  if (changes.gvDraft?.newValue || changes.gvPanelView?.newValue) void takeHandoff()
  if (changes.accessToken || changes.orgId) void load()
  if (changes.gvPrefs?.newValue) {
    state.prefs = { ...state.prefs, ...changes.gvPrefs.newValue }
    gvApplyTheme(state.prefs.theme)
  }
})

chrome.tabs.onActivated.addListener(() => void readPage())
chrome.tabs.onUpdated.addListener((_id, info, tab) => {
  if (tab.active && info.status === "complete") void readPage()
})
window.addEventListener("online", () => void load())
window.addEventListener("offline", () => {
  state.offline = true
  renderAll()
})
setInterval(() => {
  if (state.signedIn && !document.hidden) void loadApprovals(true)
}, 60000)

void load()
