// Presentation animation layer for the Gravitre Seed Deck.
// Ambient keyframes (gv-*) are referenced inline by the slide markup, so they
// must be globally defined. Entrance rules are keyed to the active slide's
// `data-deck-active` attribute and replay on every navigation because the slide
// frame is remounted (keyed) on index change.
export const DECK_CSS = `
@keyframes gv-pulse { 0%,100% { opacity: .45; scale: 1; } 50% { opacity: .8; scale: 1.06; } }
@keyframes gv-wave { 0%,100% { scale: 1 .35; } 50% { scale: 1 1; } }
@keyframes gv-orbit { from { rotate: 0deg; } to { rotate: 360deg; } }
@keyframes gv-rise { from { opacity: 0; translate: 0 26px; } to { opacity: 1; translate: 0 0; } }
@keyframes gv-slide-in { from { opacity: 0; translate: -22px 0; } to { opacity: 1; translate: 0 0; } }
@keyframes gv-grow { from { scale: 0 1; } to { scale: 1 1; } }
@keyframes gv-pop { from { opacity: 0; scale: .9; } to { opacity: 1; scale: 1; } }

/* Whole-slide entrance for the frame, direction-aware via --deck-dir */
@keyframes deck-frame-in {
  from { opacity: 0; transform: translateX(calc(var(--deck-dir, 1) * 46px)) scale(.986); }
  to   { opacity: 1; transform: translateX(0) scale(1); }
}
.deck-frame { animation: deck-frame-in .5s cubic-bezier(.22,.68,.28,1) both; }
/* The slide sections size their children with absolute positioning, so the
   section itself must be forced to fill the 1920x1080 frame. */
.deck-frame > section { display: block; width: 100%; height: 100%; }

/* Staged entrance, keyed to the stage's active slide */
section[data-deck-active] > div > div { animation: gv-rise .62s cubic-bezier(.22,.68,.28,1) both; }
section[data-deck-active] > div > div:nth-child(1) { animation-delay: .06s; }
section[data-deck-active] > div > div:nth-child(2) { animation-delay: .11s; }
section[data-deck-active] > div > div:nth-child(3) { animation-delay: .16s; }
section[data-deck-active] > div > div:nth-child(4) { animation-delay: .22s; }
section[data-deck-active] > div > div:nth-child(5) { animation-delay: .28s; }
section[data-deck-active] > div > div:nth-child(6) { animation-delay: .34s; }
section[data-deck-active] > div > div:nth-child(n+7) { animation-delay: .40s; }

/* Chrome: hairline rules wipe in from the left rather than rising */
section[data-deck-active] > div > div[style*="height:1px"],
section[data-deck-active] > div > div[style*="height:3px"],
section[data-deck-active] > div > div[style*="height:4px"] {
  animation: gv-grow .7s cubic-bezier(.22,.68,.28,1) both;
  transform-origin: left center;
}

/* Ambient glows fade in, then resume their idle pulse */
section[data-deck-active] > div > div[style*="border-radius:50%"][style*="blur"] {
  animation: gv-pop .9s ease both, gv-pulse 7s ease-in-out .9s infinite;
}

/* Cards, stat rows and diagram nodes stagger within their container */
section[data-deck-active] > div > div > div > div { animation: gv-rise .55s cubic-bezier(.22,.68,.28,1) both; animation-delay: .30s; }
section[data-deck-active] > div > div > div > div:nth-child(2) { animation-delay: .38s; }
section[data-deck-active] > div > div > div > div:nth-child(3) { animation-delay: .46s; }
section[data-deck-active] > div > div > div > div:nth-child(4) { animation-delay: .54s; }
section[data-deck-active] > div > div > div > div:nth-child(n+5) { animation-delay: .62s; }

/* Eyebrow marker slides in from the edge */
section[data-deck-active] > div > div[style*="top:76px"] { animation: gv-slide-in .6s cubic-bezier(.22,.68,.28,1) both; }

/* Market bars wipe to their measured width */
section[data-screen-label^="12"][data-deck-active] div[style*="height:74px"] {
  animation: gv-grow .85s cubic-bezier(.22,.68,.28,1) .45s both;
  transform-origin: left center;
}

/* Pricing table rows cascade */
section[data-screen-label^="13"][data-deck-active] tr { animation: gv-rise .5s ease both; }
section[data-screen-label^="13"][data-deck-active] tr:nth-child(1) { animation-delay: .28s; }
section[data-screen-label^="13"][data-deck-active] tr:nth-child(2) { animation-delay: .35s; }
section[data-screen-label^="13"][data-deck-active] tr:nth-child(3) { animation-delay: .42s; }
section[data-screen-label^="13"][data-deck-active] tr:nth-child(4) { animation-delay: .49s; }
section[data-screen-label^="13"][data-deck-active] tr:nth-child(5) { animation-delay: .56s; }
section[data-screen-label^="13"][data-deck-active] tr:nth-child(6) { animation-delay: .63s; }
section[data-screen-label^="13"][data-deck-active] tr:nth-child(7) { animation-delay: .70s; }
section[data-screen-label^="13"][data-deck-active] tr:nth-child(8) { animation-delay: .77s; }

/* Product screenshots settle with a soft lift */
section[data-deck-active] img { animation: gv-pop .7s cubic-bezier(.22,.68,.28,1) .30s both; }

@media (prefers-reduced-motion: reduce) {
  .deck-frame,
  section[data-deck-active] *,
  section[data-deck-active] *::before,
  section[data-deck-active] *::after {
    animation-duration: .01ms !important;
    animation-iteration-count: 1 !important;
    animation-delay: 0s !important;
  }
}
`
