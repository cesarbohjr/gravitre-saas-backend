/** Company website (activeTab inject) → firmographic overlay. */
(function () {
  function extractCompanySite() {
    const title = document.title || ""
    const h1 = document.querySelector("h1")?.textContent?.replace(/\s+/g, " ").trim() || ""
    let domain = ""
    try {
      domain = location.hostname.replace(/^www\./, "")
    } catch {
      domain = ""
    }
    const company = h1 || title.split(/[-|·]/)[0].trim() || domain
    return {
      company,
      domain,
      title: h1 || title,
      source: "company_site",
    }
  }

  if (!window.__gravitreeOverlay) return
  window.__gravitreeOverlay.renderOverlay({
    pageUrl: location.href,
    pageContext: extractCompanySite(),
  })
})()
