import { marketingMetadata } from "@/lib/seo"

export const metadata = marketingMetadata({
  title: "Security",
  description:
    "How Gravitre protects your data: encryption, access controls, audit logging, and human approval on writes — for one shared AI brain across your business.",
  ogDescription: "Encryption, access controls, audit logging, and approval gates on writes.",
})

export default function SecurityLayout({ children }: { children: React.ReactNode }) {
  return children
}
