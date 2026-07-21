/** Shared typography tokens for every in-product chat surface.
 *  Direction A — Operator Console: transcript panels, not consumer bubbles.
 */

export const CHAT_ROLE_LABEL_CLASS =
  "mb-1 px-0.5 text-[10px] font-medium uppercase tracking-[0.08em] text-muted-foreground"

export const CHAT_BUBBLE_BASE_CLASS =
  "w-full rounded-lg px-3.5 py-3 text-[14px] leading-relaxed"

export const CHAT_USER_BUBBLE_CLASS =
  "rounded-br-sm border border-emerald-700/25 bg-emerald-700/[0.12] text-foreground dark:border-emerald-400/20 dark:bg-emerald-500/[0.12]"

export const CHAT_ASSISTANT_BUBBLE_CLASS =
  "rounded-bl-sm border border-border/70 bg-card/90 text-foreground shadow-none backdrop-blur-[2px]"

export const CHAT_BODY_TEXT_CLASS = "text-[14px] leading-relaxed"

export const CHAT_PROSE_CLASS =
  "prose prose-sm max-w-none dark:prose-invert prose-p:my-2 prose-p:text-[14px] prose-p:leading-relaxed prose-li:my-0.5 prose-headings:mb-2 prose-headings:mt-3"

export const CHAT_COMPOSER_CLASS = "text-[14px] leading-relaxed"

export const CHAT_META_CLASS = "text-[11px] text-muted-foreground"

export const CHAT_WAITING_CLASS = "text-[14px] text-muted-foreground"

/** Quiet hover/focus action rail under message panels. */
export const CHAT_ACTION_RAIL_CLASS =
  "mt-1 flex items-center gap-0.5 opacity-100 transition-opacity sm:opacity-0 sm:group-hover/msg:opacity-100 sm:group-focus-within/msg:opacity-100"
