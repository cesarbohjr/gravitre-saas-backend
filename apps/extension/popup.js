const bodyEl = document.getElementById("body")
const footEl = document.getElementById("foot")
const wsEl = document.getElementById("ws")
const openAppEl = document.getElementById("open-app")

document.getElementById("mark").appendChild(gvMark(24, 18))
openAppEl.appendChild(gvIcon("ext"))
openAppEl.addEventListener("click", () => {
  void gvSend({ type: "OPEN_APP", path: "/home" })
  window.close()
})

const KNOWN_PAGES =
  /linkedin\.com|mail\.google\.com|outlook\.(office|live)|lightning\.force\.com|salesforce\.com|force\.com|app\.slack\.com/i

async function activeTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
  return tab || null
}

let currentTab = null
void activeTab().then((t) => (currentTab = t))

/** Opens the side panel. Chrome only allows this straight from a click, so nothing is awaited first. */
function openPanel() {
  if (currentTab?.windowId != null && chrome.sidePanel?.open) {
    chrome.sidePanel.open({ windowId: currentTab.windowId }).finally(() => window.close())
  }
}

function choosePanelTab(name) {
  return chrome.storage.session?.set({ panelTab: name }) ?? Promise.resolve()
}

function action(icon, label, onClick) {
  return h("button", { class: "act", onclick: onClick }, gvIcon(icon), h("span", { class: "grow" }, label))
}

function renderSignedOut(notice) {
  wsEl.textContent = "Not connected"
  openAppEl.classList.add("hidden")
  footEl.classList.add("hidden")
  bodyEl.replaceChildren(
    h(
      "div",
      { class: "stack fade", style: { gap: "10px" } },
      h("span", { class: "eyebrow" }, "Connect"),
      h("span", { style: { fontSize: "17px", fontWeight: "600", letterSpacing: "-.01em" } }, "Bring Gravitre to every page"),
      h(
        "span",
        { class: "sub", style: { fontSize: "13px" } },
        "Sign in on gravitre.app, then click Authorize extension. Your company's single sign-on works as usual.",
      ),
      notice ? h("div", { class: "err", role: "alert" }, notice) : null,
      h(
        "button",
        {
          class: "btn btn-k btn-block",
          onclick: () => {
            void gvSend({ type: "OPEN_CONNECT" })
            window.close()
          },
        },
        "Connect Gravitre",
      ),
    ),
  )
}

function enrich() {
  void activeTab().then((tab) => {
    if (!tab?.id) return
    const url = tab.url || ""
    const known = KNOWN_PAGES.test(url)
    // Always record the usage signal, including pages outside the allowlist.
    void gvSend({
      type: "USAGE_SIGNAL",
      pageUrl: url,
      invoked: true,
      note: known ? "popup_enrich_allowlisted" : "popup_enrich_active_tab_or_outside",
    })
    if (known) chrome.tabs.sendMessage(tab.id, { type: "OPEN_OVERLAY" })
    else void gvSend({ type: "INJECT_COMPANY_OVERLAY" })
    window.close()
  })
}

function renderSignedIn(session, me, approvals) {
  const org = (me?.organizations || []).find((o) => String(o.id) === String(session.orgId))
  wsEl.textContent = org?.name || "Your workspace"
  openAppEl.classList.remove("hidden")

  const count = approvals.length
  const tile = count
    ? h(
        "div",
        { class: "tile wait" },
        h("span", { class: "num", style: { color: "var(--apk)" } }, String(count)),
        h(
          "span",
          { class: "stack grow" },
          h("span", { style: { fontWeight: "600", fontSize: "13px" } }, count === 1 ? "Approval waiting" : "Approvals waiting"),
          h("span", { class: "sub ellipsis" }, approvals[0]?.title || ""),
        ),
        h(
          "button",
          {
            class: "btn btn-k btn-sm",
            onclick: () => {
              void choosePanelTab("appr")
              openPanel()
            },
          },
          "Review",
        ),
      )
    : h(
        "div",
        { class: "tile" },
        h("span", { style: { color: "var(--br)", display: "inline-flex" } }, gvIcon("check")),
        h("span", { class: "grow", style: { fontSize: "13px" } }, "Nothing waiting for your approval"),
      )

  const integrations = session.connectedIntegrations || []
  bodyEl.replaceChildren(
    h(
      "div",
      { class: "stack fade", style: { gap: "10px" } },
      tile,
      action("spark", "Enrich this page", enrich),
      action("ask", "Ask about this page", () => {
        void choosePanelTab("ask")
        openPanel()
      }),
      action("panel", "Open side panel", () => openPanel()),
      integrations.length
        ? h(
            "div",
            { class: "stack", style: { gap: "6px", paddingTop: "4px" } },
            h("span", { class: "eyebrow" }, "Connected"),
            h("div", { class: "logos" }, integrations.slice(0, 12).map((s) => {
              const b = gvBadge(s)
              if (b) b.title = gvAppName(s)
              return b
            })),
          )
        : h("span", { class: "sub" }, "No apps connected yet. Connect them on gravitre.app."),
    ),
  )

  footEl.classList.remove("hidden")
  footEl.replaceChildren(
    h("span", { class: "grow ellipsis" }, me?.email || ""),
    h(
      "button",
      {
        class: "btn btn-q btn-sm",
        onclick: () => void gvSend({ type: "SIGN_OUT" }).then(() => renderSignedOut(null)),
      },
      gvIcon("logout", 14),
      "Sign out",
    ),
  )
}

async function refresh() {
  const res = await gvSend({ type: "GET_SESSION" })
  if (!res.ok) return renderSignedOut(res.code === "not_authenticated" ? "Your session ended. Connect again to keep going." : null)
  if (!res.signedIn) return renderSignedOut(null)
  const [me, appr] = await Promise.all([gvSend({ type: "GET_ME" }), gvSend({ type: "LIST_APPROVALS" })])
  renderSignedIn(res.session || {}, me.ok ? me.me : null, appr.ok ? appr.approvals.map(gvApproval) : [])
}

void refresh()
