/** Company website / careers / about (activeTab inject) → firmographic overlay. */
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
    const path = (location.pathname || "").toLowerCase()
    const careersMarkers = ["/careers", "/career", "/jobs", "/job", "/about", "/about-us", "/company", "/team"]
    const isCareersAbout = careersMarkers.some((m) => path.includes(m))
    const company = h1 || title.split(/[-|·]/)[0].trim() || domain
    return {
      company,
      domain,
      title: h1 || title,
      source: isCareersAbout ? "careers_about" : "company_site",
      pageKind: isCareersAbout ? "careers_about" : "company_site",
    }
  }

  if (!window.__gravitreeOverlay) return
  window.__gravitreeOverlay.renderOverlay({
    pageUrl: location.href,
    pageContext: extractCompanySite(),
  })
})()
