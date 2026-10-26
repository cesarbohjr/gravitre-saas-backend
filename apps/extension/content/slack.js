/** Slack: the member whose profile is open. Reads only what's on screen; never touches messages. */
(function () {
  const clean = (node) => (node?.textContent || "").replace(/\s+/g, " ").trim()
  const profile = () => document.querySelector("[data-qa='member_profile_name']")

  window.__gravitre?.register({
    kind: "people",
    auto: () => Boolean(profile()),
    anchor: profile,
    extract() {
      const name = profile()
      if (!name) return {}
      const el = document.querySelector("[data-member-id], [data-qa-user-id], [data-user-id]")
      return {
        fullName: clean(name),
        title: clean(document.querySelector("[data-qa='member_profile_field']")),
        slackUserId: el?.getAttribute("data-member-id") || el?.getAttribute("data-qa-user-id") || el?.getAttribute("data-user-id") || "",
        source: "slack",
      }
    },
  })
})()
