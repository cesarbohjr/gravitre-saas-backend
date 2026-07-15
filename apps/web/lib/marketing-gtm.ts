/** Marketing Google Tag Manager + first-party Tag Gateway config. */

export const MARKETING_GTM_ID = "GTM-P9TXQF82"

/** Standard Google-hosted GTM loader (used by the marketing snippet). */
export const MARKETING_GTM_SCRIPT_SRC = `https://www.googletagmanager.com/gtm.js?id=${MARKETING_GTM_ID}`
export const MARKETING_GTM_NOSCRIPT_SRC = `https://www.googletagmanager.com/ns.html?id=${MARKETING_GTM_ID}`

/** Reserved first-party serving path (must not collide with app routes like /metrics). */
export const MARKETING_GTG_PATH = "/gtg"

/** Google FPS origin host for this GTM container (lowercase id). */
export const MARKETING_GTG_FPS_HOST = `${MARKETING_GTM_ID.toLowerCase()}.fps.goog`
