/** Flip to true when real customer testimonials are ready to publish. */
export const SHOW_MARKETING_TESTIMONIALS = false

/**
 * Research Lookups on /pricing and in-app billing — gated until technical go-live.
 * Set NEXT_PUBLIC_INTERNET_RESEARCH_ENABLED=true on Vercel when Railway
 * INTERNET_RESEARCH_ENABLED=true and live verification has passed.
 */
export const SHOW_RESEARCH_LOOKUPS_PRICING =
  process.env.NEXT_PUBLIC_INTERNET_RESEARCH_ENABLED === "true"
