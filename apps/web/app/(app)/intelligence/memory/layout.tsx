import { Metadata } from "next"
import { SURFACE_COPY } from "@/lib/surface-copy"

export const metadata: Metadata = {
  title: `${SURFACE_COPY.pages.memory.title} | Gravitre Operator`,
  description: SURFACE_COPY.pages.memory.description,
}

export default function MemoryLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
