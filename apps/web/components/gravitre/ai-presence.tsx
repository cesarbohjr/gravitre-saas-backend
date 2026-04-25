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
                    "0 0 20px rgba(59, 130, 246, 0.3)",
                    "0 0 40px rgba(59, 130, 246, 0.5)",
                    "0 0 20px rgba(59, 130, 246, 0.3)",
                  ]
                : isListening
                  ? [
                      "0 0 15px rgba(139, 92, 246, 0.2)",
                      "0 0 25px rgba(139, 92, 246, 0.4)",
                      "0 0 15px rgba(139, 92, 246, 0.2)",
                    ]
                  : [
                      "0 0 10px rgba(59, 130, 246, 0.1)",
                      "0 0 20px rgba(59, 130, 246, 0.2)",
                      "0 0 10px rgba(59, 130, 246, 0.1)",
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
                ? "bg-gradient-to-br from-blue-500 to-blue-600" 
                : isListening
                  ? "bg-gradient-to-br from-violet-500 to-purple-600"
                  : "bg-gradient-to-br from-blue-500/20 to-blue-600/10 ring-1 ring-blue-500/20"
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
                className={isProcessing || isListening ? "text-white" : "text-blue-400"} 
              />
            </motion.div>

            {/* Processing indicator dots */}
            {isProcessing && (
              <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 flex gap-0.5">
                {[0, 1, 2].map((i) => (
                  <motion.div
                    key={i}
                    className="h-1 w-1 rounded-full bg-blue-300"
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
              className="absolute inset-0 rounded-xl border-2 border-violet-400"
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
                className="rounded-full bg-blue-500/20 px-2 py-0.5 text-[9px] font-medium text-blue-400"
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
                  className="flex items-center gap-1.5 text-xs text-blue-400"
                >
                  <Icon name="activity" size="xs" />
                  <span>Processing your request</span>
                  <motion.span className="flex gap-0.5">
                    {[0, 1, 2].map((i) => (
                      <motion.span
                        key={i}
                        className="inline-block h-1 w-1 rounded-full bg-blue-400"
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
          className="absolute inset-0 rounded-full bg-blue-500/30 blur-xl"
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
              ? "bg-gradient-to-br from-blue-500 to-blue-600" 
              : "bg-card border border-border"
            }
          `}
        >
          <Icon name="ai" size="lg" emphasis className={isActive ? "text-white" : "text-muted-foreground"} />
        </div>
        {isActive && (
          <span className="absolute -top-1 -right-1 flex h-3 w-3">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-3 w-3 bg-blue-500" />
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
      <div className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-500/20">
        <Icon name="ai" size="sm" emphasis className="text-blue-400" />
      </div>
      <div className="flex gap-1">
        {[0, 1, 2].map((i) => (
          <motion.div
            key={i}
            className="h-2 w-2 rounded-full bg-blue-400"
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
