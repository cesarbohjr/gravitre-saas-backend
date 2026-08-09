/** Salesforce Lightning / Classic — page context only; catalog for reads/writes. */
(function () {
  function textOf(sel) {
    const node = document.querySelector(sel)
    return (node?.textContent || "").replace(/\s+/g, " ").trim()
  }

  function extractRecordId() {
    const href = String(location.href || "")
    const m =
      href.match(/\/lightning\/r\/(?:Lead|Contact|Account)\/([a-zA-Z0-9]{15,18})\//i) ||
      href.match(/[?&]id=([a-zA-Z0-9]{15,18})/i)
    return m ? m[1] : ""
  }

  function extractSalesforce() {
    const fullName =
      textOf(".entityNameTitle") ||
      textOf("lightning-formatted-name") ||
      textOf("h1.slds-page-header__title") ||
      textOf("h1") ||
      ""
    const company =
      textOf("[data-target-selection-name*='Company']") ||
      textOf("records-record-layout-item[field-label='Company']") ||
      ""
    const email =
      document.querySelector("a[href^='mailto:']")?.getAttribute("href")?.replace(/^mailto:/i, "") ||
      ""
    const title =
      textOf("[data-target-selection-name*='Title']") ||
      textOf("records-record-layout-item[field-label='Title']") ||
      ""
    return {
      fullName,
      company,
      email,
      title,
      salesforceRecordId: extractRecordId(),
      source: "salesforce",
    }
  }

  function open() {
    if (!window.__gravitreOverlay) return
    window.__gravitreOverlay.renderOverlay({
      pageUrl: location.href,
      pageContext: extractSalesforce(),
    })
  }

  chrome.runtime.onMessage.addListener((msg) => {
    if (msg?.type === "OPEN_OVERLAY") open()
  })
})()
