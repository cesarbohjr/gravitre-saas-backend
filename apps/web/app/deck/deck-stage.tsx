"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import {
  ChevronLeft,
  ChevronRight,
  Maximize2,
  Minimize2,
  NotebookPen,
  X,
} from "lucide-react"

import { DECK_CSS } from "./deck-css"
import { slides } from "./slides-data"

const STAGE_W = 1920
const STAGE_H = 1080

export function DeckStage() {
  const [index, setIndex] = useState(0)
  const [dir, setDir] = useState(1)
  const [scale, setScale] = useState(0)
  const [notesOpen, setNotesOpen] = useState(false)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [chromeVisible, setChromeVisible] = useState(true)
  const hideTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Fit the 1920×1080 stage inside the viewport, leaving a small margin.
  useEffect(() => {
    const compute = () => {
      const margin = window.innerWidth < 720 ? 0 : 0.94
      const fit = window.innerWidth < 720 ? 1 : margin
      setScale(
        Math.min(window.innerWidth / STAGE_W, window.innerHeight / STAGE_H) * fit,
      )
    }
    compute()
    window.addEventListener("resize", compute)
    return () => window.removeEventListener("resize", compute)
  }, [])

  const goNext = useCallback(() => {
    setIndex((p) => {
      if (p >= slides.length - 1) return p
      setDir(1)
      return p + 1
    })
  }, [])

  const goPrev = useCallback(() => {
    setIndex((p) => {
      if (p <= 0) return p
      setDir(-1)
      return p - 1
    })
  }, [])

  const goTo = useCallback(
    (target: number) => {
      setDir(target >= index ? 1 : -1)
      setIndex(Math.min(slides.length - 1, Math.max(0, target)))
    },
    [index],
  )

  const toggleFullscreen = useCallback(() => {
    if (typeof document === "undefined") return
    if (document.fullscreenElement) {
      void document.exitFullscreen?.()
    } else {
      void document.documentElement.requestFullscreen?.()
    }
  }, [])

  // Keyboard navigation.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      switch (e.key) {
        case "ArrowRight":
        case "PageDown":
        case " ":
          e.preventDefault()
          goNext()
          break
        case "ArrowLeft":
        case "PageUp":
          e.preventDefault()
          goPrev()
          break
        case "Home":
          e.preventDefault()
          goTo(0)
          break
        case "End":
          e.preventDefault()
          goTo(slides.length - 1)
          break
        case "n":
        case "N":
          setNotesOpen((o) => !o)
          break
        case "f":
        case "F":
          toggleFullscreen()
          break
        case "Escape":
          setNotesOpen(false)
          break
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [goNext, goPrev, goTo, toggleFullscreen])

  useEffect(() => {
    const onChange = () => setIsFullscreen(Boolean(document.fullscreenElement))
    document.addEventListener("fullscreenchange", onChange)
    return () => document.removeEventListener("fullscreenchange", onChange)
  }, [])

  // Auto-hide the chrome after a moment of inactivity for a clean present view.
  const wake = useCallback(() => {
    setChromeVisible(true)
    if (hideTimer.current) clearTimeout(hideTimer.current)
    hideTimer.current = setTimeout(() => setChromeVisible(false), 2800)
  }, [])

  useEffect(() => {
    wake()
    return () => {
      if (hideTimer.current) clearTimeout(hideTimer.current)
    }
  }, [wake, index])

  const current = slides[index]
  const progress = ((index + 1) / slides.length) * 100

  return (
    <main
      aria-label="Gravitre Seed Deck presentation"
      onMouseMove={wake}
      onClick={wake}
      style={{
        position: "fixed",
        inset: 0,
        overflow: "hidden",
        background:
          "radial-gradient(120% 120% at 50% 0%, #0f2c20 0%, #081712 45%, #050d0a 100%)",
        cursor: chromeVisible ? "default" : "none",
      }}
    >
      <style dangerouslySetInnerHTML={{ __html: DECK_CSS }} />

      {/* Faint dot-grid echo of the gravitre.app surface */}
      <div
        aria-hidden
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage:
            "radial-gradient(rgba(22,163,116,0.10) 1px, transparent 1px)",
          backgroundSize: "34px 34px",
          maskImage:
            "radial-gradient(120% 90% at 50% 40%, #000 30%, transparent 100%)",
          WebkitMaskImage:
            "radial-gradient(120% 90% at 50% 40%, #000 30%, transparent 100%)",
          pointerEvents: "none",
        }}
      />

      {/* Scaled 16:9 stage */}
      {scale > 0 && (
        <div
          style={{
            position: "absolute",
            top: "50%",
            left: "50%",
            width: STAGE_W,
            height: STAGE_H,
            transform: `translate(-50%, -50%) scale(${scale})`,
            transformOrigin: "center center",
          }}
        >
          <div
            key={index}
            className="deck-frame"
            style={
              {
                width: "100%",
                height: "100%",
                borderRadius: 20,
                overflow: "hidden",
                boxShadow:
                  "0 40px 120px -30px rgba(0,0,0,0.7), 0 0 0 1px rgba(22,163,116,0.18)",
                ["--deck-dir" as string]: String(dir),
              } as React.CSSProperties
            }
            dangerouslySetInnerHTML={{ __html: current.html }}
          />
        </div>
      )}

      {/* Edge tap zones (do not block the slide's own links) */}
      <button
        type="button"
        aria-label="Previous slide"
        tabIndex={-1}
        onClick={goPrev}
        disabled={index === 0}
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          bottom: 96,
          width: "12%",
          background: "transparent",
          border: "none",
          outline: "none",
          WebkitTapHighlightColor: "transparent",
          cursor: index === 0 ? "default" : "pointer",
        }}
      />
      <button
        type="button"
        aria-label="Next slide"
        tabIndex={-1}
        onClick={goNext}
        style={{
          position: "absolute",
          right: 0,
          top: 0,
          bottom: 96,
          width: "12%",
          background: "transparent",
          border: "none",
          outline: "none",
          WebkitTapHighlightColor: "transparent",
          cursor: "pointer",
        }}
      />

      {/* Top bar */}
      <header
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "20px 28px",
          opacity: chromeVisible ? 1 : 0,
          transform: chromeVisible ? "translateY(0)" : "translateY(-12px)",
          transition: "opacity .4s ease, transform .4s ease",
          pointerEvents: chromeVisible ? "auto" : "none",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/deck-assets/e7fdc3ca-256f-4b57-96f7-6e86792c52bf.png"
            alt="Gravitre"
            style={{ width: 26, height: 26 }}
          />
          <span
            style={{
              color: "rgba(255,255,255,0.92)",
              fontWeight: 700,
              fontSize: 17,
              letterSpacing: "-0.3px",
            }}
          >
            Gravitre
          </span>
          <span
            style={{
              color: "rgba(94,196,154,0.9)",
              fontSize: 12,
              letterSpacing: "2.5px",
              textTransform: "uppercase",
              fontWeight: 600,
              paddingLeft: 12,
              marginLeft: 4,
              borderLeft: "1px solid rgba(255,255,255,0.16)",
            }}
          >
            Seed Deck
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <ChromeButton
            label="Speaker notes (N)"
            active={notesOpen}
            onClick={() => setNotesOpen((o) => !o)}
          >
            <NotebookPen size={16} />
          </ChromeButton>
          <ChromeButton
            label={isFullscreen ? "Exit fullscreen (F)" : "Fullscreen (F)"}
            onClick={toggleFullscreen}
          >
            {isFullscreen ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
          </ChromeButton>
        </div>
      </header>

      {/* Bottom control pill */}
      <div
        style={{
          position: "absolute",
          bottom: 24,
          left: "50%",
          transform: `translateX(-50%) translateY(${chromeVisible ? 0 : 16}px)`,
          display: "flex",
          alignItems: "center",
          gap: 6,
          padding: "8px 10px",
          borderRadius: 999,
          background: "rgba(8,20,15,0.72)",
          border: "1px solid rgba(255,255,255,0.12)",
          backdropFilter: "blur(12px)",
          WebkitBackdropFilter: "blur(12px)",
          boxShadow: "0 10px 40px -12px rgba(0,0,0,0.7)",
          opacity: chromeVisible ? 1 : 0,
          transition: "opacity .4s ease, transform .4s ease",
          pointerEvents: chromeVisible ? "auto" : "none",
          zIndex: 5,
        }}
      >
        <ChromeButton label="Previous slide" onClick={goPrev} disabled={index === 0}>
          <ChevronLeft size={18} />
        </ChromeButton>
        <div
          style={{
            minWidth: 92,
            textAlign: "center",
            color: "rgba(255,255,255,0.9)",
            fontSize: 13,
            fontVariantNumeric: "tabular-nums",
            letterSpacing: "0.5px",
            userSelect: "none",
          }}
        >
          <span style={{ color: "#5ec49a", fontWeight: 700 }}>{current.screen}</span>
          <span style={{ opacity: 0.5 }}> / {String(slides.length).padStart(2, "0")}</span>
          <div
            style={{
              fontSize: 10,
              letterSpacing: "1.5px",
              textTransform: "uppercase",
              color: "rgba(255,255,255,0.5)",
              marginTop: 1,
            }}
          >
            {current.label}
          </div>
        </div>
        <ChromeButton
          label="Next slide"
          onClick={goNext}
          disabled={index === slides.length - 1}
        >
          <ChevronRight size={18} />
        </ChromeButton>
      </div>

      {/* Progress bar */}
      <div
        aria-hidden
        style={{
          position: "absolute",
          left: 0,
          bottom: 0,
          height: 3,
          width: "100%",
          background: "rgba(255,255,255,0.08)",
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${progress}%`,
            background: "linear-gradient(90deg, #16a374, #5ec49a)",
            transition: "width .5s cubic-bezier(.22,.68,.28,1)",
            boxShadow: "0 0 14px rgba(22,163,116,0.6)",
          }}
        />
      </div>

      {/* Speaker notes drawer */}
      <aside
        aria-label="Speaker notes"
        aria-hidden={!notesOpen}
        style={{
          position: "absolute",
          left: "50%",
          bottom: 92,
          width: "min(900px, 92vw)",
          transform: `translateX(-50%) translateY(${notesOpen ? 0 : 24}px)`,
          opacity: notesOpen ? 1 : 0,
          pointerEvents: notesOpen ? "auto" : "none",
          transition: "opacity .35s ease, transform .35s ease",
          background: "rgba(8,20,15,0.9)",
          border: "1px solid rgba(22,163,116,0.28)",
          borderRadius: 16,
          padding: "22px 26px",
          backdropFilter: "blur(16px)",
          WebkitBackdropFilter: "blur(16px)",
          boxShadow: "0 24px 70px -20px rgba(0,0,0,0.8)",
          zIndex: 6,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 10,
          }}
        >
          <span
            style={{
              fontSize: 11,
              letterSpacing: "2.5px",
              textTransform: "uppercase",
              color: "#5ec49a",
              fontWeight: 700,
            }}
          >
            Speaker notes · {current.label}
          </span>
          <button
            type="button"
            aria-label="Close speaker notes"
            onClick={() => setNotesOpen(false)}
            style={{
              display: "grid",
              placeItems: "center",
              width: 26,
              height: 26,
              borderRadius: 8,
              border: "1px solid rgba(255,255,255,0.14)",
              background: "transparent",
              color: "rgba(255,255,255,0.7)",
              cursor: "pointer",
            }}
          >
            <X size={14} />
          </button>
        </div>
        <p
          style={{
            margin: 0,
            color: "rgba(255,255,255,0.82)",
            fontSize: 15,
            lineHeight: 1.6,
          }}
        >
          {current.notes || "No speaker notes for this slide."}
        </p>
      </aside>
    </main>
  )
}

function ChromeButton({
  children,
  label,
  onClick,
  disabled,
  active,
}: {
  children: React.ReactNode
  label: string
  onClick: () => void
  disabled?: boolean
  active?: boolean
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      disabled={disabled}
      style={{
        display: "grid",
        placeItems: "center",
        width: 38,
        height: 38,
        borderRadius: 10,
        border: "1px solid rgba(255,255,255,0.12)",
        background: active ? "rgba(22,163,116,0.9)" : "rgba(255,255,255,0.04)",
        color: active ? "#04120b" : "rgba(255,255,255,0.85)",
        cursor: disabled ? "default" : "pointer",
        opacity: disabled ? 0.35 : 1,
        transition: "background .2s ease, color .2s ease, opacity .2s ease",
      }}
    >
      {children}
    </button>
  )
}
