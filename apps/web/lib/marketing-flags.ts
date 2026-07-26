/** Flip to true when real customer testimonials are ready to publish. */
export const SHOW_MARKETING_TESTIMONIALS = false

/**
 * Research Lookups on /pricing and in-app billing — on by default.
 * Set NEXT_PUBLIC_INTERNET_RESEARCH_ENABLED=false to hide until billing go-live.
 */
export const SHOW_RESEARCH_LOOKUPS_PRICING =
  process.env.NEXT_PUBLIC_INTERNET_RESEARCH_ENABLED !== "false"
