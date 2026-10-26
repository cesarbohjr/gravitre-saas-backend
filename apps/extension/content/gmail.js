/** Gmail: the sender of the open thread. */
(function () {
  const onThread = () => Boolean(document.querySelector("h2.hP"))

  window.__gravitre?.register({
    kind: "email",
    auto: onThread,
    anchor: () => document.querySelector("h2.hP"),
    extract() {
      if (!onThread()) return {}
      const sender = document.querySelector(".gD[email]") || document.querySelector("span[email]")
      const subject = document.querySelector("h2.hP")?.textContent?.trim() || ""
      return {
        email: sender?.getAttribute("email") || "",
        fullName: sender?.getAttribute("name") || sender?.textContent?.trim() || "",
        subject,
        source: "gmail",
      }
    },
  })
})()
