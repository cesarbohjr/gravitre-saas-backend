import type { Metadata } from "next"

import { DeckStage } from "./deck-stage"

// Hidden, unlisted page — reachable only by direct link and excluded from the
// site nav and from search indexing.
export const metadata: Metadata = {
  title: "Seed Deck",
  description: "Gravitre — AI you can actually trust to act on your behalf. Seed round.",
  robots: { index: false, follow: false },
}

export default function DeckPage() {
  return <DeckStage />
}
