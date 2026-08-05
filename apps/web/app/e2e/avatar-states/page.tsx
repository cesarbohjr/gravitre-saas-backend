/**
 * TEMPORARY verification harness for the assistant chat avatar states.
 * Renders idle / thinking / speaking side by side with the real theme tokens.
 * Delete once the avatar has been visually signed off.
 */
import { GravitreChatAvatar } from "@/components/gravitre/assistant/gravitre-chat-avatar"

export default function Page() {
  return (
    <main className="flex min-h-screen flex-col gap-8 bg-background p-10">
      {(["idle", "thinking", "speaking"] as const).map((state) => (
        <div key={state} className="flex items-center gap-4">
          <GravitreChatAvatar state={state} />
          <span className="font-mono text-sm text-foreground" data-testid={`label-${state}`}>
            {state}
          </span>
        </div>
      ))}
      {/* Side-by-side with a stand-in for the user avatar, to check equal mass. */}
      <div className="mt-4 flex items-center gap-4">
        <GravitreChatAvatar state="idle" />
        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-secondary text-xs font-semibold text-secondary-foreground">
          SC
        </div>
        <span className="font-mono text-sm text-foreground">vs user avatar (36px)</span>
      </div>
    </main>
  )
}
