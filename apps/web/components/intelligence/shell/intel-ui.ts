/**
 * Class recipes shared by the Intelligence pages, taken from the Intelligence
 * designs: 18px panels, 14px stat cards, 13px pill filters and white outline
 * buttons. Keeping them here keeps the six pages identical.
 */
export const INTEL = {
  /** Large white panel (timeline, spend to value, matches, models map). */
  panel:
    "rounded-[18px] border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] p-5 sm:p-[22px]",
  panelTitle: "text-[18px] font-semibold leading-tight text-[color:var(--g-text-primary)]",
  panelLead: "text-sm text-[color:var(--g-text-secondary)]",
  /** Card heading inside a two-column row (By agent, All forecasts). */
  cardTitle: "text-[15px] font-semibold leading-tight text-[color:var(--g-text-primary)]",
  /** Small stat card. */
  stat: "flex flex-col gap-1.5 rounded-[14px] border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] px-[18px] py-4",
  statLabel: "text-[13px] text-[color:var(--g-text-secondary)]",
  statValue: "text-[28px] font-semibold leading-9 tracking-[-0.02em] tabular-nums text-[color:var(--g-text-primary)]",
  statHint: "text-xs text-[color:var(--g-text-secondary)]",
  /** Pill filter. Add `pillOn` when selected. */
  pill:
    "inline-flex items-center rounded-full border border-[color:var(--g-border-strong)] bg-[color:var(--g-surface-1)] px-3 py-[7px] text-[13px] text-[#33342f] transition-colors hover:border-[color:var(--g-text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:text-[color:var(--g-text-primary)]",
  pillOn:
    "border-[color:var(--g-text-primary)] bg-[color:var(--g-text-primary)] text-[color:var(--g-surface-1)] dark:text-[color:var(--g-surface-1)]",
  /** White outline button used in page headers (Refresh, Export). */
  outlineButton:
    "inline-flex items-center gap-1.5 rounded-[10px] border border-[color:var(--g-border-strong)] bg-[color:var(--g-surface-1)] px-3.5 py-2.5 text-[13px] text-[color:var(--g-text-primary)] transition-colors hover:bg-[color:var(--g-surface-2)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60",
  /** Dark primary header button (Add a memory, Connect a source, New model). */
  primaryButton:
    "inline-flex items-center gap-1.5 rounded-[10px] bg-[color:var(--g-text-primary)] px-3.5 py-2.5 text-[13px] font-medium text-[color:var(--g-surface-1)] transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60",
  /** Segmented period switch (7 / 30 / 90 days). */
  segment: "inline-flex rounded-[10px] bg-[color:var(--g-background-muted)] p-[3px]",
  segmentItem:
    "rounded-[8px] px-3 py-2 text-[13px] text-[color:var(--g-text-secondary)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
  segmentItemOn: "bg-[color:var(--g-surface-1)] font-medium text-[color:var(--g-text-primary)] shadow-[0_1px_2px_rgba(0,0,0,0.08)]",
  /** Mono section label ("WHY GRAVITRE THINKS SO"). */
  monoLabel: "font-mono text-[10.5px] uppercase tracking-[0.08em] text-[color:var(--g-text-secondary)]",
} as const
