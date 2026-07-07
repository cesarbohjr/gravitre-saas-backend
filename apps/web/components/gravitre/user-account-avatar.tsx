"use client"

import { cn } from "@/lib/utils"
import {
  initialsFromDisplayName,
  resolveAvatarUrl,
  USER_AVATAR_SIZE_CLASSES,
  type UserAvatarSize,
} from "@/lib/user-avatar"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { useAccountProfile } from "@/hooks/use-account-profile"

type UserAccountAvatarProps = {
  name?: string | null
  email?: string | null
  avatarUrl?: string | null
  size?: UserAvatarSize
  className?: string
  fallbackClassName?: string
  /** When true, load the signed-in user's profile photo from /api/auth/me. */
  useCurrentUser?: boolean
}

export function UserAccountAvatar({
  name,
  email,
  avatarUrl,
  size = "md",
  className,
  fallbackClassName,
  useCurrentUser = false,
}: UserAccountAvatarProps) {
  const account = useAccountProfile()
  const resolvedName = useCurrentUser ? account.displayName : name
  const resolvedEmail = useCurrentUser ? account.email : email
  const resolvedAvatar = useCurrentUser
    ? account.avatarUrl
    : resolveAvatarUrl(avatarUrl)
  const initials = useCurrentUser
    ? account.initials
    : initialsFromDisplayName(resolvedName, resolvedEmail)

  return (
    <Avatar className={cn(USER_AVATAR_SIZE_CLASSES[size], className)}>
      {resolvedAvatar ? (
        <AvatarImage src={resolvedAvatar} alt={resolvedName || "User avatar"} />
      ) : null}
      <AvatarFallback
        className={cn(
          "bg-emerald-600 font-semibold text-white",
          fallbackClassName,
        )}
      >
        {initials}
      </AvatarFallback>
    </Avatar>
  )
}
