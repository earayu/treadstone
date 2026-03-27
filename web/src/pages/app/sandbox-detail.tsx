import { useParams } from "react-router"

export function SandboxDetailPage() {
  const { id } = useParams<{ id: string }>()
  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight text-foreground">Sandbox Detail</h1>
      <p className="mt-1 font-mono text-sm text-muted-foreground">{id}</p>
      <div className="mt-6 text-sm text-muted-foreground">[Sandbox detail view placeholder]</div>
    </div>
  )
}
