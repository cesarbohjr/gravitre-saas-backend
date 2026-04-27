"use client"

import { motion } from "framer-motion"
import { Bot, Sparkles, Zap, Database, Workflow, BarChart3, User } from "lucide-react"
import { cn } from "@/lib/utils"
import { useUserProfile } from "@/lib/user-profile-context"

// Agent avatar configurations matching the actual agents in the platform
export const agentAvatars = {
  operator: {
    name: "AI Operator",
    icon: Sparkles,
    gradient: "from-blue-500 to-indigo-600",
    bgColor: "bg-blue-500/10",
    textColor: "text-blue-500",
  },
  marketing: {
    name: "Marketing Agent",
    icon: BarChart3,
    gradient: "from-purple-500 to-pink-600",
    bgColor: "bg-purple-500/10",
    textColor: "text-purple-500",
  },
  sales: {
    name: "Sales Agent",
    icon: Zap,
    gradient: "from-amber-500 to-orange-600",
    bgColor: "bg-amber-500/10",
    textColor: "text-amber-500",
  },
  data: {
    name: "Data Agent",
    icon: Database,
    gradient: "from-emerald-500 to-teal-600",
    bgColor: "bg-emerald-500/10",
    textColor: "text-emerald-500",
  },
  workflow: {
    name: "Workflow Agent",
    icon: Workflow,
    gradient: "from-cyan-500 to-blue-600",
    bgColor: "bg-cyan-500/10",
    textColor: "text-cyan-500",
  },
  default: {
    name: "Gravitre AI",
    icon: Bot,
    gradient: "from-zinc-600 to-zinc-800",
    bgColor: "bg-zinc-500/10",
    textColor: "text-zinc-500",
  },
}

export type AgentType = keyof typeof agentAvatars

interface AgentAvatarProps {
  agent?: AgentType
  size?: "xs" | "sm" | "md" | "lg"
  showPulse?: boolean
  className?: string
}

const sizeClasses = {
  xs: "h-6 w-6",
  sm: "h-8 w-8",
  md: "h-10 w-10",
  lg: "h-12 w-12",
}

const iconSizes = {
  xs: "h-3 w-3",
  sm: "h-4 w-4",
  md: "h-5 w-5",
  lg: "h-6 w-6",
}

export function AgentAvatar({ agent = "default", size = "md", showPulse = false, className }: AgentAvatarProps) {
  const config = agentAvatars[agent]
  const Icon = config.icon

  return (
    <div className={cn("relative", className)}>
      <div
        className={cn(
          "rounded-xl flex items-center justify-center bg-gradient-to-br",
          config.gradient,
          sizeClasses[size]
        )}
      >
        <Icon className={cn("text-white", iconSizes[size])} />
      </div>
      {showPulse && (
        <motion.div
          className={cn(
            "absolute inset-0 rounded-xl bg-gradient-to-br opacity-50",
            config.gradient
          )}
          animate={{ scale: [1, 1.2, 1], opacity: [0.5, 0, 0.5] }}
          transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
        />
      )}
    </div>
  )
}

interface UserAvatarProps {
  name?: string
  image?: string | null
  size?: "xs" | "sm" | "md" | "lg"
  className?: string
  useProfile?: boolean
}

export function UserAvatar({ name, image, size = "md", className, useProfile = true }: UserAvatarProps) {
  // Try to use the profile context for consistent user data
  let profileData: { avatarImage: string | null; initials: string; fullName: string } | null = null
  
  try {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    const { profile, getInitials, getFullName } = useUserProfile()
    profileData = {
      avatarImage: profile.avatarImage,
      initials: getInitials(),
      fullName: getFullName(),
    }
  } catch {
    // Context not available, use props
  }

  const displayName = name || profileData?.fullName || "User"
  const displayImage = image !== undefined ? image : profileData?.avatarImage
  const initials = profileData?.initials || displayName
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2)

  return (
    <div
      className={cn(
        "rounded-xl flex items-center justify-center overflow-hidden bg-gradient-to-br from-zinc-200 to-zinc-300 dark:from-zinc-700 dark:to-zinc-800",
        sizeClasses[size],
        className
      )}
    >
      {displayImage ? (
        <img src={displayImage} alt={displayName} className="h-full w-full object-cover" />
      ) : (
        <span className={cn("font-semibold text-zinc-600 dark:text-zinc-300", {
          "text-[10px]": size === "xs",
          "text-xs": size === "sm",
          "text-sm": size === "md",
          "text-base": size === "lg",
        })}>
          {initials || <User className={iconSizes[size]} />}
        </span>
      )}
    </div>
  )
}

interface ChatMessageAvatarProps {
  type: "user" | "agent"
  agent?: AgentType
  userName?: string
  userImage?: string | null
  size?: "xs" | "sm" | "md" | "lg"
  showPulse?: boolean
  className?: string
}

export function ChatMessageAvatar({
  type,
  agent = "operator",
  userName = "You",
  userImage,
  size = "md",
  showPulse = false,
  className,
}: ChatMessageAvatarProps) {
  if (type === "user") {
    return <UserAvatar name={userName} image={userImage} size={size} className={className} />
  }
  return <AgentAvatar agent={agent} size={size} showPulse={showPulse} className={className} />
}

// Sample chat message component showing user and agent avatars
interface ChatMessageProps {
  type: "user" | "agent"
  agent?: AgentType
  userName?: string
  userImage?: string | null
  content: string
  timestamp?: string
  isTyping?: boolean
}

export function ChatMessage({
  type,
  agent = "operator",
  userName = "You",
  userImage,
  content,
  timestamp,
  isTyping = false,
}: ChatMessageProps) {
  const isUser = type === "user"

  return (
    <div className={cn("flex gap-3", isUser ? "flex-row-reverse" : "flex-row")}>
      <ChatMessageAvatar
        type={type}
        agent={agent}
        userName={userName}
        userImage={userImage}
        size="sm"
        showPulse={isTyping}
      />
      <div
        className={cn(
          "flex flex-col max-w-[80%]",
          isUser ? "items-end" : "items-start"
        )}
      >
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-medium text-muted-foreground">
            {isUser ? userName : agentAvatars[agent].name}
          </span>
          {timestamp && (
            <span className="text-[10px] text-muted-foreground/60">{timestamp}</span>
          )}
        </div>
        <div
          className={cn(
            "rounded-2xl px-4 py-2.5 text-sm",
            isUser
              ? "bg-primary text-primary-foreground rounded-br-md"
              : "bg-secondary text-secondary-foreground rounded-bl-md"
          )}
        >
          {isTyping ? (
            <div className="flex items-center gap-1">
              <motion.div
                className="h-1.5 w-1.5 rounded-full bg-current"
                animate={{ opacity: [0.4, 1, 0.4] }}
                transition={{ duration: 1, repeat: Infinity, delay: 0 }}
              />
              <motion.div
                className="h-1.5 w-1.5 rounded-full bg-current"
                animate={{ opacity: [0.4, 1, 0.4] }}
                transition={{ duration: 1, repeat: Infinity, delay: 0.2 }}
              />
              <motion.div
                className="h-1.5 w-1.5 rounded-full bg-current"
                animate={{ opacity: [0.4, 1, 0.4] }}
                transition={{ duration: 1, repeat: Infinity, delay: 0.4 }}
              />
            </div>
          ) : (
            content
          )}
        </div>
      </div>
    </div>
  )
}

// Demo conversation component for marketing screenshots
export function DemoChatConversation() {
  const messages = [
    {
      type: "user" as const,
      content: "Why did the last customer sync fail?",
      timestamp: "2m ago",
    },
    {
      type: "agent" as const,
      agent: "operator" as AgentType,
      content: "I found the issue. The sync-customers-1234 workflow failed at step 3 due to a connection timeout after 30 seconds. This appears to be related to increased API latency during peak hours.",
      timestamp: "2m ago",
    },
    {
      type: "user" as const,
      content: "Can you fix it and retry?",
      timestamp: "1m ago",
    },
    {
      type: "agent" as const,
      agent: "operator" as AgentType,
      content: "Yes, I recommend increasing the timeout to 60 seconds and implementing retry logic. Would you like me to apply this fix and restart the sync?",
      timestamp: "Just now",
    },
  ]

  return (
    <div className="space-y-4 p-4">
      {messages.map((msg, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.15 }}
        >
          <ChatMessage
            type={msg.type}
            agent={msg.agent}
            userName="Sarah Chen"
            content={msg.content}
            timestamp={msg.timestamp}
          />
        </motion.div>
      ))}
    </div>
  )
}
