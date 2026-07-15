/** Marketing Google Tag Manager + first-party Tag Gateway config. */

export const MARKETING_GTM_ID = "GTM-P9TXQF82"

/** Reserved first-party serving path (must not collide with app routes like /metrics). */
export const MARKETING_GTG_PATH = "/gtg"

/** Google FPS origin host for this GTM container (lowercase id). */
export const MARKETING_GTG_FPS_HOST = `${MARKETING_GTM_ID.toLowerCase()}.fps.goog`
