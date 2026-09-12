/** Shared typography tokens for every in-product chat surface.
 *  P9 — Nodus×Gravitre mineral shell: brand-green user, surface assistant bubbles.
 */

export const CHAT_ROLE_LABEL_CLASS =
  "mb-1 px-0.5 text-[9px] font-medium uppercase tracking-[0.08em] text-[color:var(--chat-surface-muted,var(--g-text-muted))]"

/** 14px on small screens, 15px from `sm` up: the comfortable reading size the
 *  assistant renderer also targets, so user and assistant turns match.
 *
 *  Padding lives in the per-role classes below, not here, because only the user
 *  turn is a bubble. Keeping `px-3 py-2` here would fight the assistant's
 *  padding-free surface, and two competing Tailwind padding utilities resolve by
 *  CSS source order rather than the order they appear in the class string. */
export const CHAT_BUBBLE_BASE_CLASS =
  "max-w-full rounded-[var(--np-radius-md)] text-[14px] leading-relaxed sm:text-[15px]"

/** User turns — brand green (not marketing blue / ChatGPT purple). */
export const CHAT_USER_BUBBLE_CLASS =
  "bg-[color:var(--g-brand)] px-3 py-2 text-white shadow-[var(--np-shadow)]"

/**
 * Assistant turns — no card.
 *
 * This previously carried `border border-divide`, a `--g-surface-1` fill and a
 * shadow, which boxed every reply in its own panel; a thread then read as a
 * stack of dashboard widgets rather than a conversation, and the border competed
 * with the real structure inside the answer (headings, lists, tables, code).
 * The user turn keeps its green bubble, so authorship is still unambiguous —
 * this is the ChatGPT / Claude / Cursor arrangement the design target names.
 */
export const CHAT_ASSISTANT_BUBBLE_CLASS = "text-[color:var(--g-text-primary)]"

export const CHAT_BODY_TEXT_CLASS = "text-[14px] leading-relaxed"

/**
 * Wrapper for assistant Markdown. Element-level typography lives in
 * `AssistantMarkdown`'s component map, not here.
 *
 * This previously read `prose prose-sm max-w-none dark:prose-invert prose-p:my-2
 * ...`, which looked like a styling contract but produced nothing: the
 * `@tailwindcss/typography` plugin those classes come from was never installed,
 * and `.prose` appears zero times in the shipped production CSS. Assistant
 * Markdown was therefore rendered with Tailwind Preflight's resets and nothing
 * else — no list markers, no heading sizes, no block spacing.
 *
 * `max-w-[68ch]` is the reading measure: comfortable line length without going
 * edge-to-edge in a wide window. It is a max, so narrow surfaces (float window,
 * mobile sheet) are unaffected.
 */
export const CHAT_PROSE_CLASS = "max-w-[68ch]"

export const CHAT_COMPOSER_CLASS = "text-[14px] leading-relaxed"

export const CHAT_META_CLASS = "text-[11px] text-muted-foreground"

export const CHAT_WAITING_CLASS = "text-[14px] text-muted-foreground"

/** Quiet hover/focus action rail under message panels. */
export const CHAT_ACTION_RAIL_CLASS =
  "mt-1 flex items-center gap-0.5 opacity-100 transition-opacity sm:opacity-0 sm:group-hover/msg:opacity-100 sm:group-focus-within/msg:opacity-100"
