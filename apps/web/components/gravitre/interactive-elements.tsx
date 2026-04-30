"use client"

// Interactive UI Elements with Premium Animations
// Based on Gravitre UI Interaction Upgrade Guidelines

import * as React from "react"
import { motion, AnimatePresence, type Variants } from "framer-motion"
import { cn } from "@/lib/utils"
import { 
  timing, 
  easing, 
  buttonVariants, 
  primaryButtonVariants,
  thinkingDotVariants,
  shimmerVariants,
  progressiveRevealVariants,
  listItemVariants,
  interactiveCardVariants,
  springTransition
} from "@/lib/animations"
import { Loader2, Check, AlertCircle, Sparkles } from "lucide-react"

// ============================================
// THINKING INDICATOR
// ============================================
interface ThinkingIndicatorProps {
  text?: string
  className?: string
}

export function ThinkingIndicator({ text = "Thinking", className }: ThinkingIndicatorProps) {
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div className="flex gap-1">
        {[0, 1, 2].map((i) => (
          <motion.div
            key={i}
            className="h-1.5 w-1.5 rounded-full bg-emerald-500"
            animate={{ y: [0, -4, 0] }}
            transition={{ 
              duration: 0.6, 
              repeat: Infinity, 
              delay: i * 0.15,
              ease: "easeInOut"
            }}
          />
        ))}
      </div>
      <span className="text-xs text-muted-foreground">{text}...</span>
    </div>
  )
}

// ============================================
// PROGRESSIVE THINKING STEPS
// ============================================
interface ThinkingStep {
  id: string
  text: string
  status: "pending" | "active" | "completed"
}

interface ThinkingStepsProps {
  steps: ThinkingStep[]
  className?: string
}

export function ThinkingSteps({ steps, className }: ThinkingStepsProps) {
  return (
    <div className={cn("space-y-2", className)}>
      <AnimatePresence mode="popLayout">
        {steps.map((step, index) => (
          <motion.div
            key={step.id}
            initial={{ opacity: 0, y: 10, height: 0 }}
            animate={{ 
              opacity: 1, 
              y: 0, 
              height: "auto",
              transition: { 
                delay: index * 0.15,
                duration: timing.ui,
                ease: easing.smooth as number[]
              }
            }}
            exit={{ opacity: 0, y: -10, height: 0 }}
            className="flex items-center gap-3"
          >
            <div className={cn(
              "h-5 w-5 rounded-full flex items-center justify-center transition-colors",
              step.status === "completed" && "bg-emerald-500",
              step.status === "active" && "bg-blue-500",
              step.status === "pending" && "bg-secondary"
            )}>
              {step.status === "completed" && (
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ type: "spring", stiffness: 400, damping: 15 }}
                >
                  <Check className="h-3 w-3 text-white" />
                </motion.div>
              )}
              {step.status === "active" && (
                <motion.div
                  animate={{ scale: [1, 1.2, 1] }}
                  transition={{ duration: 1, repeat: Infinity }}
                >
                  <Sparkles className="h-3 w-3 text-white" />
                </motion.div>
              )}
            </div>
            <span className={cn(
              "text-sm transition-colors",
              step.status === "completed" && "text-muted-foreground",
              step.status === "active" && "text-foreground font-medium",
              step.status === "pending" && "text-muted-foreground/50"
            )}>
              {step.text}
            </span>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}

// ============================================
// SKELETON SHIMMER
// ============================================
interface SkeletonProps {
  className?: string
  variant?: "text" | "circular" | "rectangular"
  width?: string | number
  height?: string | number
}

export function Skeleton({ className, variant = "rectangular", width, height }: SkeletonProps) {
  return (
    <div
      className={cn(
        "relative overflow-hidden bg-secondary/50",
        variant === "circular" && "rounded-full",
        variant === "text" && "rounded h-4",
        variant === "rectangular" && "rounded-lg",
        className
      )}
      style={{ width, height }}
    >
      <motion.div
        className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent"
        animate={{ x: ["-100%", "100%"] }}
        transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
      />
    </div>
  )
}

// ============================================
// INTERACTIVE BUTTON (with press feedback)
// ============================================
interface InteractiveButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "primary" | "ghost"
  isLoading?: boolean
  loadingText?: string
  successText?: string
  showSuccess?: boolean
  children: React.ReactNode
}

export const InteractiveButton = React.forwardRef<HTMLButtonElement, InteractiveButtonProps>(
  ({ className, variant = "default", isLoading, loadingText, successText, showSuccess, children, disabled, ...props }, ref) => {
    return (
      <motion.button
        ref={ref}
        whileHover={{ scale: disabled || isLoading ? 1 : 1.02 }}
        whileTap={{ scale: disabled || isLoading ? 1 : 0.97 }}
        transition={{ duration: timing.micro }}
        className={cn(
          "relative inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
          variant === "default" && "bg-secondary text-secondary-foreground hover:bg-secondary/80",
          variant === "primary" && "bg-emerald-600 text-white hover:bg-emerald-700 shadow-lg shadow-emerald-500/20",
          variant === "ghost" && "hover:bg-secondary/50",
          (disabled || isLoading) && "opacity-50 cursor-not-allowed",
          className
        )}
        disabled={disabled || isLoading}
        {...props}
      >
        <AnimatePresence mode="wait">
          {isLoading ? (
            <motion.span
              key="loading"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex items-center gap-2"
            >
              <Loader2 className="h-4 w-4 animate-spin" />
              {loadingText || "Loading..."}
            </motion.span>
          ) : showSuccess ? (
            <motion.span
              key="success"
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0 }}
              className="flex items-center gap-2 text-emerald-500"
            >
              <Check className="h-4 w-4" />
              {successText || "Done!"}
            </motion.span>
          ) : (
            <motion.span
              key="default"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              {children}
            </motion.span>
          )}
        </AnimatePresence>
      </motion.button>
    )
  }
)
InteractiveButton.displayName = "InteractiveButton"

// ============================================
// INTERACTIVE CARD
// ============================================
interface InteractiveCardProps {
  children: React.ReactNode
  className?: string
  onClick?: () => void
  isSelected?: boolean
  disabled?: boolean
}

export function InteractiveCard({ children, className, onClick, isSelected, disabled }: InteractiveCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={!disabled ? { y: -4, transition: { duration: timing.micro } } : undefined}
      whileTap={!disabled ? { scale: 0.98 } : undefined}
      onClick={disabled ? undefined : onClick}
      className={cn(
        "relative rounded-xl border bg-card p-4 transition-all duration-150",
        onClick && !disabled && "cursor-pointer",
        isSelected 
          ? "border-emerald-500/50 ring-2 ring-emerald-500/20 shadow-lg shadow-emerald-500/10" 
          : "border-border hover:border-muted-foreground/30 hover:shadow-lg hover:shadow-black/5",
        disabled && "opacity-50 cursor-not-allowed",
        className
      )}
    >
      {children}
    </motion.div>
  )
}

// ============================================
// ANIMATED LIST
// ============================================
interface AnimatedListProps {
  children: React.ReactNode
  className?: string
  staggerDelay?: number
}

export function AnimatedList({ children, className, staggerDelay = 0.05 }: AnimatedListProps) {
  return (
    <motion.div
      initial="initial"
      animate="animate"
      exit="exit"
      className={className}
    >
      {React.Children.map(children, (child, index) => (
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ 
            opacity: 1, 
            x: 0,
            transition: {
              delay: index * staggerDelay,
              duration: timing.ui,
              ease: easing.smooth as number[]
            }
          }}
          exit={{ opacity: 0, x: 20 }}
        >
          {child}
        </motion.div>
      ))}
    </motion.div>
  )
}

// ============================================
// STATUS BEACON (Live indicator)
// ============================================
interface StatusBeaconProps {
  status: "active" | "processing" | "idle" | "error" | "success"
  size?: "sm" | "md" | "lg"
  pulse?: boolean
  className?: string
}

export function StatusBeacon({ status, size = "md", pulse = true, className }: StatusBeaconProps) {
  const sizeClasses = {
    sm: "h-2 w-2",
    md: "h-2.5 w-2.5",
    lg: "h-3 w-3"
  }

  const colorClasses = {
    active: "bg-emerald-500",
    processing: "bg-blue-500",
    idle: "bg-zinc-400",
    error: "bg-red-500",
    success: "bg-emerald-500"
  }

  return (
    <span className={cn("relative inline-flex", className)}>
      <span className={cn(
        "rounded-full",
        sizeClasses[size],
        colorClasses[status]
      )} />
      {pulse && (status === "active" || status === "processing") && (
        <motion.span
          className={cn(
            "absolute inset-0 rounded-full",
            colorClasses[status]
          )}
          animate={{ scale: [1, 1.5, 1], opacity: [0.8, 0, 0.8] }}
          transition={{ duration: 1.5, repeat: Infinity, ease: "easeOut" }}
        />
      )}
    </span>
  )
}

// ============================================
// PROGRESS RING
// ============================================
interface ProgressRingProps {
  progress: number // 0-100
  size?: number
  strokeWidth?: number
  className?: string
  color?: string
}

export function ProgressRing({ 
  progress, 
  size = 40, 
  strokeWidth = 3, 
  className,
  color = "stroke-emerald-500"
}: ProgressRingProps) {
  const radius = (size - strokeWidth) / 2
  const circumference = radius * 2 * Math.PI
  const offset = circumference - (progress / 100) * circumference

  return (
    <svg width={size} height={size} className={cn("-rotate-90", className)}>
      {/* Background circle */}
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        strokeWidth={strokeWidth}
        className="stroke-secondary fill-none"
      />
      {/* Progress circle */}
      <motion.circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        strokeWidth={strokeWidth}
        className={cn("fill-none", color)}
        strokeLinecap="round"
        initial={{ strokeDasharray: circumference, strokeDashoffset: circumference }}
        animate={{ strokeDashoffset: offset }}
        transition={{ duration: timing.major, ease: easing.smooth as number[] }}
      />
    </svg>
  )
}

// ============================================
// FADE IN WRAPPER
// ============================================
interface FadeInProps {
  children: React.ReactNode
  delay?: number
  className?: string
  direction?: "up" | "down" | "left" | "right" | "none"
}

export function FadeIn({ children, delay = 0, className, direction = "up" }: FadeInProps) {
  const directionVariants = {
    up: { y: 20 },
    down: { y: -20 },
    left: { x: 20 },
    right: { x: -20 },
    none: {}
  }

  return (
    <motion.div
      initial={{ opacity: 0, ...directionVariants[direction] }}
      animate={{ 
        opacity: 1, 
        y: 0, 
        x: 0,
        transition: {
          delay,
          duration: timing.ui,
          ease: easing.smooth as number[]
        }
      }}
      className={className}
    >
      {children}
    </motion.div>
  )
}

// ============================================
// HOVER REVEAL
// ============================================
interface HoverRevealProps {
  children: React.ReactNode
  revealContent: React.ReactNode
  className?: string
}

export function HoverReveal({ children, revealContent, className }: HoverRevealProps) {
  const [isHovered, setIsHovered] = React.useState(false)

  return (
    <div
      className={cn("relative", className)}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {children}
      <AnimatePresence>
        {isHovered && (
          <motion.div
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 5 }}
            transition={{ duration: timing.micro }}
            className="absolute inset-0"
          >
            {revealContent}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ============================================
// TOAST / NOTIFICATION ANIMATION
// ============================================
interface AnimatedToastProps {
  children: React.ReactNode
  variant?: "default" | "success" | "error" | "warning"
  className?: string
}

export function AnimatedToast({ children, variant = "default", className }: AnimatedToastProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 50, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 20, scale: 0.95 }}
      transition={springTransition}
      className={cn(
        "rounded-lg border px-4 py-3 shadow-lg backdrop-blur-sm",
        variant === "default" && "bg-card border-border",
        variant === "success" && "bg-emerald-500/10 border-emerald-500/30 text-emerald-400",
        variant === "error" && "bg-red-500/10 border-red-500/30 text-red-400",
        variant === "warning" && "bg-amber-500/10 border-amber-500/30 text-amber-400",
        className
      )}
    >
      {children}
    </motion.div>
  )
}

// ============================================
// EMPTY STATE WITH ANIMATION
// ============================================
interface AnimatedEmptyStateProps {
  icon?: React.ReactNode
  title: string
  description?: string
  action?: React.ReactNode
  className?: string
}

export function AnimatedEmptyState({ icon, title, description, action, className }: AnimatedEmptyStateProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: timing.ui, ease: easing.smooth as number[] }}
      className={cn("flex flex-col items-center justify-center py-12 text-center", className)}
    >
      {icon && (
        <motion.div
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ delay: 0.1, type: "spring", stiffness: 300, damping: 20 }}
          className="mb-4 h-16 w-16 rounded-full bg-secondary/50 flex items-center justify-center text-muted-foreground"
        >
          {icon}
        </motion.div>
      )}
      <motion.h3
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.2 }}
        className="text-lg font-medium text-foreground mb-1"
      >
        {title}
      </motion.h3>
      {description && (
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
          className="text-sm text-muted-foreground max-w-sm"
        >
          {description}
        </motion.p>
      )}
      {action && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="mt-4"
        >
          {action}
        </motion.div>
      )}
    </motion.div>
  )
}
