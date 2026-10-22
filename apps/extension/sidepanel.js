const bodyEl = document.getElementById("body")
const footEl = document.getElementById("foot")
const tabsEl = document.getElementById("tabs")
const openAppEl = document.getElementById("open-app")

document.getElementById("mark").appendChild(gvMark(31, 18))
openAppEl.appendChild(gvIcon("ext"))
openAppEl.addEventListener("click", () => void gvSend({ type: "OPEN_APP", path: "/home" }))

const state = {
  tab: "ask",
  signedIn: false,
  approvals: [],
  activity: [],
  messages: [],
  conversationId: null,
  sending: false,
  page: null,
  error: null,
}

/* ------------------------------------------------------------------ */
/* Shell                                                               */
/* ------------------------------------------------------------------ */

function renderTabs() {
  const items = [
    ["ask", "Ask"],
    ["appr", "Approvals"],
    ["act", "Activity"],
  ]
  tabsEl.replaceChildren(
    h(
      "div",
      { class: "tabs", role: "tablist" },
      items.map(([key, label]) =>
        h(
          "button",
          {
            role: "tab",
            "aria-selected": state.tab === key ? "true" : "false",
            class: state.tab === key ? "on" : "",
            onclick: () => setTab(key),
          },
          label,
          key === "appr" && state.approvals.length ? h("span", { class: "n" }, String(state.approvals.length)) : null,
        ),
      ),
    ),
  )
}

function setTab(key) {
  state.tab = key
  state.error = null
  renderTabs()
  render()
  if (key === "appr") void loadApprovals()
  if (key === "act") void loadActivity()
}

function render() {
  if (!state.signedIn) return renderSignedOut()
  if (state.tab === "ask") renderAsk()
  else if (state.tab === "appr") renderApprovals()
  else renderActivity()
}

function renderSignedOut() {
  tabsEl.classList.add("hidden")
  footEl.classList.add("hidden")
  openAppEl.classList.add("hidden")
  bodyEl.replaceChildren(
    h(
      "div",
      { class: "empty fade" },
      gvMark(36, 21),
      h("b", null, "Connect Gravitre"),
      h("span", null, "Ask about any page, approve what your agents propose and follow their work, without leaving the tab."),
      h("button", { class: "btn btn-k", style: { marginTop: "8px" }, onclick: () => void gvSend({ type: "OPEN_CONNECT" }) }, "Connect Gravitre"),
    ),
  )
}

function errorLine(text) {
  return h("div", { class: "err", role: "alert" }, gvIcon("alert", 14), h("span", null, text))
}

/* ------------------------------------------------------------------ */
/* Ask                                                                 */
/* ------------------------------------------------------------------ */

async function readPage() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
  if (!tab?.url || !/^https?:/.test(tab.url)) return null
  let host = ""
  try {
    host = new URL(tab.url).hostname.replace(/^www\./, "")
  } catch {
    host = ""
  }
  return { url: tab.url, title: tab.title || host, host }
}

function renderAsk() {
  const list = state.messages.length
    ? state.messages.map((m) =>
        m.role === "user"
          ? h("div", { class: "ubub" }, m.content)
          : h(
              "div",
              { class: "abub fade" },
              gvMark(18, 11),
              h(
                "div",
                { class: "stack grow", style: { gap: "6px" } },
                h("div", { class: "prose" }, m.content),
                m.handoffUrl
                  ? h(
                      "button",
                      { class: "btn btn-sm", style: { alignSelf: "flex-start" }, onclick: () => void gvSend({ type: "OPEN_APP", path: m.handoffUrl }) },
                      "Continue on gravitre.app",
                      gvIcon("ext", 14),
                    )
                  : null,
              ),
            ),
      )
    : [
        h(
          "div",
          { class: "empty" },
          h("b", null, "Ask about this page"),
          h("span", null, "Gravitre reads the page you're on alongside your connected apps. Anything that writes to an app still asks you first."),
        ),
      ]
  if (state.sending) list.push(h("div", { class: "abub" }, gvMark(18, 11), h("span", { class: "typing", "aria-label": "Gravitre is answering" }, h("span"), h("span"), h("span"))))
  if (state.error) list.push(errorLine(state.error))
  bodyEl.replaceChildren(...list)
  bodyEl.scrollTop = bodyEl.scrollHeight
  renderComposer()
}

function renderComposer() {
  footEl.classList.toggle("hidden", state.tab !== "ask" || !state.signedIn)
  if (state.tab !== "ask") return
  const ta = h("textarea", {
    class: "ta",
    rows: "1",
    placeholder: state.page ? `Ask about ${state.page.host}…` : "Ask Gravitre…",
    "aria-label": "Message",
  })
  const send = h("button", { class: "btn btn-k btn-sm", disabled: state.sending, onclick: () => submit(ta) }, "Send")
  ta.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      submit(ta)
    }
  })
  ta.addEventListener("input", () => {
    ta.style.height = "auto"
    ta.style.height = `${Math.min(ta.scrollHeight, 140)}px`
  })
  footEl.replaceChildren(
    h(
      "div",
      { class: "composer" },
      state.page ? h("span", { class: "chip", title: state.page.url }, gvIcon("page", 13), h("span", { class: "ellipsis" }, state.page.title)) : null,
      ta,
      h(
        "div",
        { class: "row" },
        h(
          "button",
          { class: "btn btn-q btn-sm", disabled: state.sending || !state.messages.length, onclick: newConversation },
          gvIcon("plus", 14),
          "New",
        ),
        state.conversationId
          ? h(
              "button",
              { class: "btn btn-q btn-sm", onclick: () => void gvSend({ type: "OPEN_APP", path: `/ai?c=${encodeURIComponent(state.conversationId)}` }) },
              "Open on web",
            )
          : null,
        h("span", { class: "grow" }),
        send,
      ),
    ),
  )
  if (!state.sending) ta.focus()
}

async function newConversation() {
  state.messages = []
  state.conversationId = null
  state.error = null
  await chrome.storage.local.remove("panelConversationId")
  renderAsk()
}

async function submit(ta) {
  const text = ta.value.trim()
  if (!text || state.sending) return
  state.page = await readPage()
  state.messages.push({ role: "user", content: text })
  state.sending = true
  state.error = null
  renderAsk()
  const res = await gvSend({
    type: "CHAT",
    message: text,
    pageUrl: state.page?.url || null,
    pageContext: state.page ? { title: state.page.title } : {},
    conversationId: state.conversationId,
  })
  state.sending = false
  if (!res.ok) {
    if (res.code === "not_authenticated") return signedOut()
    state.error = res.error || "Gravitre couldn't answer that. Try again."
  } else {
    const r = res.result || {}
    if (r.conversationId) {
      state.conversationId = String(r.conversationId)
      await chrome.storage.local.set({ panelConversationId: state.conversationId })
    }
    state.messages.push({
      role: "assistant",
      content: String(r.answer || "No answer came back. Try asking another way."),
      handoffUrl: r.needsHandoff ? r.openInGravitreUrl || null : null,
    })
  }
  renderAsk()
}

async function loadConversation() {
  const { panelConversationId } = await chrome.storage.local.get("panelConversationId")
  if (!panelConversationId) return
  const res = await gvSend({ type: "LOAD_MESSAGES", conversationId: panelConversationId })
  if (!res.ok) return
  state.conversationId = String(panelConversationId)
  state.messages = res.messages
    .filter((m) => (m.role === "user" || m.role === "assistant") && typeof m.content === "string" && m.content.trim())
    .map((m) => ({ role: m.role, content: m.content }))
}

/* ------------------------------------------------------------------ */
/* Approvals                                                           */
/* ------------------------------------------------------------------ */

async function loadApprovals() {
  const res = await gvSend({ type: "LIST_APPROVALS" })
  if (!res.ok) {
    if (res.code === "not_authenticated") return signedOut()
    state.error = res.error || "Couldn't load approvals"
  } else state.approvals = (res.approvals || []).map(gvApproval).filter((a) => a.id)
  renderTabs()
  if (state.tab === "appr") renderApprovals()
}

function approvalCard(a) {
  const reason = h("textarea", { class: "field", rows: "2", placeholder: "Why are you rejecting this? The agent sees your reason.", "aria-label": "Reason" })
  const rejectBox = h(
    "div",
    { class: "stack hidden", style: { gap: "8px", padding: "10px 12px", borderTop: "1px solid var(--bs)" } },
    reason,
    h(
      "div",
      { class: "row" },
      h("span", { class: "grow" }),
      h("button", { class: "btn btn-q btn-sm", onclick: () => rejectBox.classList.add("hidden") }, "Cancel"),
      h("button", { class: "btn btn-dp btn-sm", onclick: (e) => decide(a, false, reason.value.trim(), e.currentTarget) }, "Reject"),
    ),
  )
  const buttons = h(
    "div",
    { class: "row", style: { padding: "10px 12px", borderTop: "1px solid var(--bs)" } },
    h("button", { class: "btn btn-q btn-sm btn-d", onclick: () => { rejectBox.classList.remove("hidden"); reason.focus() } }, "Reject…"),
    h("span", { class: "grow" }),
    h("button", { class: "btn btn-k btn-sm", onclick: (e) => decide(a, true, "", e.currentTarget) }, gvIcon("check", 14), "Approve"),
  )
  return h(
    "section",
    { class: "card fade" },
    h(
      "div",
      { class: "row", style: { padding: "12px", alignItems: "flex-start" } },
      gvAvatar(a.requester),
      h(
        "span",
        { class: "stack grow", style: { gap: "2px" } },
        h("span", { style: { fontWeight: "600", fontSize: "13px" } }, a.title),
        h("span", { class: "sub" }, [a.requester, gvAgo(a.requestedAt) && `${gvAgo(a.requestedAt)} ago`].filter(Boolean).join(" · ")),
      ),
      a.integration ? gvBadge(a.integration) : null,
    ),
    a.rows.length
      ? h(
          "div",
          null,
          h("div", { class: "eyebrow", style: { padding: "0 12px 6px" } }, "What happens if you approve"),
          a.rows.map(([k, v]) => h("div", { class: "kv" }, h("span", { class: "sub" }, k), h("span", { class: "new" }, v))),
        )
      : null,
    buttons,
    rejectBox,
  )
}

async function decide(a, approve, comment, button) {
  if (button) button.disabled = true
  const res = await gvSend({ type: "DECIDE_APPROVAL", id: a.id, approve, comment: comment || null })
  if (!res.ok) {
    if (button) button.disabled = false
    state.error = res.error || "That didn't go through. Try again."
    return renderApprovals()
  }
  state.approvals = state.approvals.filter((x) => x.id !== a.id)
  state.error = null
  renderTabs()
  renderApprovals()
}

function renderApprovals() {
  footEl.classList.add("hidden")
  const items = []
  if (state.error) items.push(errorLine(state.error))
  if (!state.approvals.length) {
    items.push(h("div", { class: "empty" }, gvIcon("appr", 22), h("b", null, "You're all caught up"), h("span", null, "When an agent needs your go-ahead, it shows up here.")))
  } else items.push(...state.approvals.map(approvalCard))
  items.push(
    h(
      "button",
      { class: "btn btn-q btn-sm", style: { alignSelf: "center" }, onclick: () => void gvSend({ type: "OPEN_APP", path: "/trust-safety?tab=approvals" }) },
      "Approval history on gravitre.app",
      gvIcon("ext", 14),
    ),
  )
  bodyEl.replaceChildren(...items)
}

/* ------------------------------------------------------------------ */
/* Activity                                                            */
/* ------------------------------------------------------------------ */

async function loadActivity() {
  const res = await gvSend({ type: "LIST_ACTIVITY", limit: 40 })
  if (!res.ok) {
    if (res.code === "not_authenticated") return signedOut()
    state.error = res.error || "Couldn't load activity"
  } else state.activity = res.events || []
  if (state.tab === "act") renderActivity()
}

function renderActivity() {
  footEl.classList.add("hidden")
  const items = []
  if (state.error) items.push(errorLine(state.error))
  if (!state.activity.length && !state.error) {
    items.push(h("div", { class: "empty" }, gvIcon("act", 22), h("b", null, "No activity yet"), h("span", null, "What your agents and apps do shows up here.")))
  }
  let day = null
  let group = null
  for (const e of state.activity) {
    const label = gvDay(e.created_at)
    if (label !== day) {
      day = label
      items.push(h("div", { class: "daylbl" }, label))
      group = h("div", { class: "card", style: { padding: "4px" } })
      items.push(group)
    }
    const url = typeof e.url === "string" && e.url ? e.url : null
    group.appendChild(
      h(
        url ? "button" : "div",
        { class: "lr", style: url ? null : { cursor: "default" }, onclick: url ? () => void gvSend({ type: "OPEN_APP", path: url }) : null },
        e.integration ? gvBadge(e.integration) : h("span", { style: { color: "var(--t3)", display: "inline-flex" } }, gvIcon("act")),
        h(
          "span",
          { class: "stack grow" },
          h("span", { class: "ellipsis", style: { fontSize: "13px", fontWeight: "500" } }, e.title || gvHumanize(e.event_type || "Event")),
          e.body ? h("span", { class: "sub ellipsis" }, e.body) : null,
        ),
        h("span", { class: "stack", style: { alignItems: "flex-end", gap: "4px" } }, gvPill(e.status), h("span", { class: "sub mono", style: { fontSize: "11px" } }, gvClock(e.created_at))),
      ),
    )
  }
  if (state.activity.length) {
    items.push(
      h("button", { class: "btn btn-q btn-sm", style: { alignSelf: "center" }, onclick: () => void gvSend({ type: "OPEN_APP", path: "/activity" }) }, "All activity on gravitre.app", gvIcon("ext", 14)),
    )
  }
  bodyEl.replaceChildren(...items)
}

/* ------------------------------------------------------------------ */
/* Start                                                               */
/* ------------------------------------------------------------------ */

function signedOut() {
  state.signedIn = false
  render()
}

async function start() {
  const res = await gvSend({ type: "GET_SESSION" })
  if (!res.ok || !res.signedIn) return signedOut()
  state.signedIn = true
  gvSetAppBase(res.cfg?.appBase)
  tabsEl.classList.remove("hidden")
  openAppEl.classList.remove("hidden")
  const picked = (await chrome.storage.session?.get("panelTab"))?.panelTab
  if (picked) {
    state.tab = picked
    void chrome.storage.session.remove("panelTab")
  }
  const [me, , page] = await Promise.all([gvSend({ type: "GET_ME" }), loadConversation(), readPage()])
  state.page = page
  const org = (me.ok ? me.me?.organizations || [] : []).find((o) => String(o.id) === String(res.session?.orgId))
  document.getElementById("mark").title = org?.name ? `Gravitre · ${org.name}` : "Gravitre"
  setTab(state.tab)
  void loadApprovals()
}

// The popup asks for a tab while the panel is already open.
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "session" && changes.panelTab?.newValue && state.signedIn) {
    setTab(changes.panelTab.newValue)
    void chrome.storage.session.remove("panelTab")
  }
  if (area === "local" && changes.accessToken && !changes.accessToken.newValue) signedOut()
  if (area === "local" && changes.accessToken?.newValue && !state.signedIn) void start()
})

// Keep the page chip in step with the tab the user is looking at.
chrome.tabs.onActivated.addListener(async () => {
  state.page = await readPage()
  if (state.signedIn && state.tab === "ask") renderComposer()
})
chrome.tabs.onUpdated.addListener(async (_id, info) => {
  if (info.status !== "complete") return
  state.page = await readPage()
  if (state.signedIn && state.tab === "ask" && !state.sending) renderComposer()
})

window.addEventListener("focus", () => {
  if (!state.signedIn) return
  void loadApprovals()
  if (state.tab === "act") void loadActivity()
})

void start()
