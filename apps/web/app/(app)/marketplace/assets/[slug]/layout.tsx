import type { Metadata } from "next"
import { marketplaceAssetMetadata } from "@/lib/marketplace-metadata"

type LayoutProps = {
  children: React.ReactNode
  params: Promise<{ slug: string }>
}

export async function generateMetadata({ params }: Pick<LayoutProps, "params">): Promise<Metadata> {
  const { slug } = await params
  return marketplaceAssetMetadata(slug)
}

export default function MarketplaceAssetSlugLayout({ children }: LayoutProps) {
  return children
}
