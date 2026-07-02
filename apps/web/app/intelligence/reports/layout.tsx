import { Metadata } from "next"

export const metadata: Metadata = {
  title: "Intelligence Reports | Gravitre Operator",
  description: "View intelligence ROI and department scorecards.",
}

export default function ReportsLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
