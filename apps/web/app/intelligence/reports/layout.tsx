import { Metadata } from "next"
import { SURFACE_COPY } from "@/lib/surface-copy"

export const metadata: Metadata = {
  title: `${SURFACE_COPY.pages.reports.title} | Gravitre Operator`,
  description: SURFACE_COPY.pages.reports.description,
}

export default function ReportsLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
