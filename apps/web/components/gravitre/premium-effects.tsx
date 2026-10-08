"use client"

import { useEffect, useRef, useState, useMemo } from "react"
import { motion, useMotionValue, useSpring, AnimatePresence, useReducedMotion } from "framer-motion"
import { cn } from "@/lib/utils"

// ============================================================================
// MOTION SYSTEM NOTE
// Shared motion variants/tokens (entrance, hover, press, success, error) and
// the `useMotionPrefs()` reduced-motion hook live in `@/lib/animations`.
// The ambient/continuous effects below (ParticleField, NeuralNetwork,
// DataStream, MorphingBackground) self-disable under prefers-reduced-motion.
// ============================================================================

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
}

function seededUnit(seed: number) {
  const value = Math.sin(seed * 12.9898) * 43758.5453
  return value - Math.floor(value)
}

interface ParticleFieldProps {
  count?: number
  color?: "emerald" | "violet" | "blue" | "amber" | "cyan"
  interactive?: boolean
  className?: string
}

export function ParticleField(props: ParticleFieldProps) {
  // Decorative ambient particles — skip entirely under reduced motion.
  const reduced = useReducedMotion()
  if (reduced) return null
  return <ParticleFieldImpl {...props} />
}

function ParticleFieldImpl({
  count = 50,
  color = "emerald",
  interactive = true,
  className,
}: ParticleFieldProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mouseX = useMotionValue(0)
  const mouseY = useMotionValue(0)
  const smoothX = useSpring(mouseX, { stiffness: 50, damping: 20 })
  const smoothY = useSpring(mouseY, { stiffness: 50, damping: 20 })

  // Theme tokens (app/globals.css) so particles follow light/dark themes.
  const colorMap = {
    emerald: "var(--g-brand)",
    violet: "var(--chart-4)",
    blue: "var(--info)",
    amber: "var(--warning)",
    cyan: "var(--g-signal)",
  }

  const particles = useMemo<Particle[]>(
    () =>
      Array.from({ length: count }, (_, i) => ({
        id: i,
        x: seededUnit(i + 1) * 100,
        y: seededUnit(i + 101) * 100,
        size: seededUnit(i + 201) * 3 + 1,
        opacity: seededUnit(i + 301) * 0.5 + 0.2,
        speedX: (seededUnit(i + 401) - 0.5) * 0.02,
        speedY: (seededUnit(i + 501) - 0.5) * 0.02,
      })),
    [count, color]
  )

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
            backgroundColor: `color-mix(in srgb, ${colorMap[color]} ${Math.round(particle.opacity * 100)}%, transparent)`,
            boxShadow: `0 0 ${particle.size * 2}px color-mix(in srgb, ${colorMap[color]} ${Math.round(particle.opacity * 50)}%, transparent)`,
          }}
          animate={{
            x: [0, seededUnit(particle.id + 701) * 20 - 10, 0],
            y: [0, seededUnit(particle.id + 801) * 20 - 10, 0],
            scale: [1, 1.2, 1],
          }}
          transition={{
            duration: 5 + seededUnit(particle.id + 901) * 5,
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
    emerald: "border-success/50",
    violet: "border-chart-4/50",
    blue: "border-info/50",
    amber: "border-warning/50",
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
    emerald: "from-success via-success to-success",
    violet: "from-chart-4 via-chart-4 to-[color:var(--g-intelligence-bright)]",
    blue: "from-info via-info to-info",
    amber: "from-warning via-warning to-destructive",
    mixed: "from-success via-chart-4 to-info",
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

interface NeuralNetworkProps {
  nodeCount?: number
  color?: "emerald" | "violet" | "blue" | "cyan"
  className?: string
}

export function NeuralNetwork(props: NeuralNetworkProps) {
  const reduced = useReducedMotion()
  if (reduced) return null
  return <NeuralNetworkImpl {...props} />
}

function NeuralNetworkImpl({
  nodeCount = 15,
  color = "emerald",
  className,
}: NeuralNetworkProps) {
  const nodes = useMemo<Node[]>(() => {
    const generated: Node[] = Array.from({ length: nodeCount }, (_, i) => ({
      id: i,
      x: seededUnit(i + 1001) * 100,
      y: seededUnit(i + 1101) * 100,
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
    emerald: { node: "bg-success", line: "stroke-success/30" },
    violet: { node: "bg-chart-4", line: "stroke-chart-4/30" },
    blue: { node: "bg-info", line: "stroke-info/30" },
    cyan: { node: "bg-info", line: "stroke-info/30" },
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
                transition={{ duration: 2, delay: seededUnit(node.id * 100 + targetIndex + 1201) * 2 }}
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
            delay: seededUnit(node.id + 1301) * 2,
          }}
        />
      ))}
    </div>
  )
}

// ============================================================================
// DATA STREAM - Flowing data visualization
// ============================================================================

interface DataStreamProps {
  direction?: "vertical" | "horizontal"
  color?: "emerald" | "violet" | "blue" | "amber"
  speed?: number
  className?: string
}

export function DataStream(props: DataStreamProps) {
  const reduced = useReducedMotion()
  if (reduced) return null
  return <DataStreamImpl {...props} />
}

function DataStreamImpl({
  direction = "vertical",
  color = "emerald",
  speed = 1,
  className,
}: DataStreamProps) {
  const streams = useMemo(() => 
    Array.from({ length: 8 }, (_, i) => ({
      id: i,
      offset: seededUnit(i + 1401) * 100,
      duration: (2 + seededUnit(i + 1501) * 2) / speed,
      delay: seededUnit(i + 1601) * 2,
      width: seededUnit(i + 1701) * 2 + 0.5,
      opacity: seededUnit(i + 1801) * 0.5 + 0.3,
    })),
    [speed]
  )

  const colorClasses = {
    emerald: "bg-gradient-to-b from-transparent via-success to-transparent",
    violet: "bg-gradient-to-b from-transparent via-chart-4 to-transparent",
    blue: "bg-gradient-to-b from-transparent via-info to-transparent",
    amber: "bg-gradient-to-b from-transparent via-warning to-transparent",
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
    active: "bg-success shadow-success/50",
    processing: "bg-info shadow-info/50",
    warning: "bg-warning shadow-warning/50",
    error: "bg-destructive shadow-destructive/50",
    idle: "bg-status-idle shadow-status-idle/50",
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

interface MorphingBackgroundProps {
  colors?: ("emerald" | "violet" | "blue" | "amber" | "cyan")[]
  className?: string
}

export function MorphingBackground(props: MorphingBackgroundProps) {
  const reduced = useReducedMotion()
  if (reduced) return null
  return <MorphingBackgroundImpl {...props} />
}

function MorphingBackgroundImpl({
  colors = ["emerald", "violet", "blue"],
  className,
}: MorphingBackgroundProps) {
  const colorValues = {
    emerald: "color-mix(in srgb, var(--g-brand) 15%, transparent)",
    violet: "color-mix(in srgb, var(--chart-4) 15%, transparent)",
    blue: "color-mix(in srgb, var(--info) 15%, transparent)",
    amber: "color-mix(in srgb, var(--warning) 15%, transparent)",
    cyan: "color-mix(in srgb, var(--g-signal) 15%, transparent)",
  }

  return (
    <div className={cn("absolute inset-0 overflow-hidden pointer-events-none", className)}>
      {colors.map((color, i) => (
        <motion.div
          key={i}
          className="pointer-events-none absolute rounded-full"
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

  const depthShadows = {
    1: "shadow-lg",
    2: "shadow-xl",
    3: "shadow-2xl",
  }

  const glowColors = {
    emerald: "shadow-success/20",
    violet: "shadow-chart-4/20",
    blue: "shadow-info/20",
    amber: "shadow-warning/20",
  }

  return (
    <motion.div
      className={cn(
        "relative rounded-2xl border border-border bg-card transition-shadow",
        depthShadows[depth],
        glow && isHovered && glowColors[glowColor],
        className
      )}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
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
    emerald: { stroke: "stroke-success", text: "text-success", bg: "stroke-success/10" },
    violet: { stroke: "stroke-chart-4", text: "text-intelligence-text", bg: "stroke-chart-4/10" },
    blue: { stroke: "stroke-info", text: "text-info", bg: "stroke-info/10" },
    amber: { stroke: "stroke-warning", text: "text-warning", bg: "stroke-warning/10" },
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
    emerald: "bg-success",
    violet: "bg-chart-4",
    blue: "bg-info",
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
    emerald: "stroke-success/10",
    violet: "stroke-chart-4/10",
    blue: "stroke-info/10",
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
