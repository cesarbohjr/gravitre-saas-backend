import type { Metadata } from "next"

/** Metadata for authenticated app routes — always noindex. */
export function authenticatedMetadata(
  title: string,
  description: string,
  options?: { canonical?: string },
): Metadata {
  return {
    title,
    description,
    robots: { index: false, follow: false },
    ...(options?.canonical
      ? { alternates: { canonical: options.canonical } }
      : {}),
  }
}

/** Metadata for public marketing pages with OG defaults. */
export function marketingPageMetadata(
  title: string,
  description: string,
  path: string,
): Metadata {
  return {
    title,
    description,
    alternates: { canonical: path },
    openGraph: {
      title,
      description,
      url: path,
      type: "website",
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
    },
  }
}
