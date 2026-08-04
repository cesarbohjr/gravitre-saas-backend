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
// already running, so the popup drives opening via OPEN_OVERLAY. Anywhere else
// arrives by activeTab injection and self-opens.
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
 * Ported verbatim from the old content/*.js files. Both the CSS selectors and
 * the emitted key names are load-bearing:
 *
 *   - The selectors encode hard-won knowledge of each host page's DOM.
 *   - The keys (`fullName`, `company`, `email`, `domain`, `title`, `source`)
 *     are the wire contract `enrich_from_page_context` reads. Renaming them
 *     yields a silently empty enrichment.
 *
 * A visual redesign must not change what data we can read, so nothing here is
 * "improved" — only moved.
 * ---------------------------------------------------------------------------*/

/** textContent with collapsed whitespace, matching the original `textOf`. */
function textOf(sel: string): string {
  const node = document.querySelector(sel)
  return (node?.textContent || "").replace(/\s+/g, " ").trim()
}

const EMAIL_RE = /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i

function extractLinkedIn(): PageContext {
  return {
    fullName:
      textOf("h1") ||
      textOf(".text-heading-xlarge") ||
      textOf("[data-anonymize='person-name']"),
    title:
      textOf(".text-body-medium") ||
      textOf("[data-anonymize='headline']") ||
      textOf(".pv-text-details__left-panel .text-body-medium"),
    company:
      textOf("[data-field='experience_company_logo']") ||
      textOf(".pv-text-details__right-panel .inline-show-more-text") ||
      "",
    linkedinUrl: location.href,
    source: "linkedin",
  }
}

function extractGmail(): PageContext {
  const sender = document.querySelector("span[email]")
  const subject = document.querySelector("h2.hP")?.textContent?.trim() || ""
  return {
    email:
      sender?.getAttribute("email") ||
      document
        .querySelector("[data-hovercard-id]")
        ?.getAttribute("data-hovercard-id") ||
      "",
    fullName: sender?.getAttribute("name") || subject || "",
    title: subject ? `Email: ${subject}` : undefined,
    source: "gmail",
  }
}

function extractOutlook(): PageContext {
  const emailMatch = document.body.innerText.match(EMAIL_RE)
  return {
    fullName:
      document.querySelector("[aria-label*='From']")?.textContent?.trim() ||
      document.querySelector(".allowTextSelection")?.textContent?.trim() ||
      "",
    email: emailMatch ? emailMatch[0] : "",
    source: "outlook",
  }
}

function extractSalesforce(): PageContext {
  return {
    fullName:
      textOf(".entityNameTitle") ||
      textOf("lightning-formatted-name") ||
      textOf("h1.slds-page-header__title") ||
      textOf("h1") ||
      "",
    company:
      textOf("[data-target-selection-name*='Company']") ||
      textOf("records-record-layout-item[field-label='Company']") ||
      "",
    email:
      document
        .querySelector("a[href^='mailto:']")
        ?.getAttribute("href")
        ?.replace(/^mailto:/i, "") || "",
    title:
      textOf("[data-target-selection-name*='Title']") ||
      textOf("records-record-layout-item[field-label='Title']") ||
      "",
    source: "salesforce",
  }
}

function extractSlack(): PageContext {
  const emailMatch = document.body.innerText.match(EMAIL_RE)
  return {
    fullName:
      textOf("[data-qa='member_profile_name']") ||
      textOf(".p-ia__main_menu__user__name") ||
      textOf("[data-qa='message_sender_name']") ||
      "",
    email: emailMatch ? emailMatch[0] : "",
    title: textOf("[data-qa='member_profile_field']") || "",
    source: "slack",
  }
}

// From content/company.js. On an arbitrary site the extension distinguishes a
// careers/about page from a generic one and passes that as `source`/`pageKind`,
// which the backend uses to pick an enrichment strategy.
function extractCompanySite(): PageContext {
  const docTitle = document.title || ""
  const h1 = textOf("h1")
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
    company: h1 || docTitle.split(/[-|·]/)[0].trim() || domain,
    domain,
    title: h1 || docTitle,
    source: isCareersAbout ? "careers_about" : "company_site",
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
  // Extracted once per open, outside the render callback, so the object identity
  // stays stable — Overlay's enrich effect keys off `pageContext`, and a fresh
  // literal each render would re-fire the request in a loop.
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

if (!alreadyInjected) {
  const surface = detectSurface()
  if (!DECLARED.includes(surface)) {
    // Fresh activeTab injection: no message follows, so open immediately —
    // mirroring the old content/company.js IIFE.
    open()
  } else if (surface === "linkedin" && /linkedin\.com\/in\//i.test(location.href)) {
    // Preserved from content/linkedin.js: a LinkedIn *profile* auto-opened
    // after a short delay, because the profile header hydrates late and an
    // immediate read returns empty strings. Other declared surfaces stay
    // user-invoked.
    setTimeout(() => {
      if (!document.getElementById("gravitre-overlay-root")) open()
    }, 1200)
  }
}

export {}
