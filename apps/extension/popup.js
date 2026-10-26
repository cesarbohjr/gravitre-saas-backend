/* The toolbar popup: signed in, signed out, session expired, no workspace access and offline. */
const headEl = document.getElementById("head")
const bodyEl = document.getElementById("body")
const footEl = document.getElementById("foot")

let tab = null
let prefs = { ...GV_DEFAULT_PREFS }
const tabReady = chrome.tabs.query({ active: true, currentWindow: true }).then(([t]) => (tab = t || null))

/**
 * Opens the side panel. Chrome only allows this straight from a click, so the open call
 * goes first and anything the panel should pick up is written to storage after it.
 */
function openPanel(handoff) {
  if (tab?.windowId != null && chrome.sidePanel?.open) {
    chrome.sidePanel.open({ windowId: tab.windowId }).catch(() => {})
  }
  const writes = []
  if (handoff?.draft) writes.push(chrome.storage.local.set({ gvDraft: { text: handoff.draft, at: Date.now() } }))
  if (handoff?.view) writes.push(chrome.storage.local.set({ gvPanelView: { view: handoff.view, at: Date.now() } }))
  void Promise.all(writes).finally(() => setTimeout(() => window.close(), 60))
}

function openWeb(path) {
  void gvSend({ type: "OPEN_APP", path }).then(() => window.close())
}

function header(orgName, opts = {}) {
  gvSet(headEl, 
    gvMarkTile(22),
    opts.orgs
      ? gvWorkspaceButton(orgName, opts.orgs, opts.orgId, (id) => void gvSend({ type: "SWITCH_ORG", orgId: id }).then(load))
      : orgName
        ? h("span", { class: "row", style: { gap: "6px", fontWeight: "600", fontSize: "12px", opacity: opts.dim ? ".7" : "1" } }, gvWsTile(orgName, 18), orgName)
        : null,
    h("span", { class: "grow" }),
    opts.offline ? h("span", { class: "row sub xs", style: { gap: "5px" } }, h("span", { class: "dot", style: { background: "var(--ap)" } }), "Offline") : null,
    opts.person ? h("span", { title: opts.person }, gvAvatar(opts.person, 24)) : null,
  )
}

function footer(synced) {
  footEl.classList.remove("hidden")
  gvSet(footEl, 
    h("button", { class: "mlink", onclick: () => openWeb("/home") }, "Open Gravitre ↗"),
    h("button", { class: "mlink", onclick: () => openPanel({ view: "settings" }) }, "Settings ↗"),
    h("span", { class: "grow" }),
    synced ? h("span", { class: "row sub xs", style: { gap: "5px" } }, h("span", { class: "dot", style: { background: "var(--ok)" } }), "Synced") : null,
  )
}

function iconBox(name, tone) {
  const tones = { amber: ["var(--aps)", "var(--apk)"], quiet: ["var(--s3)", "var(--t2)"], ok: ["var(--brs)", "var(--brk)"] }
  const [bg, fg] = tones[tone] || tones.quiet
  return h("span", { class: "ibox", style: { background: bg, color: fg } }, gvIcon(name, 15))
}

/* ------------------------------------------------------------------ */
/* Signed out, expired, no access, offline                              */
/* ------------------------------------------------------------------ */

function renderSignedOut() {
  headEl.classList.add("hidden")
  footEl.classList.remove("hidden")
  footEl.style.justifyContent = "center"
  gvSet(footEl, h("button", { class: "mlink", onclick: () => openWeb("/get-started") }, "New to Gravitre? Create a workspace ↗"))
  gvSet(bodyEl, 
    h(
      "div",
      { class: "stack fade", style: { alignItems: "center", textAlign: "center", gap: "12px", padding: "40px 16px 24px" } },
      gvMarkTile(44),
      h("span", { style: { fontSize: "18px", fontWeight: "600", letterSpacing: "-.01em" } }, "Gravitre in your browser"),
      h("span", { class: "sub", style: { fontSize: "13px", color: "var(--t2)" } }, "Ask about any page, run Plays and approve requests without switching tabs."),
      h("button", { class: "btn btn-p btn-lg btn-block", onclick: () => void gvSend({ type: "OPEN_CONNECT" }).then(() => window.close()) }, "Connect Gravitre"),
      h("span", { class: "sub xs" }, "Opens gravitre.app to sign in. Works with your company's single sign-on."),
    ),
  )
}

function renderExpired(snapshot) {
  header(snapshot?.profile?.orgName || "", { dim: true })
  footEl.classList.add("hidden")
  gvSet(bodyEl, 
    h(
      "div",
      { class: "state fade" },
      iconBox("lock"),
      h("h1", null, "Your session expired"),
      h("span", { class: "sub", style: { color: "var(--t2)" } }, "Sign in again to pick up where you left off. Your conversations are saved."),
      h("button", { class: "btn btn-p btn-block", onclick: () => void gvSend({ type: "OPEN_CONNECT" }).then(() => window.close()) }, "Sign in again"),
    ),
    h("div", { class: "skel" }),
    h("div", { class: "skel" }),
  )
}

function renderNoAccess(res) {
  const name = res.snapshot?.profile?.orgName || "this workspace"
  const others = (res.organizations || []).filter((o) => o.id !== res.cfg?.orgId)
  header(res.snapshot?.profile?.orgName || "", { orgs: res.organizations?.length > 1 ? res.organizations : null, orgId: res.cfg?.orgId })
  footEl.classList.add("hidden")
  const switchBtn = h("button", { class: "btn btn-p btn-sm" }, "Switch workspace")
  switchBtn.addEventListener("click", () => {
    if (!others.length) {
      void gvSend({ type: "OPEN_CONNECT" }).then(() => window.close())
      return
    }
    gvMenu(
      switchBtn,
      others.map((o) => ({ label: o.name || "Workspace", icon: gvWsTile(o.name || "W", 16), run: () => void gvSend({ type: "SWITCH_ORG", orgId: o.id }).then(load) })),
    )
  })
  gvSet(bodyEl, 
    h(
      "div",
      { class: "state fade", style: { position: "relative" } },
      iconBox("user"),
      h("h1", null, `You don't have access to ${name.replace(/\.$/, "")}.`),
      h("span", { class: "sub", style: { color: "var(--t2)" } }, "Your account isn't a member of this workspace. Ask an admin to add you, or switch to another workspace."),
      h("div", { class: "row" }, switchBtn),
    ),
  )
}

function renderOffline(snapshot) {
  const at = snapshot?.at ? gvClock(snapshot.at) : ""
  header(snapshot?.profile?.orgName || "", { offline: true })
  footEl.classList.add("hidden")
  const n = Number(snapshot?.approvals || 0)
  gvSet(bodyEl, 
    h("div", { class: "note fade" }, gvIcon("wifioff", 14), h("span", null, at ? `You're offline. Showing what was saved at ${at}. We'll reconnect on our own.` : "You're offline. We'll reconnect on our own.")),
    h("div", { class: "ask", style: { opacity: ".6" } }, h("input", { disabled: true, placeholder: "Reconnect to ask", "aria-label": "Ask" })),
    snapshot
      ? h("div", { class: "rowbtn", style: { cursor: "default" } }, iconBox("clock", "amber"), h("span", null, h("b", null, `${n} waiting`), at ? h("span", { class: "sub" }, ` as of ${at}`) : null))
      : null,
    h("span", { class: "sub xs", style: { padding: "0 4px" } }, "Approving is paused until you're back online."),
  )
}

/* ------------------------------------------------------------------ */
/* Signed in                                                            */
/* ------------------------------------------------------------------ */

function askBox(agent) {
  const input = h("input", { placeholder: `Ask ${agent ? agent.name : "Gravitre"} anything…`, "aria-label": "Ask", autofocus: true })
  const go = () => {
    const text = input.value.trim()
    if (text) openPanel({ draft: text, view: "ask" })
  }
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") go()
  })
  return h(
    "div",
    { class: "ask" },
    agent ? h("span", { class: "chip flat", style: { height: "24px" } }, gvAgentAvatar(gvIdentity([agent], agent.name, agent.id), 18), agent.name) : null,
    input,
    h("span", { class: "kbd" }, "Enter"),
  )
}

/** "On this page": the person or company the content script found, with what Gravitre already has on them. */
function pageCard(ctx) {
  const c = ctx.context || {}
  const name = c.fullName || c.company || ""
  const line = [c.title, c.fullName && c.company && !String(c.title || "").includes(c.company) ? c.company : null].filter(Boolean).join(" at ")
  const matches = h("div", { class: "stack", style: { gap: "4px" } })
  const card = h(
    "div",
    { class: "card fade", style: { padding: "10px 12px", display: "flex", flexDirection: "column", gap: "8px" } },
    h("span", { class: "sub xs" }, "On this page"),
    h(
      "div",
      { class: "row", style: { alignItems: "flex-start", gap: "10px" } },
      c.fullName ? gvPersonAvatar(c.fullName, 32) : h("span", { class: "ibox", style: { background: "var(--s3)", width: "32px", height: "32px" } }, gvIcon("globe", 15)),
      h("span", { class: "stack grow" }, h("span", { class: "strong" }, name || ctx.title || ctx.host), h("span", { class: "sub" }, line || ctx.host)),
    ),
    matches,
    h("button", { class: "btn btn-sm btn-block", onclick: () => openPanel({ view: "ask" }) }, gvIcon("panel", 14), "Open in side panel"),
  )
  const kind = ctx.kind || "people"
  if (name && prefs.detect[kind] !== false) {
    matches.appendChild(h("span", { class: "sub xs" }, "Checking your connected apps…"))
    void gvSend({ type: "ENRICH", pageUrl: ctx.url, pageContext: c }).then((res) => {
      const found = res.ok ? gvMatches(res.result) : []
      gvSet(matches, 
        ...(found.length
          ? found.map((m) => h("span", { class: "row sub xs", style: { gap: "6px" } }, gvBadge(m.app, 16), m.label))
          : [h("span", { class: "sub xs" }, res.ok ? "Not in your connected apps yet" : "Couldn't check your connected apps")]),
      )
    })
  }
  return card
}

function canSee(hostId, host) {
  const reads = ["The current tab's address and title", "The text you can see on the page", "Text you select and choose to attach"]
  const never = ["Passwords or anything you type into forms", "Other tabs or your browsing history", "Pages on sites you turn off"]
  const list = (items, icon, color) => h("div", { class: "stack", style: { gap: "4px" } }, items.map((t) => h("span", { class: "row xs", style: { gap: "6px", color: "var(--t2)" } }, h("span", { style: { color } }, gvIcon(icon, 12)), t)))
  const inner = h(
    "div",
    { class: "stack hidden", style: { gap: "10px", padding: "0 12px 12px" } },
    h("span", { class: "sub xs" }, "When you ask, Gravitre reads"),
    list(reads, "check", "var(--br)"),
    h("span", { class: "sub xs" }, "Gravitre never reads"),
    list(never, "x", "var(--t3)"),
    hostId
      ? h(
          "div",
          { class: "row", style: { borderTop: "1px solid var(--bs)", paddingTop: "8px" } },
          h("span", { class: "grow xs" }, `On ${host}`),
          gvToggle(gvSiteOn(prefs, hostId), `Allow Gravitre on ${host}`, (on) => void gvSavePrefs({ sites: { ...prefs.sites, [hostId]: on } }).then((p) => (prefs = p))),
        )
      : h("span", { class: "sub xs" }, host ? `${host} isn't one of your allowed sites. Add it from Settings.` : ""),
  )
  const chev = gvIcon("chev", 14)
  const btn = h(
    "button",
    {
      class: "row",
      "aria-expanded": "false",
      style: { width: "100%", border: 0, background: "transparent", padding: "10px 12px", cursor: "pointer", fontWeight: "500", textAlign: "left" },
      onclick: () => {
        const open = inner.classList.toggle("hidden") === false
        btn.setAttribute("aria-expanded", open ? "true" : "false")
        chev.style.transform = open ? "rotate(180deg)" : ""
      },
    },
    h("span", { style: { color: "var(--br)", display: "inline-flex" } }, gvIcon("shieldok", 15)),
    h("span", { class: "grow" }, "What Gravitre can see"),
    chev,
  )
  return h("div", { class: "card" }, btn, inner)
}

async function renderSignedIn(res) {
  const profile = res.profile || {}
  header(profile.orgName, { orgs: profile.organizations, orgId: res.cfg?.orgId, person: profile.name || profile.email })
  footer(true)
  gvSet(bodyEl, h("div", { class: "skel" }), h("div", { class: "skel", style: { height: "120px" } }))

  await tabReady
  const host = gvHostOf(tab?.url || "")
  const hostId = gvSiteIdFor(host, prefs)
  const [agentsRes, approvalsRes, ctx] = await Promise.all([
    gvSend({ type: "LIST_AGENTS" }),
    gvSend({ type: "LIST_APPROVALS" }),
    prefs.consentAt && hostId && gvSiteOn(prefs, hostId) ? gvPageContext(tab?.id) : Promise.resolve(null),
  ])
  const agents = agentsRes.ok ? gvAgents(agentsRes.agents) : []
  const agent = agents.find((a) => a.id === prefs.agentId) || agents[0] || null
  const waiting = approvalsRes.ok ? approvalsRes.approvals.length : 0
  const connected = Array.isArray(res.session?.connectedIntegrations) ? res.session.connectedIntegrations : []

  const parts = [askBox(agent)]
  if (!prefs.consentAt) {
    parts.push(
      h(
        "button",
        { class: "rowbtn", onclick: () => openPanel({ view: "consent" }) },
        iconBox("shieldok", "ok"),
        h("span", { class: "grow" }, "Choose the sites Gravitre can read"),
        gvIcon("chevr", 14),
      ),
    )
  } else if (ctx) parts.push(pageCard(ctx))
  parts.push(
    h(
      "button",
      { class: "rowbtn", onclick: () => openPanel({ view: "approvals" }) },
      iconBox("appr", waiting ? "amber" : "quiet"),
      h("span", { class: "grow" }, waiting ? `${waiting} waiting for you` : "Nothing waiting for you"),
      gvIcon("chevr", 14),
    ),
  )
  if (connected.length) {
    parts.push(
      h(
        "div",
        { class: "row", style: { flexWrap: "wrap", gap: "6px" } },
        h("span", { class: "sub xs" }, "Connected"),
        connected.slice(0, 6).map((slug) => h("span", { class: "tag xs" }, gvBadge(slug, 16), gvAppName(slug))),
      ),
    )
  }
  parts.push(canSee(hostId, host))
  gvSet(bodyEl, ...parts)
  bodyEl.querySelector("input")?.focus()
}

async function load() {
  prefs = await gvPrefs()
  gvApplyTheme(prefs.theme)
  headEl.classList.remove("hidden")
  footEl.style.justifyContent = ""
  const res = await gvSend({ type: "GET_SESSION" })
  if (res.cfg?.appBase) gvSetAppBase(res.cfg.appBase)
  if (!res.ok) {
    if (res.offline || navigator.onLine === false) return renderOffline((await chrome.storage.local.get("snapshot")).snapshot)
    header("")
    footEl.classList.add("hidden")
    gvSet(bodyEl, h("div", { class: "err", role: "alert" }, gvIcon("alert", 14), h("span", { class: "grow" }, res.error || "Couldn't reach Gravitre")), h("button", { class: "btn btn-sm", onclick: load }, "Try again"))
    return
  }
  if (!res.signedIn) return res.expired ? renderExpired(res.snapshot) : renderSignedOut()
  if (res.offline) return renderOffline(res.snapshot)
  if (res.noAccess) return renderNoAccess(res)
  return renderSignedIn(res)
}

window.addEventListener("online", () => void load())
void load()
