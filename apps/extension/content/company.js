/** Any other site the person allowed: the company behind the page. */
(function () {
  const domain = location.hostname.replace(/^www\./, "")
  const path = location.pathname.toLowerCase()
  const careers = ["/careers", "/career", "/jobs", "/about", "/company", "/team"].some((m) => path.includes(m))

  window.__gravitre?.register({
    kind: "company",
    auto: () => false,
    extract() {
      const site = document.querySelector("meta[property='og:site_name']")?.getAttribute("content")?.trim()
      const h1 = document.querySelector("h1")?.textContent?.replace(/\s+/g, " ").trim() || ""
      return {
        company: site || document.title.split(/[-|·]/).pop().trim() || domain,
        domain,
        title: h1 || document.title,
        source: careers ? "careers_about" : "company_site",
        pageKind: careers ? "careers_about" : "company_site",
      }
    },
  })
})()
