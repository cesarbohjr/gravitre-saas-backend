import { useCallback, useEffect, useRef, useState } from "react"
import { useStore } from "../store"

export type VoiceState = "checking" | "unavailable" | "idle" | "listening" | "thinking" | "speaking"

export type VoiceTurn = { who: "you" | "agent"; text: string; at: string }

type Options = {
  /** Existing conversation to continue, or null to start one on the first turn. */
  conversationId: string | null
  agentId: string | null
  onConversation?: (id: string) => void
  onTurn?: (turn: VoiceTurn) => void
}

/** Push-to-talk: tap to record, tap again to send; the answer is spoken back. */
export function useVoice({ conversationId, agentId, onConversation, onTurn }: Options) {
  const { api, prefs, toast } = useStore()
  const [state, setState] = useState<VoiceState>("checking")
  const [reason, setReason] = useState<string | null>(null)
  const [muted, setMuted] = useState(false)
  const [turns, setTurns] = useState<VoiceTurn[]>([])
  const recorder = useRef<MediaRecorder | null>(null)
  const chunks = useRef<Blob[]>([])
  const stream = useRef<MediaStream | null>(null)
  const audio = useRef<HTMLAudioElement | null>(null)
  const convRef = useRef<string | null>(conversationId)
  convRef.current = conversationId ?? convRef.current
  const historyRef = useRef<{ role: "user" | "assistant"; text: string }[]>([])
  const stateRef = useRef(state)
  stateRef.current = state

  useEffect(() => {
    let alive = true
    api
      .voiceStatus()
      .then((s) => {
        if (!alive) return
        setReason(s.reason)
        setState(s.enabled ? "idle" : "unavailable")
      })
      .catch(() => alive && (setReason("Voice isn't reachable right now."), setState("unavailable")))
    return () => {
      alive = false
    }
  }, [api])

  const releaseMic = () => {
    stream.current?.getTracks().forEach((t) => t.stop())
    stream.current = null
  }

  const stopAudio = () => {
    if (audio.current) {
      audio.current.pause()
      URL.revokeObjectURL(audio.current.src)
      audio.current = null
    }
  }

  useEffect(
    () => () => {
      recorder.current?.state === "recording" && recorder.current.stop()
      releaseMic()
      stopAudio()
    },
    [],
  )

  const push = useCallback(
    (turn: VoiceTurn) => {
      setTurns((t) => [...t, turn])
      onTurn?.(turn)
    },
    [onTurn],
  )

  const answer = useCallback(
    async (blob: Blob) => {
      setState("thinking")
      try {
        const heard = await api.transcribe(blob, convRef.current)
        if (!heard) {
          setReason("Didn't catch that. Tap the orb and try again.")
          setState("idle")
          return
        }
        push({ who: "you", text: heard, at: new Date().toISOString() })
        if (!convRef.current) {
          const conv = await api.createConversation(heard)
          convRef.current = conv.id
          onConversation?.(conv.id)
        }
        const reply = await api.chat({
          history: historyRef.current,
          message: heard,
          conversationId: convRef.current,
          agentId,
          spoken: true,
        })
        historyRef.current = [...historyRef.current, { role: "user" as const, text: heard }, { role: "assistant" as const, text: reply.text }].slice(-20)
        const said = reply.text || "Done."
        push({ who: "agent", text: said, at: new Date().toISOString() })
        setReason(null)
        setState("speaking")
        const sound = await api.speak(said)
        stopAudio()
        const player = new Audio(URL.createObjectURL(sound))
        audio.current = player
        player.onended = () => {
          stopAudio()
          if (stateRef.current === "speaking") setState("idle")
        }
        await player.play()
      } catch (err) {
        setReason(err instanceof Error ? err.message : "Voice stopped.")
        setState("idle")
      }
    },
    [agentId, api, onConversation, push],
  )

  const start = useCallback(async () => {
    if (muted || stateRef.current === "unavailable" || stateRef.current === "checking" || stateRef.current === "thinking") return
    stopAudio()
    try {
      const media = await navigator.mediaDevices.getUserMedia({
        audio: prefs.micId ? { deviceId: { exact: prefs.micId } } : true,
      })
      stream.current = media
      const type = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"].find((t) => MediaRecorder.isTypeSupported?.(t))
      const rec = new MediaRecorder(media, type ? { mimeType: type } : undefined)
      chunks.current = []
      rec.ondataavailable = (e) => e.data.size && chunks.current.push(e.data)
      rec.onstop = () => {
        releaseMic()
        const blob = new Blob(chunks.current, { type: rec.mimeType || "audio/webm" })
        if (blob.size < 1200) {
          setReason("That was too short. Tap the orb, speak, then tap again.")
          setState("idle")
          return
        }
        void answer(blob)
      }
      recorder.current = rec
      rec.start()
      setReason(null)
      setState("listening")
    } catch {
      releaseMic()
      toast("Gravitre can't use the microphone. Allow it in your system settings.", "error")
      setState("idle")
    }
  }, [answer, muted, prefs.micId, toast])

  const stop = useCallback(() => {
    if (recorder.current?.state === "recording") recorder.current.stop()
  }, [])

  const toggle = useCallback(() => {
    const s = stateRef.current
    if (s === "listening") stop()
    else if (s === "idle" || s === "speaking") void start()
  }, [start, stop])

  const toggleMute = useCallback(() => {
    setMuted((m) => {
      if (!m && recorder.current?.state === "recording") {
        recorder.current.onstop = () => {
          releaseMic()
          setState("idle")
        }
        recorder.current.stop()
      }
      return !m
    })
  }, [])

  const end = useCallback(() => {
    if (recorder.current?.state === "recording") {
      recorder.current.onstop = () => releaseMic()
      recorder.current.stop()
    }
    stopAudio()
    if (stateRef.current !== "unavailable") setState("idle")
  }, [])

  // The push-to-talk shortcut works from any app.
  useEffect(() => {
    const onPtt = () => toggle()
    window.addEventListener("gravitre:ptt", onPtt)
    return () => window.removeEventListener("gravitre:ptt", onPtt)
  }, [toggle])

  return { state, reason, muted, turns, start, stop, toggle, toggleMute, end }
}
