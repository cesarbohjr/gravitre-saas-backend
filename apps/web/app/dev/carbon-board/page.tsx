import type { Metadata } from "next"
import { CarbonBoard } from "./_components/carbon-board"

export const metadata: Metadata = {
  title: "Carbon design board (internal) · Gravitre",
  robots: { index: false, follow: false },
}

export default function CarbonBoardPage() {
  return <CarbonBoard />
}
