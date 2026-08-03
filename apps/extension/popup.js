const statusEl = document.getElementById("status")
const actionsEl = document.getElementById("actions")

function btn(label, className, onClick) {
  const b = document.createElement("button")
  b.textContent = label
  if (className) b.className = className
  b.addEventListener("click", onClick)
  return b
}

async function refresh() {
  actionsEl.innerHTML = ""
  chrome.runtime.sendMessage({ type: "GET_SESSION" }, (res) => {
    if (!res?.ok || !res.signedIn) {
      statusEl.textContent =
        "Not connected. Sign in with your Gravitree account (same org session)."
      actionsEl.appendChild(
        btn("Connect Gravitree", null, () => {
          chrome.runtime.sendMessage({ type: "OPEN_CONNECT" })
        }),
      )
      return
    }
    const integrations = (res.session?.connectedIntegrations || []).join(", ") || "none"
    statusEl.textContent = `Signed in · connectors: ${integrations}`
    actionsEl.appendChild(
      btn("Enrich this page", null, () => {
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
          const tab = tabs[0]
          if (!tab?.id) return
          const url = tab.url || ""
          const known =
            /linkedin\.com|mail\.google\.com|outlook\.(office|live)/i.test(url)
          if (known) {
            chrome.tabs.sendMessage(tab.id, { type: "OPEN_OVERLAY" })
          } else {
            chrome.runtime.sendMessage({ type: "INJECT_COMPANY_OVERLAY" })
          }
          window.close()
        })
      }),
    )
    actionsEl.appendChild(
      btn("Open side panel", "secondary", async () => {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
        if (tab?.windowId != null && chrome.sidePanel?.open) {
          await chrome.sidePanel.open({ windowId: tab.windowId })
        }
      }),
    )
    actionsEl.appendChild(
      btn("Sign out", "secondary", () => {
        chrome.runtime.sendMessage({ type: "SIGN_OUT" }, () => refresh())
      }),
    )
  })
}

refresh()
