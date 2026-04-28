"use client"

import { useEffect, useRef, useState } from "react"
import { motion } from "framer-motion"
import { DotLottieReact } from "@lottiefiles/dotlottie-react"

// DotLottie component for .lottie files from LottieFiles
interface DotLottieAnimationProps {
  src: string
  className?: string
  loop?: boolean
  autoplay?: boolean
  speed?: number
  onComplete?: () => void
}

export function DotLottieAnimation({
  src,
  className = "",
  loop = true,
  autoplay = true,
  speed = 1,
  onComplete,
}: DotLottieAnimationProps) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3 }}
      className={className}
    >
      <DotLottieReact
        src={src}
        loop={loop}
        autoplay={autoplay}
        speed={speed}
      />
    </motion.div>
  )
}

interface LottieAnimationProps {
  src: string
  className?: string
  loop?: boolean
  autoplay?: boolean
  speed?: number
}

// Simple Lottie player using lottie-web
export function LottieAnimation({ 
  src, 
  className = "", 
  loop = true, 
  autoplay = true,
  speed = 1 
}: LottieAnimationProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [isLoaded, setIsLoaded] = useState(false)

  useEffect(() => {
    let animation: any

    const loadLottie = async () => {
      try {
        const lottie = (await import("lottie-web")).default
        
        if (containerRef.current) {
          animation = lottie.loadAnimation({
            container: containerRef.current,
            renderer: "svg",
            loop,
            autoplay,
            path: src,
          })
          
          animation.setSpeed(speed)
          animation.addEventListener("DOMLoaded", () => setIsLoaded(true))
        }
      } catch (error) {
        console.error("[v0] Failed to load Lottie animation:", error)
      }
    }

    loadLottie()

    return () => {
      if (animation) {
        animation.destroy()
      }
    }
  }, [src, loop, autoplay, speed])

  return (
    <motion.div
      ref={containerRef}
      className={className}
      initial={{ opacity: 0 }}
      animate={{ opacity: isLoaded ? 1 : 0 }}
      transition={{ duration: 0.5 }}
    />
  )
}

// Premium animated background patterns
export function AnimatedGradientOrb({ 
  className = "", 
  color = "emerald",
  size = "lg",
  delay = 0 
}: { 
  className?: string
  color?: "emerald" | "amber" | "blue" | "purple"
  size?: "sm" | "md" | "lg" | "xl"
  delay?: number
}) {
  const sizeClasses = {
    sm: "w-32 h-32",
    md: "w-64 h-64",
    lg: "w-96 h-96",
    xl: "w-[500px] h-[500px]"
  }
  
  const colorClasses = {
    emerald: "from-emerald-500/30 via-emerald-400/20 to-transparent",
    amber: "from-amber-500/30 via-orange-400/20 to-transparent",
    blue: "from-blue-500/30 via-cyan-400/20 to-transparent",
    purple: "from-purple-500/30 via-violet-400/20 to-transparent"
  }

  return (
    <motion.div
      className={`absolute rounded-full blur-3xl bg-gradient-radial ${colorClasses[color]} ${sizeClasses[size]} ${className}`}
      animate={{
        scale: [1, 1.2, 1],
        opacity: [0.3, 0.5, 0.3],
        x: [0, 20, 0],
        y: [0, -20, 0],
      }}
      transition={{
        duration: 8,
        delay,
        repeat: Infinity,
        ease: "easeInOut",
      }}
    />
  )
}

// Animated pulse ring effect
export function PulseRing({ 
  className = "", 
  color = "emerald" 
}: { 
  className?: string
  color?: "emerald" | "amber" | "blue" 
}) {
  const colorClasses = {
    emerald: "border-emerald-500",
    amber: "border-amber-500",
    blue: "border-blue-500"
  }

  return (
    <div className={`relative ${className}`}>
      {[0, 1, 2].map((i) => (
        <motion.div
          key={i}
          className={`absolute inset-0 rounded-full border ${colorClasses[color]}`}
          initial={{ scale: 0.8, opacity: 0.8 }}
          animate={{ scale: 2, opacity: 0 }}
          transition={{
            duration: 2,
            delay: i * 0.6,
            repeat: Infinity,
            ease: "easeOut",
          }}
        />
      ))}
    </div>
  )
}

// Floating particles effect
export function FloatingParticles({ 
  count = 20, 
  className = "" 
}: { 
  count?: number
  className?: string 
}) {
  return (
    <div className={`absolute inset-0 overflow-hidden pointer-events-none ${className}`}>
      {Array.from({ length: count }).map((_, i) => (
        <motion.div
          key={i}
          className="absolute w-1 h-1 bg-emerald-400/30 rounded-full"
          initial={{
            x: `${Math.random() * 100}%`,
            y: `${Math.random() * 100}%`,
          }}
          animate={{
            y: [null, "-100%"],
            opacity: [0, 1, 0],
          }}
          transition={{
            duration: 4 + Math.random() * 4,
            delay: Math.random() * 4,
            repeat: Infinity,
            ease: "linear",
          }}
        />
      ))}
    </div>
  )
}

// Animated connection lines
export function ConnectionLines({ className = "" }: { className?: string }) {
  return (
    <svg className={`absolute inset-0 w-full h-full ${className}`} xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="line-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="transparent" />
          <stop offset="50%" stopColor="rgb(16 185 129 / 0.3)" />
          <stop offset="100%" stopColor="transparent" />
        </linearGradient>
      </defs>
      {[...Array(5)].map((_, i) => (
        <motion.line
          key={i}
          x1="0%"
          y1={`${20 + i * 15}%`}
          x2="100%"
          y2={`${20 + i * 15}%`}
          stroke="url(#line-gradient)"
          strokeWidth="1"
          initial={{ pathLength: 0, opacity: 0 }}
          animate={{ pathLength: 1, opacity: [0, 0.5, 0] }}
          transition={{
            duration: 3,
            delay: i * 0.5,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        />
      ))}
    </svg>
  )
}

// Animated typing effect for code blocks
export function TypewriterText({ 
  text, 
  speed = 50,
  className = "" 
}: { 
  text: string
  speed?: number
  className?: string 
}) {
  const [displayText, setDisplayText] = useState("")
  const [currentIndex, setCurrentIndex] = useState(0)

  useEffect(() => {
    if (currentIndex < text.length) {
      const timeout = setTimeout(() => {
        setDisplayText(prev => prev + text[currentIndex])
        setCurrentIndex(prev => prev + 1)
      }, speed)
      
      return () => clearTimeout(timeout)
    }
  }, [currentIndex, text, speed])

  return (
    <span className={className}>
      {displayText}
      <motion.span
        animate={{ opacity: [1, 0] }}
        transition={{ duration: 0.5, repeat: Infinity }}
        className="inline-block w-2 h-4 bg-emerald-400 ml-0.5"
      />
    </span>
  )
}

// Animated counter
export function AnimatedCounter({ 
  value, 
  duration = 2,
  suffix = "",
  className = "" 
}: { 
  value: number
  duration?: number
  suffix?: string
  className?: string 
}) {
  const [count, setCount] = useState(0)
  const [hasAnimated, setHasAnimated] = useState(false)

  useEffect(() => {
    if (hasAnimated) return

    const start = 0
    const end = value
    const incrementTime = (duration * 1000) / end
    let current = start

    const timer = setInterval(() => {
      current += 1
      setCount(current)
      if (current >= end) {
        clearInterval(timer)
        setHasAnimated(true)
      }
    }, incrementTime)

    return () => clearInterval(timer)
  }, [value, duration, hasAnimated])

  return (
    <span className={className}>
      {count.toLocaleString()}{suffix}
    </span>
  )
}
