"use client"

import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Icon, type IconName } from "@/lib/icons"

interface AIPresenceProps {
  isProcessing?: boolean
  isListening?: boolean
  className?: string
}

const ambientMessages: { text: string; icon: IconName }[] = [
  { text: "Monitoring systems", icon: "view" },
  { text: "Ready to assist", icon: "ai" },
  { text: "Analyzing patterns", icon: "activity" },
  { text: "Security verified", icon: "shield" },
  { text: "Models loaded", icon: "aiAnalysis" },
  { text: "Standing by", icon: "execution" },
]

export function AIPresence({ isProcessing = false, isListening = false, className }: AIPresenceProps) {
  const [messageIndex, setMessageIndex] = useState(0)
  const [showMessage, setShowMessage] = useState(true)

  useEffect(() => {
    if (isProcessing) return

    const interval = setInterval(() => {
      setShowMessage(false)
      setTimeout(() => {
        setMessageIndex((prev) => (prev + 1) % ambientMessages.length)
        setShowMessage(true)
      }, 300)
    }, 4000)

    return () => clearInterval(interval)
  }, [isProcessing])

  const currentMessage = ambientMessages[messageIndex]

  return (
    <div className={className}>
      <div className="flex items-center gap-3">
        {/* Animated AI Orb */}
        <div className="relative">
          {/* Outer glow rings */}
          <motion.div
            className="absolute inset-0 rounded-xl"
            animate={{
              boxShadow: isProcessing
                ? [
                    "0 0 20px color-mix(in srgb, var(--g-intelligence) 30%, transparent)",
                    "0 0 40px color-mix(in srgb, var(--g-intelligence) 50%, transparent)",
                    "0 0 20px color-mix(in srgb, var(--g-intelligence) 30%, transparent)",
                  ]
                : isListening
                  ? [
                      "0 0 15px color-mix(in srgb, var(--g-electric) 20%, transparent)",
                      "0 0 25px color-mix(in srgb, var(--g-electric) 40%, transparent)",
                      "0 0 15px color-mix(in srgb, var(--g-electric) 20%, transparent)",
                    ]
                  : [
                      "0 0 10px color-mix(in srgb, var(--g-intelligence) 10%, transparent)",
                      "0 0 20px color-mix(in srgb, var(--g-intelligence) 20%, transparent)",
                      "0 0 10px color-mix(in srgb, var(--g-intelligence) 10%, transparent)",
                    ],
            }}
            transition={{
              duration: isProcessing ? 1 : 3,
              repeat: Infinity,
              ease: "easeInOut",
            }}
          />

          {/* Core icon container */}
          <motion.div
            className={`
              relative flex h-10 w-10 items-center justify-center rounded-xl
              ${isProcessing 
                ? "bg-[color:var(--g-intelligence)]" 
                : isListening
                  ? "bg-[color:var(--g-electric)]"
                  : "bg-gradient-to-br from-[color:var(--g-intelligence)]/20 to-[color:var(--g-intelligence)]/10 ring-1 ring-[color:var(--g-intelligence)]/20"
              }
            `}
            animate={isProcessing ? { scale: [1, 1.05, 1] } : {}}
            transition={{ duration: 0.8, repeat: Infinity }}
          >
            <motion.div
              animate={isProcessing ? { rotate: 360 } : { rotate: 0 }}
              transition={{ duration: 3, repeat: Infinity, ease: "linear" }}
            >
              <Icon 
                name="ai" 
                size="lg" 
                emphasis 
                className={isProcessing || isListening ? "text-primary-foreground" : "text-intelligence-text"} 
              />
            </motion.div>

            {/* Processing indicator dots */}
            {isProcessing && (
              <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 flex gap-0.5">
                {[0, 1, 2].map((i) => (
                  <motion.div
                    key={i}
                    className="h-1 w-1 rounded-full bg-primary-foreground/80"
                    animate={{ opacity: [0.3, 1, 0.3], scale: [0.8, 1, 0.8] }}
                    transition={{
                      duration: 0.6,
                      repeat: Infinity,
                      delay: i * 0.15,
                    }}
                  />
                ))}
              </div>
            )}
          </motion.div>

          {/* Listening indicator ring */}
          {isListening && (
            <motion.div
              className="absolute inset-0 rounded-xl border-2 border-[color:var(--g-electric)]"
              animate={{ scale: [1, 1.2, 1], opacity: [0.8, 0, 0.8] }}
              transition={{ duration: 1.5, repeat: Infinity }}
            />
          )}
        </div>

        {/* Status Text */}
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h1 className="text-sm font-semibold text-foreground">AI Assistant</h1>
            {isProcessing && (
              <motion.span
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                className="rounded-full bg-[color:var(--g-intelligence)]/20 px-2 py-0.5 text-[9px] font-medium text-intelligence-text"
              >
                Working
              </motion.span>
            )}
          </div>
          
          {/* Ambient status message */}
          <div className="h-4 overflow-hidden">
            <AnimatePresence mode="wait">
              {showMessage && !isProcessing && (
                <motion.div
                  key={messageIndex}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ duration: 0.3 }}
                  className="flex items-center gap-1.5 text-xs text-muted-foreground"
                >
                  <Icon name={currentMessage.icon} size="xs" />
                  <span>{currentMessage.text}</span>
                </motion.div>
              )}
              {isProcessing && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex items-center gap-1.5 text-xs text-intelligence-text"
                >
                  <Icon name="activity" size="xs" />
                  <span>Processing your request</span>
                  <motion.span className="flex gap-0.5">
                    {[0, 1, 2].map((i) => (
                      <motion.span
                        key={i}
                        className="inline-block h-1 w-1 rounded-full bg-[color:var(--g-intelligence)]"
                        animate={{ opacity: [0.3, 1, 0.3] }}
                        transition={{ duration: 0.8, repeat: Infinity, delay: i * 0.2 }}
                      />
                    ))}
                  </motion.span>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </div>
  )
}

// Floating AI indicator for bottom corner
export function AIFloatingIndicator({ isActive = false }: { isActive?: boolean }) {
  return (
    <motion.div
      className="fixed bottom-6 right-6 z-50"
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      whileHover={{ scale: 1.1 }}
    >
      <div className="relative">
        <motion.div
          className="absolute inset-0 rounded-full bg-[color:var(--g-intelligence)]/30 blur-xl"
          animate={{
            scale: isActive ? [1, 1.5, 1] : [1, 1.2, 1],
            opacity: isActive ? [0.5, 0.8, 0.5] : [0.3, 0.5, 0.3],
          }}
          transition={{ duration: 2, repeat: Infinity }}
        />
        <div
          className={`
            relative flex h-12 w-12 items-center justify-center rounded-full shadow-lg
            ${isActive 
              ? "bg-[color:var(--g-intelligence)]" 
              : "bg-card border border-border"
            }
          `}
        >
          <Icon name="ai" size="lg" emphasis className={isActive ? "text-primary-foreground" : "text-muted-foreground"} />
        </div>
        {isActive && (
          <span className="absolute -top-1 -right-1 flex h-3 w-3">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[color:var(--g-intelligence)] opacity-75" />
            <span className="relative inline-flex rounded-full h-3 w-3 bg-[color:var(--g-intelligence)]" />
          </span>
        )}
      </div>
    </motion.div>
  )
}

// Typing indicator for AI responses
export function AITypingIndicator() {
  return (
    <div className="flex items-center gap-2 p-3 rounded-lg bg-secondary/50">
      <div className="flex h-6 w-6 items-center justify-center rounded-full bg-[color:var(--g-intelligence)]/20">
        <Icon name="ai" size="sm" emphasis className="text-intelligence-text" />
      </div>
      <div className="flex gap-1">
        {[0, 1, 2].map((i) => (
          <motion.div
            key={i}
            className="h-2 w-2 rounded-full bg-[color:var(--g-intelligence)]"
            animate={{
              y: [0, -6, 0],
              opacity: [0.5, 1, 0.5],
            }}
            transition={{
              duration: 0.6,
              repeat: Infinity,
              delay: i * 0.15,
              ease: "easeInOut",
            }}
          />
        ))}
      </div>
    </div>
  )
}
