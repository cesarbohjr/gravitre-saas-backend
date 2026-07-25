/** Shared typography tokens for every in-product chat surface. */

export const CHAT_ROLE_LABEL_CLASS =
  "mb-1.5 px-1 text-[11px] font-medium text-muted-foreground"

export const CHAT_BUBBLE_BASE_CLASS =
  "w-full rounded-[1.15rem] px-4 py-3 text-[15px] leading-relaxed"

// Solid emerald so the user's own words read as the brand voice; a hairline
// inner ring keeps the edge crisp over any background theme.
export const CHAT_USER_BUBBLE_CLASS =
  "rounded-tr-sm bg-emerald-600 text-white shadow-sm ring-1 ring-inset ring-emerald-400/20 dark:bg-emerald-600"

// Opaque card fill + defined border/shadow so assistant text stays legible
// even over the textured background themes at every breakpoint.
export const CHAT_ASSISTANT_BUBBLE_CLASS =
  "rounded-tl-sm border border-border/70 bg-card text-foreground shadow-sm ring-1 ring-black/[0.02] dark:ring-white/[0.04]"

export const CHAT_BODY_TEXT_CLASS = "text-[15px] leading-relaxed"

export const CHAT_PROSE_CLASS =
  "prose prose-sm max-w-none dark:prose-invert prose-p:my-2 prose-p:text-[15px] prose-p:leading-relaxed prose-li:my-0.5 prose-headings:mb-2 prose-headings:mt-3"

export const CHAT_COMPOSER_CLASS = "text-[15px] leading-relaxed"

export const CHAT_META_CLASS = "text-[11px] text-muted-foreground"

export const CHAT_WAITING_CLASS = "text-[15px] text-muted-foreground"
