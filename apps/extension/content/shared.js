/** Shared overlay renderer for Gravitree content scripts. */
(function () {
  if (window.__gravitreeOverlay) return

  function el(tag, className, text) {
    const node = document.createElement(tag)
    if (className) node.className = className
    if (text != null) node.textContent = text
    return node
  }

  function ensureRoot() {
    let root = document.getElementById("gravitree-overlay-root")
    if (root) return root
    root = el("div")
    root.id = "gravitree-overlay-root"
    document.documentElement.appendChild(root)
    return root
  }

  function renderOverlay({ pageContext, pageUrl }) {
    const root = ensureRoot()
    root.innerHTML = ""
    const card = el("div", "gvt-card")
    const header = el("div", "gvt-header")
    header.appendChild(el("div", "gvt-brand", "Gravitree"))
    const close = el("button", "gvt-close", "×")
    close.type = "button"
    close.addEventListener("click", () => root.remove())
    header.appendChild(close)
    card.appendChild(header)
    card.appendChild(
      el(
        "p",
        "gvt-muted",
        "Enrichment from connected connectors. Writes need your approval — same gate as chat.",
      ),
    )
    const status = el("p", "gvt-muted", "Loading…")
    card.appendChild(status)
    const body = el("div")
    card.appendChild(body)
    root.appendChild(card)

    chrome.runtime.sendMessage(
      { type: "ENRICH", pageUrl, pageContext },
      (response) => {
        if (!response?.ok) {
          status.textContent = response?.error || "Could not enrich this page."
          return
        }
        const result = response.result || {}
        status.textContent = result.voiceNote || "Ready."
        body.innerHTML = ""

        const extracted = result.extracted || {}
        ;[
          ["Name", extracted.fullName],
          ["Title", extracted.title],
          ["Company", extracted.company],
          ["Email", extracted.email],
        ].forEach(([label, value]) => {
          if (!value) return
          const row = el("div", "gvt-row")
          row.appendChild(el("div", "gvt-label", label))
          row.appendChild(el("div", "gvt-value", value))
          body.appendChild(row)
        })

        ;(result.matches || []).forEach((match) => {
          const row = el("div", "gvt-row")
          row.appendChild(el("div", "gvt-label", match.action))
          const badge = el(
            "span",
            `gvt-badge${match.success ? "" : " warn"}`,
            match.confidenceLabel || (match.success ? "matched" : "unavailable"),
          )
          row.appendChild(badge)
          if (match.error) row.appendChild(el("div", "gvt-muted", match.error))
          body.appendChild(row)
        })

        const actions = el("div", "gvt-actions")
        const confirmBox = el("div", "gvt-confirm")
        confirmBox.style.display = "none"

        function showConfirm(suggestion, params) {
          confirmBox.style.display = "block"
          confirmBox.innerHTML = ""
          confirmBox.appendChild(
            el(
              "p",
              null,
              `Approve ${suggestion.invokeAction}? This uses catalog_write_authority and will appear in Outcomes.`,
            ),
          )
          if (suggestion.note) {
            confirmBox.appendChild(el("p", "gvt-muted", suggestion.note))
          }
          let listInput = null
          if (
            suggestion.invokeAction === "hubspot.lists.add_contact" &&
            !String(params.list_id || "").trim()
          ) {
            const label = el("div", "gvt-label", "HubSpot list id")
            listInput = document.createElement("input")
            listInput.className = "gvt-input"
            listInput.placeholder = "e.g. 15"
            listInput.value = ""
            confirmBox.appendChild(label)
            confirmBox.appendChild(listInput)
          }
          const row = el("div", "gvt-actions")
          const yes = el("button", "gvt-btn", "Approve & run")
          yes.type = "button"
          const no = el("button", "gvt-btn secondary", "Cancel")
          no.type = "button"
          no.addEventListener("click", () => {
            confirmBox.style.display = "none"
          })
          yes.addEventListener("click", () => {
            function finishWithToken(token) {
              yes.disabled = true
              chrome.runtime.sendMessage(
                {
                  type: "EXECUTE_ACTION",
                  confirmationToken: token,
                  pageUrl,
                },
                (exec) => {
                  yes.disabled = false
                  confirmBox.style.display = "none"
                  if (!exec?.ok) {
                    status.textContent = exec?.error || "Action failed"
                    return
                  }
                  const r = exec.result || {}
                  status.textContent = r.success
                    ? `Done — ${r.invokeAction}. Open Outcomes/Runs in Gravitree.`
                    : r.error || "Action did not succeed"
                },
              )
            }

            if (listInput) {
              const listId = String(listInput.value || "").trim()
              if (!listId) {
                status.textContent = "Enter a HubSpot list id to continue."
                return
              }
              // Re-stage with list_id — staged args are immutable after token issue.
              yes.disabled = true
              chrome.runtime.sendMessage(
                {
                  type: "EXECUTE_ACTION",
                  invokeAction: suggestion.invokeAction,
                  params: { ...params, list_id: listId },
                  pageUrl,
                },
                (pre) => {
                  if (!pre?.ok || pre.result?.status !== "needs_confirmation") {
                    yes.disabled = false
                    status.textContent = pre?.error || "Could not stage write with list id"
                    return
                  }
                  finishWithToken(pre.result.confirmationToken)
                },
              )
              return
            }

            const token = suggestion._confirmationToken
            if (!token) {
              status.textContent =
                "Missing server confirmation token — propose the action again."
              return
            }
            finishWithToken(token)
          })
          row.appendChild(yes)
          row.appendChild(no)
          confirmBox.appendChild(row)
        }

        ;(result.suggestions || []).forEach((suggestion) => {
          const btn = el("button", "gvt-btn", suggestion.label)
          btn.type = "button"
          btn.addEventListener("click", () => {
            const params =
              suggestion.params && Object.keys(suggestion.params).length
                ? { ...suggestion.params }
                : buildParamsForAction(suggestion.invokeAction, extracted, result)
            chrome.runtime.sendMessage(
              {
                type: "EXECUTE_ACTION",
                invokeAction: suggestion.invokeAction,
                params,
                pageUrl,
              },
              (pre) => {
                if (!pre?.ok) {
                  status.textContent = pre?.error || "Could not propose action"
                  return
                }
                if (pre.result?.status === "needs_confirmation") {
                  if (!pre.result.confirmationToken) {
                    status.textContent =
                      "Server did not issue a confirmation token — write blocked."
                    return
                  }
                  suggestion._confirmationToken = pre.result.confirmationToken
                  showConfirm(suggestion, pre.result.params || params)
                  return
                }
                status.textContent = pre.result?.success
                  ? "Done."
                  : pre.result?.error || "Finished"
              },
            )
          })
          actions.appendChild(btn)
        })

        const openApp = el("button", "gvt-btn secondary", "Open in Gravitree")
        openApp.type = "button"
        openApp.addEventListener("click", () => {
          const path = result.openInGravitreeUrl || "/ai"
          window.open(`https://gravitre.app${path.startsWith("/") ? path : `/${path}`}`, "_blank")
        })
        actions.appendChild(openApp)
        body.appendChild(actions)
        body.appendChild(confirmBox)
      },
    )
  }

  function buildParamsForAction(action, extracted, enrichResult) {
    const email = extracted.email || ""
    const first = extracted.firstName || (extracted.fullName || "").split(/\s+/)[0] || ""
    const last =
      extracted.lastName ||
      (extracted.fullName || "").split(/\s+/).slice(1).join(" ") ||
      ""
    if (action === "apollo.contacts.create") {
      return {
        first_name: first || "Unknown",
        last_name: last || "Contact",
        email: email || undefined,
        organization_name: extracted.company || undefined,
      }
    }
    if (action === "apollo.lists.create") {
      return {
        name: extracted.company
          ? `${extracted.company} — Extension`
          : `Extension list ${new Date().toISOString().slice(0, 10)}`,
        modality: "contacts",
      }
    }
    if (action === "apollo.lists.add") {
      const match = (enrichResult.matches || []).find(
        (m) => m.action === "apollo.people.match" && m.success,
      )
      const data = match?.data || {}
      const person = data.person || data.contact || data
      const id = person.id || person.contact_id || data.primary_contact_id
      return {
        entity_ids: id ? [String(id)] : [],
        label_names: ["Extension Prospects"],
        modality: "contacts",
      }
    }
    if (action === "hubspot.contacts.create") {
      return {
        properties: {
          email: email || undefined,
          firstname: first || undefined,
          lastname: last || "Contact",
          company: extracted.company || undefined,
          jobtitle: extracted.title || undefined,
        },
      }
    }
    if (action === "hubspot.lists.create") {
      return {
        name: extracted.company
          ? `${extracted.company} — Extension`
          : `Extension list ${new Date().toISOString().slice(0, 10)}`,
      }
    }
    if (action === "hubspot.lists.add_contact") {
      return {
        list_id: "",
        contact_id: "",
      }
    }
    return {}
  }

  window.__gravitreeOverlay = { renderOverlay, ensureRoot }
})()
