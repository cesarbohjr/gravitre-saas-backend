export function marketplaceSlugToTitle(slug: string): string {
  return slug
    .split("-")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ")
}

export function marketplaceAssetShareUrl(slug: string): string {
  const appUrl = (process.env.NEXT_PUBLIC_APP_URL || "https://gravitre.app").replace(/\/+$/, "")
  return `${appUrl}/marketplace/assets/${encodeURIComponent(slug)}`
}

export function marketplaceAssetMetadata(slug: string) {
  const title = marketplaceSlugToTitle(slug)
  const pageTitle = `${title} · Gravitre Marketplace`
  const description = `Install ${title} from the Gravitre unified marketplace — agents, workflows, and knowledge packs with guided connector setup.`
  const url = marketplaceAssetShareUrl(slug)

  return {
    title: pageTitle,
    description,
    openGraph: {
      title,
      description,
      url,
      siteName: "Gravitre",
      type: "website" as const,
    },
    twitter: {
      card: "summary_large_image" as const,
      title,
      description,
    },
  }
}
