/** Gmail thread context → Gravitre overlay (user-invoked via action). */
(function () {
  function extractGmail() {
    const email =
      document.querySelector("span[email]")?.getAttribute("email") ||
      document.querySelector("[data-hovercard-id]")?.getAttribute("data-hovercard-id") ||
      ""
    const fullName =
      document.querySelector("span[email]")?.getAttribute("name") ||
      document.querySelector("h2.hP")?.textContent?.trim() ||
      ""
    const subject = document.querySelector("h2.hP")?.textContent?.trim() || ""
    return {
      email,
      fullName,
      title: subject ? `Email: ${subject}` : undefined,
      source: "gmail",
    }
  }

  function open() {
    if (!window.__gravitreOverlay) return
    window.__gravitreOverlay.renderOverlay({
      pageUrl: location.href,
      pageContext: extractGmail(),
    })
  }

  chrome.runtime.onMessage.addListener((msg) => {
    if (msg?.type === "OPEN_OVERLAY") open()
  })
})()
