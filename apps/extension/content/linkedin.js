/** LinkedIn profile page context → Gravitre overlay. */
(function () {
  function textOf(sel) {
    const node = document.querySelector(sel)
    return (node?.textContent || "").replace(/\s+/g, " ").trim()
  }

  function extractLinkedInProfile() {
    const fullName =
      textOf("h1") ||
      textOf(".text-heading-xlarge") ||
      textOf("[data-anonymize='person-name']")
    const headline =
      textOf(".text-body-medium") ||
      textOf("[data-anonymize='headline']") ||
      textOf(".pv-text-details__left-panel .text-body-medium")
    const company =
      textOf("[data-field='experience_company_logo']") ||
      textOf(".pv-text-details__right-panel .inline-show-more-text") ||
      ""
    return {
      fullName,
      title: headline,
      company,
      linkedinUrl: location.href,
      source: "linkedin",
    }
  }

  function maybeOpen() {
    if (!/linkedin\.com\/in\//i.test(location.href)) return
    if (!window.__gravitreOverlay) return
    window.__gravitreOverlay.renderOverlay({
      pageUrl: location.href,
      pageContext: extractLinkedInProfile(),
    })
  }

  // Auto-open on profile; also listen for toolbar message.
  setTimeout(maybeOpen, 1200)
  chrome.runtime.onMessage.addListener((msg) => {
    if (msg?.type === "OPEN_OVERLAY") maybeOpen()
  })
})()
