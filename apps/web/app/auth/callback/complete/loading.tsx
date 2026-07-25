import { GravitreThinkingLoader } from "@/components/gravitre/assistant/thinking-loader"

export default function AuthCallbackCompleteLoading() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <GravitreThinkingLoader size={72} title="Completing sign in" />
    </div>
  )
}
