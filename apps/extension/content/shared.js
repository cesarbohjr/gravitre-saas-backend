/** Shared overlay renderer for Gravitre content scripts. */
(function () {
  if (window.__gravitreOverlay) return

  function el(tag, className, text) {
    const node = document.createElement(tag)
    if (className) node.className = className
    if (text != null) node.textContent = text
    return node
  }

  /** Compact BusinessOutcome evidence — matched preview for connector writes. */
  function renderBusinessOutcomeCard(parent, result) {
    const bo = result?.businessOutcome
    if (!bo || typeof bo !== "object") return false
    const sections = bo.sections || {}
    const card = el("div", "gvt-outcome")
    card.appendChild(el("div", "gvt-outcome-title", bo.title || result.invokeAction || "Completed work"))
    const summary = sections.summary || result.error || ""
    if (summary) card.appendChild(el("p", "gvt-outcome-summary", String(summary).slice(0, 400)))
    const ver = sections.verification
    const status = String(bo.status || "").toLowerCase()
    const reviewState = String(ver?.reviewState || "").toLowerCase()
    const flagged = status === "flagged_for_review" || reviewState === "flagged_for_review"
    if (ver && typeof ver === "object") {
      const badgeClass = flagged
        ? "gvt-outcome-flagged"
        : ver.verified
          ? "gvt-outcome-verified"
          : "gvt-outcome-unverified"
      const badgeLabel = flagged
        ? "Flagged for review"
        : ver.verified
          ? "Verified evidence"
          : "Not verified"
      const badge = el("div", badgeClass, badgeLabel)
      card.appendChild(badge)
      if (ver.finding) {
        card.appendChild(el("p", "gvt-outcome-finding", String(ver.finding).slice(0, 280)))
      }
      if (Array.isArray(ver.nextActions) && ver.nextActions.length) {
        const list = el("ul", "gvt-outcome-next")
        ver.nextActions.slice(0, 3).forEach((line) => {
          list.appendChild(el("li", null, String(line)))
        })
        card.appendChild(list)
      }
    }
    const links = (sections.evidence && sections.evidence.links) || []
    if (links.length) {
      const row = el("div", "gvt-outcome-links")
      links.slice(0, 4).forEach((link) => {
        if (!link?.href) return
        const a = document.createElement("a")
        a.className = "gvt-outcome-link"
        a.href = String(link.href).startsWith("http")
          ? link.href
          : `https://gravitre.app${link.href.startsWith("/") ? "" : "/"}${link.href}`
        a.target = "_blank"
        a.rel = "noopener noreferrer"
        a.textContent = link.label || "Open"
        row.appendChild(a)
      })
      card.appendChild(row)
    } else if (result.runId || result.businessOutcomeUrl || result.outcomeUrl) {
      const row = el("div", "gvt-outcome-links")
      const href =
        result.outcomeUrl ||
        result.businessOutcomeUrl ||
        `/runs/${result.runId}`
      const a = document.createElement("a")
      a.className = "gvt-outcome-link"
      a.href = String(href).startsWith("http") ? href : `https://gravitre.app${href}`
      a.target = "_blank"
      a.rel = "noopener noreferrer"
      a.textContent = "Open in Activity / Runs"
      row.appendChild(a)
      card.appendChild(row)
    }
    parent.appendChild(card)
    return true
  }

  function showExecuteResult(statusEl, cardEl, result) {
    const r = result || {}
    if (renderBusinessOutcomeCard(cardEl, r)) {
      statusEl.textContent = r.success ? "Done — evidence below." : r.error || "Finished with evidence."
      return
    }
    statusEl.textContent = r.success
      ? `Done — ${r.invokeAction || "action"}. Open Activity in Gravitre.`
      : r.error || "Action did not succeed"
  }

  function ensureRoot() {
    let root = document.getElementById("gravitre-overlay-root")
    if (root) return root
    root = el("div")
    root.id = "gravitre-overlay-root"
    document.documentElement.appendChild(root)
    return root
  }

  function renderOverlay({ pageContext, pageUrl }) {
    const root = ensureRoot()
    root.innerHTML = ""
    const card = el("div", "gvt-card")
    const header = el("div", "gvt-header")
    header.appendChild(el("div", "gvt-brand", "Gravitre"))
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
                  showExecuteResult(status, card, exec.result || {})
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
                showExecuteResult(status, card, pre.result || {})
              },
            )
          })
          actions.appendChild(btn)
        })

        // v3 — lightweight workflow trigger (chat plan-bar / confirm pattern)
        const wfBox = el("div", "gvt-row")
        wfBox.appendChild(el("div", "gvt-label", "Workflows"))
        const wfStatus = el("p", "gvt-muted", "Loading workflows…")
        wfBox.appendChild(wfStatus)
        const wfList = el("div", "gvt-actions")
        wfBox.appendChild(wfList)
        body.appendChild(wfBox)

        chrome.runtime.sendMessage({ type: "LIST_WORKFLOWS" }, (wfRes) => {
          if (!wfRes?.ok) {
            wfStatus.textContent = wfRes?.error || "Could not load workflows"
            return
          }
          const workflows = wfRes.result?.workflows || []
          if (!workflows.length) {
            wfStatus.textContent = "No active multi-step workflows."
            return
          }
          wfStatus.textContent =
            "Select a workflow — same typed-contract execute path as chat."
          workflows.slice(0, 5).forEach((wf) => {
            const btn = el(
              "button",
              "gvt-btn secondary",
              `${wf.name} (${wf.stepCount} steps)`,
            )
            btn.type = "button"
            btn.addEventListener("click", () => {
              const plan = el("div", "gvt-confirm")
              plan.appendChild(
                el("p", null, `Plan: ${wf.name} — approve to run all steps.`),
              )
              const stepEls = []
              ;(wf.progressSteps || []).forEach((step, i) => {
                const label = step.label || step.name || `Step ${i + 1}`
                const line = el(
                  "div",
                  "gvt-step gvt-step-pending",
                  `${i + 1}. ${label}${step.action ? ` · ${step.action}` : ""}`,
                )
                line.dataset.stepIndex = String(i)
                stepEls.push(line)
                plan.appendChild(line)
              })
              const row = el("div", "gvt-actions")
              const yes = el("button", "gvt-btn", "Approve & run workflow")
              yes.type = "button"
              const no = el("button", "gvt-btn secondary", "Cancel")
              no.type = "button"
              no.addEventListener("click", () => plan.remove())
              yes.addEventListener("click", () => {
                yes.disabled = true
                stepEls.forEach((line) => {
                  line.className = "gvt-step gvt-step-running"
                })
                status.textContent = "Running workflow — named steps below…"
                chrome.runtime.sendMessage(
                  {
                    type: "EXECUTE_WORKFLOW",
                    workflowId: wf.id,
                    pageUrl,
                    parameters: {},
                  },
                  (pre) => {
                    if (!pre?.ok || pre.result?.status !== "needs_confirmation") {
                      yes.disabled = false
                      stepEls.forEach((line) => {
                        line.className = "gvt-step gvt-step-pending"
                      })
                      status.textContent = pre?.error || "Could not stage workflow"
                      return
                    }
                    const staged = pre.result.progressSteps || wf.progressSteps || []
                    staged.forEach((step, i) => {
                      if (!stepEls[i]) return
                      const label = step.label || step.name || `Step ${i + 1}`
                      stepEls[i].textContent = `${i + 1}. ${label}${
                        step.action ? ` · ${step.action}` : ""
                      }`
                      stepEls[i].className = "gvt-step gvt-step-running"
                    })
                    const token = pre.result.confirmationToken
                    chrome.runtime.sendMessage(
                      {
                        type: "EXECUTE_WORKFLOW",
                        confirmationToken: token,
                        pageUrl,
                      },
                      (exec) => {
                        yes.disabled = true
                        yes.textContent = "Ran"
                        no.disabled = true
                        if (!exec?.ok) {
                          yes.disabled = false
                          yes.textContent = "Approve & run workflow"
                          status.textContent = exec?.error || "Workflow failed"
                          stepEls.forEach((line) => {
                            line.className = "gvt-step gvt-step-failed"
                          })
                          return
                        }
                        const r = exec.result || {}
                        const done = r.progressSteps || staged
                        done.forEach((step, i) => {
                          if (!stepEls[i]) return
                          const label = step.label || step.name || `Step ${i + 1}`
                          const st = String(step.status || r.status || "completed")
                          stepEls[i].textContent = `${i + 1}. ${label}${
                            step.action ? ` · ${step.action}` : ""
                          } — ${st}`
                          stepEls[i].className =
                            st === "completed" || st === "running"
                              ? `gvt-step gvt-step-${st === "completed" ? "done" : "running"}`
                              : "gvt-step gvt-step-failed"
                        })
                        if (r.runId && !renderBusinessOutcomeCard(card, r)) {
                          status.textContent = `Workflow ${r.status} — open Activity for evidence.`
                        } else if (!r.runId) {
                          status.textContent = r.error || "Workflow finished"
                        } else {
                          status.textContent = `Workflow ${r.status} — named steps + evidence below.`
                        }
                      },
                    )
                  },
                )
              })
              row.appendChild(yes)
              row.appendChild(no)
              plan.appendChild(row)
              wfBox.appendChild(plan)
            })
            wfList.appendChild(btn)
          })
        })

        // v4 — lightweight chat (same unified-turn path as main chat)
        const chatBox = el("div", "gvt-row")
        chatBox.appendChild(el("div", "gvt-label", "Ask about this page"))
        const chatInput = el("textarea", "gvt-chat-input")
        chatInput.rows = 2
        chatInput.placeholder = "Quick question (page context included)…"
        chatBox.appendChild(chatInput)
        const chatReply = el("p", "gvt-muted", "")
        chatBox.appendChild(chatReply)
        const chatActions = el("div", "gvt-actions")
        const askBtn = el("button", "gvt-btn", "Ask")
        askBtn.type = "button"
        const continueBtn = el("button", "gvt-btn secondary", "Continue in Gravitre")
        continueBtn.type = "button"
        continueBtn.style.display = "none"
        let lastHandoffUrl = result.openInGravitreUrl || result.openInGravitreeUrl || "/ai"
        let conversationId = null
        askBtn.addEventListener("click", () => {
          const message = (chatInput.value || "").trim()
          if (!message) {
            chatReply.textContent = "Type a short question first."
            return
          }
          askBtn.disabled = true
          chatReply.textContent = "Thinking…"
          chrome.runtime.sendMessage(
            {
              type: "CHAT",
              message,
              pageUrl,
              pageContext,
              conversationId,
            },
            (chatRes) => {
              askBtn.disabled = false
              if (!chatRes?.ok) {
                chatReply.textContent = chatRes?.error || "Chat failed"
                return
              }
              const r = chatRes.result || {}
              conversationId = r.conversationId || conversationId
              chatReply.textContent = r.answer || "(no answer)"
              if (r.businessOutcome) {
                renderBusinessOutcomeCard(card, r)
              }
              if (r.openInGravitreUrl || r.openInGravitreeUrl) {
                lastHandoffUrl = r.openInGravitreUrl || r.openInGravitreeUrl
              }
              continueBtn.style.display = ""
              if (r.needsHandoff) {
                const reason = String(r.handoffReason || "")
                if (reason === "multi_step_progress") {
                  status.textContent =
                    "Multi-step work — continue in Gravitre for the progress panel (same thread)."
                  continueBtn.textContent = "Open progress in Gravitre"
                } else if (
                  reason === "action_or_write_intent" ||
                  reason === "tool_write_path" ||
                  reason === "approval_required"
                ) {
                  status.textContent =
                    "Writes/approvals need full Gravitre chat — same conversation thread."
                  continueBtn.textContent = "Continue in Gravitre"
                } else {
                  status.textContent =
                    "Continue in Gravitre — same conversation thread."
                  continueBtn.textContent = "Continue in Gravitre"
                }
              } else {
                continueBtn.textContent = "Open thread in Gravitre"
                status.textContent =
                  "Answered here — open the same thread in Gravitre anytime."
              }
            },
          )
        })
        continueBtn.addEventListener("click", () => {
          let path = lastHandoffUrl || "/ai"
          // Prefer same conversation id even if URL omitted.
          if (conversationId && !/[?&]c=/.test(path)) {
            const base = path.split("?")[0] || "/ai"
            const rest = path.includes("?") ? path.slice(path.indexOf("?") + 1) : ""
            path = `${base}?c=${encodeURIComponent(conversationId)}${rest ? `&${rest}` : ""}`
          }
          window.open(
            `https://gravitre.app${path.startsWith("/") ? path : `/${path}`}`,
            "_blank",
          )
        })
        chatActions.appendChild(askBtn)
        chatActions.appendChild(continueBtn)
        chatBox.appendChild(chatActions)
        body.appendChild(chatBox)

        const openApp = el("button", "gvt-btn secondary", "Open in Gravitre")
        openApp.type = "button"
        openApp.addEventListener("click", () => {
          const path =
            lastHandoffUrl || result.openInGravitreUrl || result.openInGravitreeUrl || "/ai"
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

  window.__gravitreOverlay = {
    renderOverlay,
    ensureRoot,
    renderBusinessOutcomeCard,
    showExecuteResult,
  }
  // Legacy alias for content scripts still reading __gravitreeOverlay.
  window.__gravitreeOverlay = window.__gravitreOverlay
})()
