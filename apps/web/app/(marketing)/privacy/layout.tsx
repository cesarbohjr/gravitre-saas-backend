import { marketingMetadata } from "@/lib/seo"

export const metadata = marketingMetadata({
  title: "Gravitre Privacy Policy and Data Handling",
  canonical: "/privacy",
  description: "Read how Gravitre collects, uses, and protects account information, usage data, and information accessed through connected services.",
})

export default function PrivacyLayout({ children }: { children: React.ReactNode }) {
  return children
}
