/** Slack web — extract visible person/company context; no message DOM automation. */
(function () {
  function extractSlack() {
    const fullName =
      document.querySelector("[data-qa='member_profile_name']")?.textContent?.replace(/\s+/g, " ").trim() ||
      document.querySelector(".p-ia__main_menu__user__name")?.textContent?.replace(/\s+/g, " ").trim() ||
      document.querySelector("[data-qa='message_sender_name']")?.textContent?.replace(/\s+/g, " ").trim() ||
      ""
    const emailMatch = document.body.innerText.match(
      /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i,
    )
    const title =
      document.querySelector("[data-qa='member_profile_field']")?.textContent?.replace(/\s+/g, " ").trim() ||
      ""
    return {
      fullName,
      email: emailMatch ? emailMatch[0] : "",
      title,
      source: "slack",
    }
  }

  function open() {
    if (!window.__gravitreeOverlay) return
    window.__gravitreeOverlay.renderOverlay({
      pageUrl: location.href,
      pageContext: extractSlack(),
    })
  }

  chrome.runtime.onMessage.addListener((msg) => {
    if (msg?.type === "OPEN_OVERLAY") open()
  })
})()
