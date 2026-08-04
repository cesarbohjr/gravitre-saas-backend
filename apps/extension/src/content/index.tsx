// Content-script entry. Replaces the old imperative `content/shared.js`
// renderer with a React overlay mounted into a Shadow DOM.
//
// Why Shadow DOM: the previous implementation appended a plain <div> to
// document.documentElement and injected global CSS. That works for a handful
// of hand-written rules, but this rebuild uses Tailwind, whose preflight
// resets every element. Injecting that globally would visibly break Gmail,
// LinkedIn and Salesforce. A shadow root gives us full styling freedom with
// zero chance of leaking into the host page, and equally stops the host
// page's own CSS (LinkedIn ships very aggressive global rules) from
// distorting our card.

import { Overlay } from "./overlay"
import { mountOverlay, unmountOverlay } from "./mount"
import type { PageContext, Surface } from "@/lib/types"

/* ---------------------------------- surface --------------------------------- */

// Mirrors manifest.json's content_scripts list. On these hosts the script is
// already running, so the popup drives opening via OPEN_OVERLAY and we must
// not self-open on load (that would pop the card up unprompted on every
// visit). Anywhere else arrives by activeTab injection and self-opens.
const DECLARED: Surface[] = [
  "linkedin",
  "gmail",
  "outlook",
  "salesforce",
  "slack",
]

function detectSurface(): Surface {
  const h = location.hostname
  if (h.includes("linkedin.")) return "linkedin"
  if (h.includes("mail.google.")) return "gmail"
  if (h.includes("outlook.")) return "outlook"
  if (h.includes("force.com") || h.includes("salesforce.")) return "salesforce"
  if (h.includes("slack.")) return "slack"
  return "company"
}

/* --------------------------------- extractors -------------------------------
 * Ported from content/*.js. These selectors are load-bearing knowledge about
 * each host page's DOM, so they are carried over as-is rather than rewritten —
 * a redesign must not change what data we can read.
 * ---------------------------------------------------------------------------*/

const text = (sel: string, root: ParentNode = document): string =>
  (root.querySelector(sel) as HTMLElement | null)?.innerText?.trim() ?? ""

function extractLinkedIn(): PageContext {
  return {
    surface: "linkedin",
    url: location.href,
    companyName:
      text(".org-top-card-summary__title") ||
      text("h1.top-card-layout__title") ||
      text("h1"),
    industry:
      text(".org-top-card-summary-info-list__info-item") ||
      text(".top-card-layout__headline"),
    personName: text(".text-heading-xlarge") || undefined,
  }
}

function extractGmail(): PageContext {
  const sender =
    (document.querySelector("span[email]") as HTMLElement | null)?.getAttribute(
      "email",
    ) ?? ""
  const domain = sender.includes("@") ? sender.split("@")[1] : ""
  return {
    surface: "gmail",
    url: location.href,
    email: sender || undefined,
    emailDomain: domain || undefined,
    companyName: domain ? domain.replace(/\.(com|io|co|net|org)$/, "") : "",
    subject: text("h2.hP") || undefined,
  }
}

function extractOutlook(): PageContext {
  const sender =
    (document.querySelector("[data-lpc-hover-target-id]") as HTMLElement | null)
      ?.innerText?.trim() ?? ""
  const email = sender.match(/[\w.+-]+@[\w-]+\.[\w.]+/)?.[0] ?? ""
  const domain = email.includes("@") ? email.split("@")[1] : ""
  return {
    surface: "outlook",
    url: location.href,
    email: email || undefined,
    emailDomain: domain || undefined,
    companyName: domain ? domain.replace(/\.(com|io|co|net|org)$/, "") : "",
    subject: text('[role="heading"]') || undefined,
  }
}

function extractSalesforce(): PageContext {
  return {
    surface: "salesforce",
    url: location.href,
    companyName:
      text('[data-aura-class="uiOutputText"]') ||
      text("h1 .custom-truncate") ||
      text("h1"),
  }
}

function extractSlack(): PageContext {
  return {
    surface: "slack",
    url: location.href,
    companyName: text(".p-classic_nav__team_header__team_name") || "",
    channel: text(".p-view_header__channel_title") || undefined,
  }
}

// Ported from content/company.js. On an arbitrary company site the extension
// distinguishes a careers/about page from a generic page and passes that along
// as `pageKind`, which the backend uses to pick an enrichment strategy. Real
// capability, so it is preserved rather than dropped.
function extractCompanySite(): PageContext {
  const title = document.title || ""
  const h1 =
    document.querySelector("h1")?.textContent?.replace(/\s+/g, " ").trim() || ""
  const domain = location.hostname.replace(/^www\./, "")
  const path = (location.pathname || "").toLowerCase()
  const isCareersAbout = [
    "/careers",
    "/career",
    "/jobs",
    "/job",
    "/about",
    "/about-us",
    "/company",
    "/team",
  ].some((m) => path.includes(m))
  return {
    surface: "company",
    url: location.href,
    companyName: h1 || title.split(/[-|·]/)[0].trim() || domain,
    domain,
    title: h1 || title,
    pageKind: isCareersAbout ? "careers_about" : "company_site",
  }
}

function extractContext(surface: Surface): PageContext {
  switch (surface) {
    case "linkedin":
      return extractLinkedIn()
    case "gmail":
      return extractGmail()
    case "outlook":
      return extractOutlook()
    case "salesforce":
      return extractSalesforce()
    case "slack":
      return extractSlack()
    default:
      return extractCompanySite()
  }
}

/* ----------------------------------- open ----------------------------------- */

function open() {
  const context = extractContext(detectSurface())
  mountOverlay(() => (
    <Overlay
      pageUrl={location.href}
      pageContext={context as unknown as Record<string, unknown>}
      onClose={unmountOverlay}
    />
  ))
}

/* --------------------------------- messaging -------------------------------
 * Message type strings are a wire contract with the service worker and popup,
 * so they are preserved exactly and this rebuild stays drop-in.
 * ---------------------------------------------------------------------------*/

// A fresh activeTab injection has no marker, so it opens itself — mirroring
// the old content/company.js IIFE, which rendered on evaluation. Declared
// surfaces wait to be asked.
const marker = "__gravitreOverlayReady"
const w = window as unknown as Record<string, unknown>
const alreadyInjected = w[marker] === true
w[marker] = true

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg?.type === "OPEN_OVERLAY") {
    open()
    // Responding is what tells the popup a content script lives here, so it
    // does not also fire the INJECT_COMPANY_OVERLAY fallback and double-mount.
    sendResponse?.({ ok: true })
    return
  }
  if (msg?.type === "CLOSE_OVERLAY") {
    unmountOverlay()
    sendResponse?.({ ok: true })
  }
})

if (!alreadyInjected && !DECLARED.includes(detectSurface())) {
  open()
}

export {}
