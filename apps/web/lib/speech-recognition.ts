/** Browser Web Speech API helpers for voice input. */

export type SpeechRecognitionStatus =
  | "idle"
  | "listening"
  | "unsupported"
  | "permission-denied"
  | "no-speech"
  | "audio-capture"
  | "network"
  | "error"

export type SpeechRecognitionErrorCode =
  | "not-allowed"
  | "no-speech"
  | "audio-capture"
  | "network"
  | "aborted"
  | "service-not-allowed"
  | "bad-grammar"
  | "language-not-supported"
  | "unknown"

export function isSpeechRecognitionSupported(): boolean {
  if (typeof window === "undefined") return false
  return Boolean(getSpeechRecognitionConstructor())
}

export function getSpeechRecognitionConstructor():
  | (new () => SpeechRecognition)
  | undefined {
  if (typeof window === "undefined") return undefined
  const w = window as Window & {
    SpeechRecognition?: new () => SpeechRecognition
    webkitSpeechRecognition?: new () => SpeechRecognition
  }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition
}

/** User-facing copy for common speech recognition failures. */
export function speechRecognitionErrorMessage(code: SpeechRecognitionErrorCode): string {
  switch (code) {
    case "not-allowed":
    case "service-not-allowed":
      return "Microphone access was denied. Enable it in your browser settings to use voice input."
    case "no-speech":
      return "No speech detected. Try speaking closer to your microphone."
    case "audio-capture":
      return "No microphone found. Connect a microphone and try again."
    case "network":
      return "Voice input requires a network connection in this browser."
    case "aborted":
      return ""
    case "language-not-supported":
      return "Your browser does not support speech recognition for this language."
    default:
      return "Voice input failed. Try again or type your message instead."
  }
}

export function mapSpeechRecognitionError(error: string): SpeechRecognitionErrorCode {
  switch (error) {
    case "not-allowed":
    case "service-not-allowed":
    case "no-speech":
    case "audio-capture":
    case "network":
    case "aborted":
    case "bad-grammar":
    case "language-not-supported":
      return error
    default:
      return "unknown"
  }
}
