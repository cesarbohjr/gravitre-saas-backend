/** Shared typography tokens for every in-product chat surface.
 *  Handoff 5a/5b — warm stone canvas, compact rounded bubbles, brand green send.
 */

export const CHAT_ROLE_LABEL_CLASS =
  "mb-1 px-0.5 text-[9px] font-medium uppercase tracking-[0.08em] text-[color:var(--chat-surface-muted,#a19a91)]"

export const CHAT_BUBBLE_BASE_CLASS =
  "max-w-full rounded-[10px] px-3 py-2 text-[13px] leading-relaxed sm:text-[14px]"

// Handoff user bubble — solid #16a374.
export const CHAT_USER_BUBBLE_CLASS =
  "bg-[#16a374] text-white shadow-[0_1px_2px_rgba(0,0,0,0.04)]"

// Handoff assistant bubble — white / dark card over patterned canvas.
export const CHAT_ASSISTANT_BUBBLE_CLASS =
  "border border-[#ececea] bg-white text-[#1c1917] shadow-[0_1px_2px_rgba(0,0,0,0.04)] dark:border-[#3a3a3a] dark:bg-[#292929] dark:text-[#e9e9e6]"

export const CHAT_BODY_TEXT_CLASS = "text-[14px] leading-relaxed"

export const CHAT_PROSE_CLASS =
  "prose prose-sm max-w-none dark:prose-invert prose-p:my-2 prose-p:text-[14px] prose-p:leading-relaxed prose-li:my-0.5 prose-headings:mb-2 prose-headings:mt-3"

export const CHAT_COMPOSER_CLASS = "text-[14px] leading-relaxed"

export const CHAT_META_CLASS = "text-[11px] text-muted-foreground"

export const CHAT_WAITING_CLASS = "text-[14px] text-muted-foreground"

/** Quiet hover/focus action rail under message panels. */
export const CHAT_ACTION_RAIL_CLASS =
  "mt-1 flex items-center gap-0.5 opacity-100 transition-opacity sm:opacity-0 sm:group-hover/msg:opacity-100 sm:group-focus-within/msg:opacity-100"
