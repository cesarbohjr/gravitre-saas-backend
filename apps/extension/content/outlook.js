/** Outlook on the web: the sender of the open message. */
(function () {
  const reading = () => document.querySelector("[aria-label='Reading Pane'], [aria-label='Message body']")

  window.__gravitre?.register({
    kind: "email",
    auto: () => Boolean(reading()),
    extract() {
      const pane = reading()
      if (!pane) return {}
      const from = document.querySelector("[aria-label^='From'], [aria-label*=' From ']")
      const text = (from?.textContent || "").trim()
      const email = (text.match(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i) || [""])[0]
      return {
        fullName: text.replace(email, "").replace(/[<>]/g, "").trim(),
        email,
        subject: document.querySelector("[role='heading'][aria-level='2']")?.textContent?.trim() || "",
        source: "outlook",
      }
    },
  })
})()
