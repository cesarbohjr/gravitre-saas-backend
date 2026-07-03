import { Loader2 } from "lucide-react"

export default function AuthCallbackCompleteLoading() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <Loader2 className="h-8 w-8 animate-spin text-primary" aria-label="Completing sign in" />
    </div>
  )
}
