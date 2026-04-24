import { IdentitySurface } from "@/components/identity-surface";
export default function HomePage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight text-foreground">
          Gravitre Operator Console
        </h1>
        <p className="text-sm text-muted-foreground">
          Enterprise AI control plane for workflows, approvals, and operators.
        </p>
      </div>
      <section aria-labelledby="identity-heading">
        <h2 id="identity-heading" className="sr-only">
          Identity
        </h2>
        <IdentitySurface />
      </section>
    </div>
  );
}
