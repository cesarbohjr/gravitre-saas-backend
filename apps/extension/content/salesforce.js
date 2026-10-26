/** Salesforce: the Lead, Contact or Account record on screen. */
(function () {
  const textOf = (sel) => (document.querySelector(sel)?.textContent || "").replace(/\s+/g, " ").trim()
  const recordId = () => {
    const m = String(location.href).match(/\/lightning\/r\/(?:Lead|Contact|Account)\/([a-zA-Z0-9]{15,18})\//i) || String(location.href).match(/[?&]id=([a-zA-Z0-9]{15,18})/i)
    return m ? m[1] : ""
  }

  window.__gravitre?.register({
    kind: "crm",
    auto: () => Boolean(recordId()),
    anchor: () => document.querySelector("h1.slds-page-header__title, .entityNameTitle"),
    extract() {
      if (!recordId()) return {}
      const isAccount = /\/Account\//i.test(location.href)
      const name = textOf("lightning-formatted-name") || textOf("h1.slds-page-header__title") || textOf(".entityNameTitle")
      return {
        fullName: isAccount ? "" : name,
        company: isAccount ? name : textOf("records-record-layout-item[field-label='Company']"),
        email: document.querySelector("a[href^='mailto:']")?.getAttribute("href")?.replace(/^mailto:/i, "") || "",
        title: textOf("records-record-layout-item[field-label='Title']"),
        salesforceRecordId: recordId(),
        source: "salesforce",
      }
    },
  })
})()
