export function getAuthRedirectUrl(path: string = "/operator"): string | undefined {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`
  const configuredBase = (process.env.NEXT_PUBLIC_APP_URL || "").trim()

  if (configuredBase) {
    return `${configuredBase.replace(/\/+$/, "")}${normalizedPath}`
  }

  if (typeof window !== "undefined") {
    return `${window.location.origin}${normalizedPath}`
  }

  return undefined
}
