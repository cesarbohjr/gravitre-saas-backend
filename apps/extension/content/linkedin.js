/** LinkedIn: the person on a profile page. */
(function () {
  const textOf = (sel) => (document.querySelector(sel)?.textContent || "").replace(/\s+/g, " ").trim()
  const onProfile = () => /linkedin\.com\/in\//i.test(location.href)

  window.__gravitre?.register({
    kind: "people",
    auto: onProfile,
    anchor: () => (onProfile() ? document.querySelector("main h1") || document.querySelector("h1") : null),
    extract() {
      if (!onProfile()) return {}
      const headline = textOf(".text-body-medium") || textOf("[data-anonymize='headline']")
      const company = textOf("[data-field='experience_company_logo']") || textOf(".pv-text-details__right-panel .inline-show-more-text")
      return {
        fullName: textOf("main h1") || textOf(".text-heading-xlarge") || textOf("[data-anonymize='person-name']"),
        title: headline,
        company,
        linkedinUrl: location.href,
        source: "linkedin",
      }
    },
  })
})()
