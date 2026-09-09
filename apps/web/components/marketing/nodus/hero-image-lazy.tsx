"use client"

import dynamic from "next/dynamic"
import { useEffect, useRef, useState } from "react"

const HeroImage = dynamic(
  () => import("./hero-image").then((m) => ({ default: m.HeroImage })),
  { ssr: false },
)

/**
 * Loads the dashboard screenshot only when scrolled into view — no sized
 * placeholder (a full-width aspect box was becoming the LCP element on CI).
 */
export function HeroImageLazy() {
  const hostRef = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const node = hostRef.current
    if (!node) return

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          setVisible(true)
          observer.disconnect()
        }
      },
      { rootMargin: "120px 0px" },
    )
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  return <div ref={hostRef}>{visible ? <HeroImage /> : null}</div>
}
