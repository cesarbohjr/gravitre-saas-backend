import { Skeleton } from "@/components/ui/skeleton"

export default function WelcomeLoading() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 px-4">
      <Skeleton className="h-2 w-full max-w-md rounded-full" />
      <Skeleton className="h-64 w-full max-w-2xl rounded-2xl" />
      <Skeleton className="h-10 w-40 rounded-lg" />
    </div>
  )
}
