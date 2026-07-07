export type UserAvatarSize = "xs" | "sm" | "md" | "lg" | "xl"

export const USER_AVATAR_SIZE_CLASSES: Record<UserAvatarSize, string> = {
  xs: "h-6 w-6 text-[10px]",
  sm: "h-8 w-8 text-xs",
  md: "h-9 w-9 text-xs",
  lg: "h-11 w-11 text-sm",
  xl: "h-12 w-12 text-base",
}

export function initialsFromDisplayName(name?: string | null, email?: string | null): string {
  const clean = (name || "").trim()
  if (clean) {
    const parts = clean.split(/\s+/).filter(Boolean)
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
    return `${parts[0][0] ?? ""}${parts[1][0] ?? ""}`.toUpperCase()
  }
  const local = (email || "").split("@")[0]?.trim()
  if (!local) return "U"
  return local.slice(0, 2).toUpperCase()
}

export function resolveAvatarUrl(
  ...candidates: Array<string | null | undefined>
): string | null {
  for (const candidate of candidates) {
    const value = (candidate || "").trim()
    if (value) return value
  }
  return null
}
