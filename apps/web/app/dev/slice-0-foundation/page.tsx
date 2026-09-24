import type { Metadata } from "next"
import { Slice0FoundationPreview } from "./_components/slice-0-foundation-preview"

export const metadata: Metadata = {
  title: "Slice 0 foundation (internal) · Gravitre",
  robots: { index: false, follow: false },
}

export default function Slice0FoundationPage() {
  return <Slice0FoundationPreview />
}
