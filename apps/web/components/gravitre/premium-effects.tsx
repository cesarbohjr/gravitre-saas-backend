"use client"

import { useEffect, useRef, useState, useMemo } from "react"
import { motion, useMotionValue, useSpring, useTransform, AnimatePresence } from "framer-motion"
import { cn } from "@/lib/utils"

// ============================================================================
// PARTICLE FIELD - Ambient floating particles that respond to cursor
// ============================================================================

interface Particle {
  id: number
  x: number
  y: number
  size: number
  opacity: number
  speedX: number
  speedY: number
  hue: number
}

export function ParticleField({
  count = 50,
  color = "emerald",
  interactive = true,
  className,
}: {
  count?: number
  color?: "emerald" | "violet" | "blue" | "amber" | "cyan"
  interactive?: boolean
  className?: string
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [particles, setParticles] = useState<Particle[]>([])
  const mouseX = useMotionValue(0)
  const mouseY = useMotionValue(0)
  const smoothX = useSpring(mouseX, { stiffness: 50, damping: 20 })
  const smoothY = useSpring(mouseY, { stiffness: 50, damping: 20 })

  const colorMap = {
    emerald: { h: 160, s: 84, l: 39 },
    violet: { h: 270, s: 76, l: 60 },
    blue: { h: 217, s: 91, l: 60 },
    amber: { h: 38, s: 92, l: 50 },
    cyan: { h: 186, s: 94, l: 50 },
  }

  useEffect(() => {
    const newParticles: Particle[] = Array.from({ length: count }, (_, i) => ({
      id: i,
      x: Math.random() * 100,
      y: Math.random() * 100,
      size: Math.random() * 3 + 1,
      opacity: Math.random() * 0.5 + 0.2,
      speedX: (Math.random() - 0.5) * 0.02,
      speedY: (Math.random() - 0.5) * 0.02,
      hue: colorMap[color].h + (Math.random() - 0.5) * 20,
    }))
    setParticles(newParticles)
  }, [count, color])

  useEffect(() => {
    if (!interactive) return
    
    const handleMouseMove = (e: MouseEvent) => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect()
        mouseX.set((e.clientX - rect.left) / rect.width * 100)
        mouseY.set((e.clientY - rect.top) / rect.height * 100)
      }
    }

    window.addEventListener("mousemove", handleMouseMove)
    return () => window.removeEventListener("mousemove", handleMouseMove)
  }, [interactive, mouseX, mouseY])

  return (
    <div ref={containerRef} className={cn("absolute inset-0 overflow-hidden pointer-events-none", className)}>
      {particles.map((particle) => (
        <motion.div
          key={particle.id}
          className="absolute rounded-full"
          style={{
            left: `${particle.x}%`,
            top: `${particle.y}%`,
            width: particle.size,
            height: particle.size,
            backgroundColor: `hsla(${particle.hue}, ${colorMap[color].s}%, ${colorMap[color].l}%, ${particle.opacity})`,
            boxShadow: `0 0 ${particle.size * 2}px hsla(${particle.hue}, ${colorMap[color].s}%, ${colorMap[color].l}%, ${particle.opacity * 0.5})`,
          }}
          animate={{
            x: [0, Math.random() * 20 - 10, 0],
            y: [0, Math.random() * 20 - 10, 0],
            scale: [1, 1.2, 1],
          }}
          transition={{
            duration: 5 + Math.random() * 5,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        />
      ))}
    </div>
  )
}

// ============================================================================
// PULSE RING - Expanding rings that indicate activity
// ============================================================================

export function PulseRing({
  size = 100,
  color = "emerald",
  delay = 0,
  className,
}: {
  size?: number
  color?: "emerald" | "violet" | "blue" | "amber"
  delay?: number
  className?: string
}) {
  const colorClasses = {
    emerald: "border-emerald-500/50",
    violet: "border-violet-500/50",
    blue: "border-blue-500/50",
    amber: "border-amber-500/50",
  }

  return (
    <div className={cn("absolute", className)}>
      {[0, 1, 2].map((i) => (
        <motion.div
          key={i}
          className={cn("absolute rounded-full border-2", colorClasses[color])}
          style={{
            width: size,
            height: size,
            left: -size / 2,
            top: -size / 2,
          }}
          initial={{ scale: 0.5, opacity: 0.8 }}
          animate={{ scale: 2, opacity: 0 }}
          transition={{
            duration: 3,
            repeat: Infinity,
            delay: delay + i * 1,
            ease: "easeOut",
          }}
        />
      ))}
    </div>
  )
}

// ============================================================================
// GLOW ORB - Premium floating orb with depth
// ============================================================================

export function GlowOrb({
  size = 200,
  color = "emerald",
  intensity = 1,
  animate = true,
  className,
}: {
  size?: number
  color?: "emerald" | "violet" | "blue" | "amber" | "mixed"
  intensity?: number
  animate?: boolean
  className?: string
}) {
  const gradients = {
    emerald: "from-emerald-400 via-emerald-500 to-teal-600",
    violet: "from-violet-400 via-purple-500 to-indigo-600",
    blue: "from-blue-400 via-blue-500 to-cyan-600",
    amber: "from-amber-400 via-orange-500 to-red-500",
    mixed: "from-emerald-400 via-violet-500 to-blue-600",
  }

  return (
    <motion.div
      className={cn("absolute rounded-full pointer-events-none", className)}
      style={{
        width: size,
        height: size,
        filter: `blur(${size * 0.4}px)`,
        opacity: 0.3 * intensity,
      }}
      animate={animate ? {
        scale: [1, 1.1, 1],
        rotate: [0, 180, 360],
      } : undefined}
      transition={{
        duration: 20,
        repeat: Infinity,
        ease: "linear",
      }}
    >
      <div className={cn("w-full h-full rounded-full bg-gradient-to-br", gradients[color])} />
    </motion.div>
  )
}

// ============================================================================
// NEURAL NETWORK - Animated connecting lines
// ============================================================================

interface Node {
  id: number
  x: number
  y: number
  connections: number[]
}

export function NeuralNetwork({
  nodeCount = 15,
  color = "emerald",
  className,
}: {
  nodeCount?: number
  color?: "emerald" | "violet" | "blue"
  className?: string
}) {
  const nodes = useMemo<Node[]>(() => {
    const generated: Node[] = Array.from({ length: nodeCount }, (_, i) => ({
      id: i,
      x: Math.random() * 100,
      y: Math.random() * 100,
      connections: [],
    }))

    // Create connections between nearby nodes
    generated.forEach((node, i) => {
      const nearby = generated
        .map((other, j) => ({
          index: j,
          distance: Math.hypot(other.x - node.x, other.y - node.y),
        }))
        .filter((d) => d.index !== i && d.distance < 30)
        .slice(0, 3)
        .map((d) => d.index)
      node.connections = nearby
    })

    return generated
  }, [nodeCount])

  const colorClasses = {
    emerald: { node: "bg-emerald-400", line: "stroke-emerald-500/30" },
    violet: { node: "bg-violet-400", line: "stroke-violet-500/30" },
    blue: { node: "bg-blue-400", line: "stroke-blue-500/30" },
  }

  return (
    <div className={cn("absolute inset-0 overflow-hidden pointer-events-none", className)}>
      <svg className="absolute inset-0 w-full h-full">
        {nodes.map((node) =>
          node.connections.map((targetIndex) => {
            const target = nodes[targetIndex]
            return (
              <motion.line
                key={`${node.id}-${targetIndex}`}
                x1={`${node.x}%`}
                y1={`${node.y}%`}
                x2={`${target.x}%`}
                y2={`${target.y}%`}
                className={colorClasses[color].line}
                strokeWidth={1}
                initial={{ pathLength: 0, opacity: 0 }}
                animate={{ pathLength: 1, opacity: 1 }}
                transition={{ duration: 2, delay: Math.random() * 2 }}
              />
            )
          })
        )}
      </svg>
      {nodes.map((node) => (
        <motion.div
          key={node.id}
          className={cn("absolute w-2 h-2 rounded-full", colorClasses[color].node)}
          style={{ left: `${node.x}%`, top: `${node.y}%` }}
          initial={{ scale: 0, opacity: 0 }}
          animate={{ scale: [1, 1.5, 1], opacity: [0.5, 1, 0.5] }}
          transition={{
            duration: 3,
            repeat: Infinity,
            delay: Math.random() * 2,
          }}
        />
      ))}
    </div>
  )
}

// ============================================================================
// DATA STREAM - Flowing data visualization
// ============================================================================

export function DataStream({
  direction = "vertical",
  color = "emerald",
  speed = 1,
  className,
}: {
  direction?: "vertical" | "horizontal"
  color?: "emerald" | "violet" | "blue" | "amber"
  speed?: number
  className?: string
}) {
  const streams = useMemo(() => 
    Array.from({ length: 8 }, (_, i) => ({
      id: i,
      offset: Math.random() * 100,
      duration: (2 + Math.random() * 2) / speed,
      delay: Math.random() * 2,
      width: Math.random() * 2 + 0.5,
      opacity: Math.random() * 0.5 + 0.3,
    })),
    [speed]
  )

  const colorClasses = {
    emerald: "bg-gradient-to-b from-transparent via-emerald-400 to-transparent",
    violet: "bg-gradient-to-b from-transparent via-violet-400 to-transparent",
    blue: "bg-gradient-to-b from-transparent via-blue-400 to-transparent",
    amber: "bg-gradient-to-b from-transparent via-amber-400 to-transparent",
  }

  return (
    <div className={cn("absolute inset-0 overflow-hidden pointer-events-none", className)}>
      {streams.map((stream) => (
        <motion.div
          key={stream.id}
          className={cn(
            "absolute",
            direction === "vertical" ? "w-px h-20" : "h-px w-20",
            colorClasses[color]
          )}
          style={{
            [direction === "vertical" ? "left" : "top"]: `${stream.offset}%`,
            opacity: stream.opacity,
          }}
          animate={{
            [direction === "vertical" ? "y" : "x"]: ["-100%", "500%"],
          }}
          transition={{
            duration: stream.duration,
            repeat: Infinity,
            delay: stream.delay,
            ease: "linear",
          }}
        />
      ))}
    </div>
  )
}

// ============================================================================
// STATUS BEACON - Animated status indicator
// ============================================================================

export function StatusBeacon({
  status = "active",
  size = "md",
  pulse = true,
  className,
}: {
  status?: "active" | "processing" | "warning" | "error" | "idle"
  size?: "sm" | "md" | "lg"
  pulse?: boolean
  className?: string
}) {
  const sizeClasses = {
    sm: "w-2 h-2",
    md: "w-3 h-3",
    lg: "w-4 h-4",
  }

  const colorClasses = {
    active: "bg-emerald-400 shadow-emerald-400/50",
    processing: "bg-blue-400 shadow-blue-400/50",
    warning: "bg-amber-400 shadow-amber-400/50",
    error: "bg-red-400 shadow-red-400/50",
    idle: "bg-zinc-400 shadow-zinc-400/50",
  }

  return (
    <div className={cn("relative", className)}>
      <motion.div
        className={cn("rounded-full shadow-lg", sizeClasses[size], colorClasses[status])}
        animate={pulse && status !== "idle" ? {
          scale: [1, 1.2, 1],
          opacity: [1, 0.8, 1],
        } : undefined}
        transition={{
          duration: status === "processing" ? 1 : 2,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      />
      {pulse && status !== "idle" && (
        <motion.div
          className={cn("absolute inset-0 rounded-full", colorClasses[status].split(" ")[0])}
          initial={{ scale: 1, opacity: 0.5 }}
          animate={{ scale: 2.5, opacity: 0 }}
          transition={{
            duration: 2,
            repeat: Infinity,
            ease: "easeOut",
          }}
        />
      )}
    </div>
  )
}

// ============================================================================
// MORPHING BACKGROUND - Animated gradient mesh
// ============================================================================

export function MorphingBackground({
  colors = ["emerald", "violet", "blue"],
  className,
}: {
  colors?: ("emerald" | "violet" | "blue" | "amber" | "cyan")[]
  className?: string
}) {
  const colorValues = {
    emerald: "rgba(16, 185, 129, 0.15)",
    violet: "rgba(139, 92, 246, 0.15)",
    blue: "rgba(59, 130, 246, 0.15)",
    amber: "rgba(245, 158, 11, 0.15)",
    cyan: "rgba(6, 182, 212, 0.15)",
  }

  return (
    <div className={cn("absolute inset-0 overflow-hidden", className)}>
      {colors.map((color, i) => (
        <motion.div
          key={i}
          className="absolute rounded-full"
          style={{
            width: "60%",
            height: "60%",
            background: `radial-gradient(circle, ${colorValues[color]} 0%, transparent 70%)`,
            filter: "blur(60px)",
          }}
          animate={{
            x: ["0%", "50%", "0%", "-50%", "0%"],
            y: ["0%", "30%", "60%", "30%", "0%"],
          }}
          transition={{
            duration: 20 + i * 5,
            repeat: Infinity,
            ease: "easeInOut",
            delay: i * 2,
          }}
        />
      ))}
    </div>
  )
}

// ============================================================================
// FLOATING CARD - Card with depth and motion
// ============================================================================

export function FloatingCard({
  children,
  depth = 1,
  glow = true,
  glowColor = "emerald",
  className,
}: {
  children: React.ReactNode
  depth?: 1 | 2 | 3
  glow?: boolean
  glowColor?: "emerald" | "violet" | "blue" | "amber"
  className?: string
}) {
  const [isHovered, setIsHovered] = useState(false)
  const x = useMotionValue(0)
  const y = useMotionValue(0)

  const rotateX = useTransform(y, [-100, 100], [5, -5])
  const rotateY = useTransform(x, [-100, 100], [-5, 5])

  const handleMouseMove = (e: React.MouseEvent) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const centerX = rect.left + rect.width / 2
    const centerY = rect.top + rect.height / 2
    x.set(e.clientX - centerX)
    y.set(e.clientY - centerY)
  }

  const handleMouseLeave = () => {
    x.set(0)
    y.set(0)
    setIsHovered(false)
  }

  const depthShadows = {
    1: "shadow-lg",
    2: "shadow-xl",
    3: "shadow-2xl",
  }

  const glowColors = {
    emerald: "shadow-emerald-500/20",
    violet: "shadow-violet-500/20",
    blue: "shadow-blue-500/20",
    amber: "shadow-amber-500/20",
  }

  return (
    <motion.div
      className={cn(
        "relative rounded-2xl border border-border bg-card transition-shadow",
        depthShadows[depth],
        glow && isHovered && glowColors[glowColor],
        className
      )}
      style={{
        perspective: 1000,
        rotateX,
        rotateY,
        transformStyle: "preserve-3d",
      }}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={handleMouseLeave}
      whileHover={{ y: -4, transition: { duration: 0.2 } }}
    >
      {children}
    </motion.div>
  )
}

// ============================================================================
// ACTIVITY INDICATOR - Multi-ring activity visualization
// ============================================================================

export function ActivityIndicator({
  value = 75,
  size = 120,
  color = "emerald",
  animated = true,
  label,
  className,
}: {
  value?: number
  size?: number
  color?: "emerald" | "violet" | "blue" | "amber"
  animated?: boolean
  label?: string
  className?: string
}) {
  const strokeWidth = size * 0.08
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius

  const colorClasses = {
    emerald: { stroke: "stroke-emerald-500", text: "text-emerald-400", bg: "stroke-emerald-500/10" },
    violet: { stroke: "stroke-violet-500", text: "text-violet-400", bg: "stroke-violet-500/10" },
    blue: { stroke: "stroke-blue-500", text: "text-blue-400", bg: "stroke-blue-500/10" },
    amber: { stroke: "stroke-amber-500", text: "text-amber-400", bg: "stroke-amber-500/10" },
  }

  return (
    <div className={cn("relative inline-flex items-center justify-center", className)}>
      <svg width={size} height={size} className="-rotate-90">
        {/* Background ring */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          className={colorClasses[color].bg}
          strokeWidth={strokeWidth}
        />
        {/* Progress ring */}
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          className={colorClasses[color].stroke}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ 
            strokeDashoffset: circumference - (value / 100) * circumference,
          }}
          transition={{ duration: 1.5, ease: "easeOut" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <motion.span
          className={cn(
            "font-bold", 
            colorClasses[color].text,
            // Dynamic text sizing based on ring size
            size <= 50 ? "text-xs" : size <= 80 ? "text-sm" : size <= 120 ? "text-xl" : "text-2xl"
          )}
          initial={{ opacity: 0, scale: 0.5 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.5 }}
        >
          {value}%
        </motion.span>
        {label && size > 60 && (
          <span className="text-xs text-muted-foreground mt-1">{label}</span>
        )}
      </div>
    </div>
  )
}

// ============================================================================
// TYPING INDICATOR - AI typing feedback
// ============================================================================

export function TypingIndicator({
  color = "emerald",
  className,
}: {
  color?: "emerald" | "violet" | "blue"
  className?: string
}) {
  const colorClasses = {
    emerald: "bg-emerald-400",
    violet: "bg-violet-400",
    blue: "bg-blue-400",
  }

  return (
    <div className={cn("flex items-center gap-1", className)}>
      {[0, 1, 2].map((i) => (
        <motion.div
          key={i}
          className={cn("w-2 h-2 rounded-full", colorClasses[color])}
          animate={{
            y: [0, -6, 0],
            opacity: [0.5, 1, 0.5],
          }}
          transition={{
            duration: 0.8,
            repeat: Infinity,
            delay: i * 0.15,
            ease: "easeInOut",
          }}
        />
      ))}
    </div>
  )
}

// ============================================================================
// SHIMMER TEXT - Text with animated shimmer effect
// ============================================================================

export function ShimmerText({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  return (
    <motion.span
      className={cn(
        "relative inline-block bg-gradient-to-r from-foreground via-foreground/50 to-foreground bg-clip-text text-transparent bg-[length:200%_100%]",
        className
      )}
      animate={{
        backgroundPosition: ["200% 0", "-200% 0"],
      }}
      transition={{
        duration: 3,
        repeat: Infinity,
        ease: "linear",
      }}
    >
      {children}
    </motion.span>
  )
}

// ============================================================================
// COUNTER - Animated number counter
// ============================================================================

export function AnimatedCounter({
  value,
  duration = 2,
  className,
}: {
  value: number
  duration?: number
  className?: string
}) {
  const [displayValue, setDisplayValue] = useState(0)

  useEffect(() => {
    let startTime: number
    let animationFrame: number

    const animate = (currentTime: number) => {
      if (!startTime) startTime = currentTime
      const progress = Math.min((currentTime - startTime) / (duration * 1000), 1)
      
      setDisplayValue(Math.floor(progress * value))
      
      if (progress < 1) {
        animationFrame = requestAnimationFrame(animate)
      }
    }

    animationFrame = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(animationFrame)
  }, [value, duration])

  return (
    <motion.span
      className={className}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
    >
      {displayValue.toLocaleString()}
    </motion.span>
  )
}

// ============================================================================
// GRID PATTERN - Subtle animated grid background
// ============================================================================

export function GridPattern({
  size = 40,
  color = "default",
  animated = true,
  className,
}: {
  size?: number
  color?: "default" | "emerald" | "violet" | "blue"
  animated?: boolean
  className?: string
}) {
  const colorClasses = {
    default: "stroke-border/30",
    emerald: "stroke-emerald-500/10",
    violet: "stroke-violet-500/10",
    blue: "stroke-blue-500/10",
  }

  return (
    <div className={cn("absolute inset-0 overflow-hidden pointer-events-none", className)}>
      <svg className="absolute inset-0 w-full h-full">
        <defs>
          <pattern
            id={`grid-${color}`}
            width={size}
            height={size}
            patternUnits="userSpaceOnUse"
          >
            <path
              d={`M ${size} 0 L 0 0 0 ${size}`}
              fill="none"
              className={colorClasses[color]}
              strokeWidth="0.5"
            />
          </pattern>
        </defs>
        <motion.rect
          width="100%"
          height="100%"
          fill={`url(#grid-${color})`}
          initial={{ opacity: 0 }}
          animate={animated ? { opacity: [0.3, 0.5, 0.3] } : { opacity: 0.4 }}
          transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
        />
      </svg>
    </div>
  )
}
