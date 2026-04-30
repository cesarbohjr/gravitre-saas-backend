// Shared Animation Utilities for Gravitre UI
// Based on premium interaction guidelines for alive, responsive, intelligent feel

import type { Variants, Transition } from "framer-motion"

// ============================================
// TIMING CONSTANTS
// ============================================
export const timing = {
  micro: 0.15,      // 150ms - micro interactions (hover, press)
  ui: 0.25,         // 250ms - UI transitions
  major: 0.4,       // 400ms - major transitions
  slow: 0.6,        // 600ms - emphasis animations
} as const

// ============================================
// EASING CURVES
// ============================================
export const easing = {
  // Smooth for most transitions
  smooth: [0.4, 0, 0.2, 1],
  // Snappy for quick interactions
  snappy: [0.2, 0, 0, 1],
  // Bounce for playful feedback
  bounce: [0.34, 1.56, 0.64, 1],
  // Gentle for subtle animations
  gentle: [0.25, 0.1, 0.25, 1],
  // Spring-like
  spring: { type: "spring", stiffness: 300, damping: 25 },
} as const

// ============================================
// CARD INTERACTIONS
// ============================================
export const cardVariants: Variants = {
  initial: { 
    opacity: 0, 
    y: 20, 
    scale: 0.98 
  },
  animate: { 
    opacity: 1, 
    y: 0, 
    scale: 1,
    transition: { 
      duration: timing.ui, 
      ease: easing.smooth 
    }
  },
  exit: { 
    opacity: 0, 
    y: -10, 
    scale: 0.98,
    transition: { 
      duration: timing.micro 
    }
  },
  hover: { 
    y: -2, 
    scale: 1.01,
    boxShadow: "0 10px 40px -10px rgba(0,0,0,0.3)",
    transition: { 
      duration: timing.micro, 
      ease: easing.snappy 
    }
  },
  tap: { 
    scale: 0.98,
    transition: { 
      duration: 0.1 
    }
  }
}

// Interactive card for connectors, workflows, etc.
export const interactiveCardVariants: Variants = {
  initial: { 
    opacity: 0, 
    y: 20 
  },
  animate: { 
    opacity: 1, 
    y: 0 
  },
  hover: { 
    y: -4,
    transition: { 
      duration: timing.micro, 
      ease: easing.snappy 
    }
  },
  tap: { 
    scale: 0.97,
    transition: { 
      duration: 0.1 
    }
  }
}

// ============================================
// BUTTON INTERACTIONS
// ============================================
export const buttonVariants: Variants = {
  initial: { scale: 1 },
  hover: { 
    scale: 1.02,
    transition: { 
      duration: timing.micro 
    }
  },
  tap: { 
    scale: 0.97,
    transition: { 
      duration: 0.1 
    }
  }
}

// Primary action button with glow
export const primaryButtonVariants: Variants = {
  initial: { scale: 1, boxShadow: "0 0 0 rgba(16, 185, 129, 0)" },
  hover: { 
    scale: 1.02,
    boxShadow: "0 0 20px rgba(16, 185, 129, 0.3)",
    transition: { 
      duration: timing.micro 
    }
  },
  tap: { 
    scale: 0.97,
    transition: { 
      duration: 0.1 
    }
  }
}

// ============================================
// LIST ITEM STAGGER
// ============================================
export const listContainerVariants: Variants = {
  initial: { opacity: 0 },
  animate: {
    opacity: 1,
    transition: {
      staggerChildren: 0.05,
      delayChildren: 0.1
    }
  }
}

export const listItemVariants: Variants = {
  initial: { opacity: 0, x: -20 },
  animate: { 
    opacity: 1, 
    x: 0,
    transition: {
      duration: timing.ui,
      ease: easing.smooth
    }
  },
  exit: { 
    opacity: 0, 
    x: 20,
    transition: {
      duration: timing.micro
    }
  }
}

// ============================================
// PAGE TRANSITIONS
// ============================================
export const pageVariants: Variants = {
  initial: { 
    opacity: 0, 
    y: 10 
  },
  animate: { 
    opacity: 1, 
    y: 0,
    transition: {
      duration: timing.ui,
      ease: easing.smooth,
      staggerChildren: 0.1
    }
  },
  exit: { 
    opacity: 0, 
    y: -10,
    transition: {
      duration: timing.micro
    }
  }
}

export const sectionVariants: Variants = {
  initial: { opacity: 0, y: 20 },
  animate: { 
    opacity: 1, 
    y: 0,
    transition: {
      duration: timing.ui,
      ease: easing.smooth
    }
  }
}

// ============================================
// THINKING / PROCESSING STATES
// ============================================
export const thinkingDotVariants: Variants = {
  animate: {
    y: [0, -4, 0],
    transition: {
      duration: 0.6,
      repeat: Infinity,
      ease: "easeInOut"
    }
  }
}

export const pulseVariants: Variants = {
  animate: {
    scale: [1, 1.05, 1],
    opacity: [0.7, 1, 0.7],
    transition: {
      duration: 2,
      repeat: Infinity,
      ease: "easeInOut"
    }
  }
}

export const shimmerVariants: Variants = {
  animate: {
    x: ["-100%", "100%"],
    transition: {
      duration: 1.5,
      repeat: Infinity,
      ease: "linear"
    }
  }
}

// ============================================
// NODE / WORKFLOW INTERACTIONS
// ============================================
export const nodeVariants: Variants = {
  initial: { 
    opacity: 0, 
    scale: 0.8 
  },
  animate: { 
    opacity: 1, 
    scale: 1,
    transition: easing.spring
  },
  selected: {
    scale: 1.02,
    boxShadow: "0 0 0 2px var(--info), 0 0 20px rgba(59, 130, 246, 0.3)",
    transition: { 
      duration: timing.micro 
    }
  },
  hover: {
    scale: 1.02,
    transition: { 
      duration: timing.micro 
    }
  },
  drag: {
    scale: 1.05,
    boxShadow: "0 20px 40px -10px rgba(0,0,0,0.4)",
    transition: { 
      duration: timing.micro 
    }
  }
}

export const connectionLineVariants: Variants = {
  initial: { pathLength: 0, opacity: 0 },
  animate: { 
    pathLength: 1, 
    opacity: 1,
    transition: {
      duration: timing.major,
      ease: easing.smooth
    }
  }
}

// ============================================
// STATUS INDICATORS
// ============================================
export const statusPulseVariants: Variants = {
  active: {
    scale: [1, 1.2, 1],
    opacity: [1, 0.5, 1],
    transition: {
      duration: 1.5,
      repeat: Infinity,
      ease: "easeInOut"
    }
  },
  idle: {
    scale: 1,
    opacity: 0.6
  }
}

export const successVariants: Variants = {
  initial: { scale: 0, opacity: 0 },
  animate: { 
    scale: 1, 
    opacity: 1,
    transition: {
      type: "spring",
      stiffness: 400,
      damping: 15
    }
  }
}

export const errorShakeVariants: Variants = {
  initial: { x: 0 },
  animate: {
    x: [0, -8, 8, -8, 8, 0],
    transition: {
      duration: 0.5,
      ease: "easeInOut"
    }
  }
}

// ============================================
// AGENT ORB ANIMATIONS
// ============================================
export const orbVariants: Variants = {
  initial: { 
    opacity: 0, 
    y: 30, 
    scale: 0.8 
  },
  animate: { 
    opacity: 1, 
    y: 0, 
    scale: 1,
    transition: easing.spring
  },
  hover: { 
    scale: 1.08, 
    y: -8,
    transition: { 
      duration: timing.micro 
    }
  },
  tap: { 
    scale: 0.95,
    transition: { 
      duration: 0.1 
    }
  },
  selected: {
    scale: 1.05,
    transition: { 
      duration: timing.ui 
    }
  }
}

export const orbPulseRingVariants: Variants = {
  animate: {
    scale: [1, 1.3, 1],
    opacity: [0.6, 0, 0.6],
    transition: {
      duration: 2.5,
      repeat: Infinity,
      ease: "easeOut"
    }
  }
}

// ============================================
// MODAL / SHEET TRANSITIONS
// ============================================
export const modalVariants: Variants = {
  initial: { 
    opacity: 0, 
    scale: 0.95, 
    y: 20 
  },
  animate: { 
    opacity: 1, 
    scale: 1, 
    y: 0,
    transition: {
      duration: timing.ui,
      ease: easing.smooth
    }
  },
  exit: { 
    opacity: 0, 
    scale: 0.95, 
    y: 20,
    transition: {
      duration: timing.micro
    }
  }
}

export const sheetVariants: Variants = {
  initial: { x: "100%" },
  animate: { 
    x: 0,
    transition: {
      duration: timing.ui,
      ease: easing.smooth
    }
  },
  exit: { 
    x: "100%",
    transition: {
      duration: timing.micro
    }
  }
}

export const overlayVariants: Variants = {
  initial: { opacity: 0 },
  animate: { 
    opacity: 1,
    transition: {
      duration: timing.micro
    }
  },
  exit: { 
    opacity: 0,
    transition: {
      duration: timing.micro
    }
  }
}

// ============================================
// PROGRESSIVE REVEAL (AI Thinking Steps)
// ============================================
export const progressiveRevealVariants: Variants = {
  initial: { opacity: 0, y: 10 },
  animate: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: {
      delay: i * 0.15,
      duration: timing.ui,
      ease: easing.smooth
    }
  })
}

export const typewriterVariants: Variants = {
  initial: { opacity: 0 },
  animate: {
    opacity: 1,
    transition: {
      staggerChildren: 0.02
    }
  }
}

// ============================================
// TOOLTIP / POPOVER
// ============================================
export const tooltipVariants: Variants = {
  initial: { 
    opacity: 0, 
    scale: 0.95, 
    y: 5 
  },
  animate: { 
    opacity: 1, 
    scale: 1, 
    y: 0,
    transition: {
      duration: timing.micro,
      ease: easing.snappy
    }
  },
  exit: { 
    opacity: 0, 
    scale: 0.95,
    transition: {
      duration: 0.1
    }
  }
}

// ============================================
// DATA FLOW / SYNC ANIMATIONS
// ============================================
export const dataFlowVariants: Variants = {
  animate: {
    x: ["-100%", "400%"],
    transition: {
      duration: 2,
      repeat: Infinity,
      ease: "linear"
    }
  }
}

export const syncingVariants: Variants = {
  animate: {
    rotate: 360,
    transition: {
      duration: 1,
      repeat: Infinity,
      ease: "linear"
    }
  }
}

// ============================================
// SPRING TRANSITIONS (reusable)
// ============================================
export const springTransition: Transition = {
  type: "spring",
  stiffness: 300,
  damping: 25
}

export const gentleSpringTransition: Transition = {
  type: "spring",
  stiffness: 200,
  damping: 20
}

export const bouncySpringTransition: Transition = {
  type: "spring",
  stiffness: 400,
  damping: 15
}

// ============================================
// UTILITY FUNCTIONS
// ============================================

/**
 * Creates staggered delay for list items
 */
export function getStaggerDelay(index: number, baseDelay = 0.05): number {
  return index * baseDelay
}

/**
 * Creates spring transition with custom values
 */
export function createSpring(stiffness = 300, damping = 25): Transition {
  return { type: "spring", stiffness, damping }
}

/**
 * Creates timed transition
 */
export function createTimed(duration: number, ease = easing.smooth): Transition {
  return { duration, ease }
}
