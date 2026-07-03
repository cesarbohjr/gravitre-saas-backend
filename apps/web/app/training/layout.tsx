import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Agent Training | Gravitre",
  "Train and fine-tune agent behavior.",
  { canonical: "/training" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
