/** Outlook web context → Gravitre overlay. */
(function () {
  function extractOutlook() {
    const fullName =
      document.querySelector("[aria-label*='From']")?.textContent?.trim() ||
      document.querySelector(".allowTextSelection")?.textContent?.trim() ||
      ""
    const emailMatch = document.body.innerText.match(
      /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i,
    )
    return {
      fullName,
      email: emailMatch ? emailMatch[0] : "",
      source: "outlook",
    }
  }

  function open() {
    if (!window.__gravitreOverlay) return
    window.__gravitreOverlay.renderOverlay({
      pageUrl: location.href,
      pageContext: extractOutlook(),
    })
  }

  chrome.runtime.onMessage.addListener((msg) => {
    if (msg?.type === "OPEN_OVERLAY") open()
  })
})()
