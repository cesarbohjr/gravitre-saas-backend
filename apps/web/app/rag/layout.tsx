import { AppHeader } from "@/components/app-header";

export default function RagLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col">
      <AppHeader />
      <main className="flex-1 px-6 py-8 md:py-12" role="main">
        <div className="mx-auto max-w-6xl">{children}</div>
      </main>
    </div>
  );
}
