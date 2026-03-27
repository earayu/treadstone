import { useMemo, useState } from "react"
import * as Dialog from "@radix-ui/react-dialog"
import * as Switch from "@radix-ui/react-switch"
import { Copy, Plus, Search, X, MoreVertical, Trash2 } from "lucide-react"
import { toast } from "sonner"

import {
  useApiKeys,
  useCreateApiKey,
  useDeleteApiKey,
  type ApiKey,
} from "@/api/api-keys"
import { cn } from "@/lib/utils"

function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—"
  try {
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    })
  } catch {
    return iso
  }
}

function isExpired(expiresAt: string | null | undefined): boolean {
  if (!expiresAt) return false
  return new Date(expiresAt).getTime() < Date.now()
}

function ScopeBadges({ keyRow }: { keyRow: ApiKey }) {
  const cp = keyRow.scope.control_plane
  const dpMode = keyRow.scope.data_plane.mode
  const hasData = dpMode !== "none"
  return (
    <div className="flex flex-wrap gap-1">
      {cp && (
        <span className="bg-primary/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-primary">
          Control plane
        </span>
      )}
      {hasData && (
        <span className="bg-primary/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-primary">
          Data plane
        </span>
      )}
      {!cp && !hasData && (
        <span className="text-xs text-muted-foreground">—</span>
      )}
    </div>
  )
}

export function ApiKeysPage() {
  const { data, isLoading } = useApiKeys()
  const createKey = useCreateApiKey()
  const deleteKey = useDeleteApiKey()

  const items = useMemo(() => data?.items ?? [], [data])

  const [filter, setFilter] = useState("")
  const [createOpen, setCreateOpen] = useState(false)
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null)

  const [newName, setNewName] = useState("my-api-key")
  const [expiryDate, setExpiryDate] = useState("")
  const [scopeControl, setScopeControl] = useState(true)
  const [scopeData, setScopeData] = useState(true)

  const [createdSecret, setCreatedSecret] = useState<string | null>(null)

  const filtered = useMemo(() => {
    if (!filter.trim()) return items
    const q = filter.toLowerCase()
    return items.filter(
      (k) =>
        k.name.toLowerCase().includes(q) ||
        k.key_prefix.toLowerCase().includes(q) ||
        k.id.toLowerCase().includes(q),
    )
  }, [items, filter])

  const totalKeys = items.length
  const activeKeys = useMemo(
    () => items.filter((k) => !isExpired(k.expires_at)).length,
    [items],
  )

  function resetCreateForm() {
    setNewName("my-api-key")
    setExpiryDate("")
    setScopeControl(true)
    setScopeData(true)
  }

  async function handleCreate() {
    let expiresIn: number | null = null
    if (expiryDate) {
      const end = new Date(expiryDate).getTime()
      const sec = Math.max(0, Math.floor((end - Date.now()) / 1000))
      expiresIn = sec > 0 ? sec : null
    }

    const body = {
      name: newName.trim() || "default",
      expires_in: expiresIn,
      scope: {
        control_plane: scopeControl,
        data_plane: scopeData
          ? { mode: "all" as const }
          : { mode: "none" as const },
      },
    }

    try {
      const res = await createKey.mutateAsync(body)
      setCreatedSecret(res.key)
      resetCreateForm()
      setCreateOpen(false)
      toast.success("API key created.")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to create key.")
    }
  }

  async function handleDelete(id: string, name: string) {
    if (!window.confirm(`Delete API key “${name}”?`)) return
    try {
      await deleteKey.mutateAsync(id)
      setMenuOpenId(null)
      toast.success("API key deleted.")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to delete key.")
    }
  }

  function copySecret() {
    if (!createdSecret) return
    void navigator.clipboard.writeText(createdSecret)
    toast.success("Copied to clipboard.")
  }

  return (
    <div className="flex flex-col gap-10">
      <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-4xl font-bold tracking-tight text-foreground">API Keys</h1>
          <p className="mt-1 text-base text-muted-foreground">
            Create and revoke keys for the REST API, CLI, and SDKs.
          </p>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="relative">
            <Search className="absolute left-2 top-1/2 size-4 -translate-y-1/2 text-muted-foreground/60" />
            <input
              type="search"
              placeholder="Search keys…"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="h-10 w-full min-w-[200px] border border-border/30 bg-background pl-9 pr-3 text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-1 focus:ring-ring sm:w-64"
            />
          </div>
          <button
            type="button"
            onClick={() => {
              resetCreateForm()
              setCreateOpen(true)
            }}
            className="flex h-10 items-center justify-center gap-2 bg-primary px-5 text-sm font-bold uppercase tracking-wide text-primary-foreground transition-colors hover:bg-primary/90"
          >
            <Plus className="size-4" />
            Create API key
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 border border-border/15 sm:grid-cols-2">
        <div className="border-b border-border/15 bg-card px-6 py-5 sm:border-b-0 sm:border-r">
          <p className="text-[10px] font-bold uppercase tracking-[2px] text-muted-foreground">
            Active keys
          </p>
          <p className="mt-2 text-3xl font-bold tabular-nums text-foreground">{activeKeys}</p>
        </div>
        <div className="bg-card px-6 py-5">
          <p className="text-[10px] font-bold uppercase tracking-[2px] text-muted-foreground">
            Total keys
          </p>
          <p className="mt-2 text-3xl font-bold tabular-nums text-foreground">{totalKeys}</p>
        </div>
      </div>

      <div className="border border-border/15 bg-black">
        <div className="border-b border-border/15 bg-card px-6 py-4">
          <h3 className="text-xs font-bold uppercase tracking-[1.2px] text-muted-foreground">
            Keys
          </h3>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px]">
            <thead>
              <tr className="border-b border-border/15 bg-card">
                {(
                  [
                    ["Name", "w-[16%]"],
                    ["Prefix", "w-[20%]"],
                    ["Scope", "w-[18%]"],
                    ["Created at", "w-[16%]"],
                    ["Expiry", "w-[16%]"],
                    ["Actions", "w-[14%] text-right"],
                  ] as const
                ).map(([label, cls]) => (
                  <th
                    key={label}
                    className={cn(
                      "px-6 py-3 text-left text-[10px] font-bold uppercase tracking-[1px] text-muted-foreground",
                      cls,
                    )}
                  >
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-sm text-muted-foreground">
                    Loading…
                  </td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-sm text-muted-foreground">
                    {filter ? "No keys match your search." : "No API keys yet."}
                  </td>
                </tr>
              ) : (
                filtered.map((row, idx) => (
                  <tr
                    key={row.id}
                    className={cn(
                      "transition-colors hover:bg-card/50",
                      idx > 0 && "border-t border-border/5",
                    )}
                  >
                    <td className="px-6 py-4 text-sm font-medium text-foreground">{row.name}</td>
                    <td className="px-6 py-4 font-mono text-xs text-muted-foreground">
                      {row.key_prefix}
                    </td>
                    <td className="px-6 py-4">
                      <ScopeBadges keyRow={row} />
                    </td>
                    <td className="px-6 py-4 text-xs text-muted-foreground">
                      {formatDateTime(row.created_at)}
                    </td>
                    <td className="px-6 py-4 text-xs">
                      {isExpired(row.expires_at) ? (
                        <span className="font-semibold text-destructive">Expired</span>
                      ) : row.expires_at ? (
                        <span className="text-muted-foreground">{formatDateTime(row.expires_at)}</span>
                      ) : (
                        <span className="text-muted-foreground">Never</span>
                      )}
                    </td>
                    <td className="relative px-6 py-4 text-right">
                      <button
                        type="button"
                        onClick={() => setMenuOpenId((id) => (id === row.id ? null : row.id))}
                        className="inline-flex text-muted-foreground transition-colors hover:text-foreground"
                        aria-label="Actions"
                      >
                        <MoreVertical className="size-4" />
                      </button>
                      {menuOpenId === row.id && (
                        <>
                          <button
                            type="button"
                            className="fixed inset-0 z-10 cursor-default bg-transparent"
                            aria-label="Close menu"
                            onClick={() => setMenuOpenId(null)}
                          />
                          <div className="absolute right-4 top-full z-20 mt-1 min-w-[140px] border border-border/20 bg-card py-1 shadow-lg">
                            <button
                              type="button"
                              onClick={() => void handleDelete(row.id, row.name)}
                              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-destructive hover:bg-destructive/10"
                            >
                              <Trash2 className="size-3.5" />
                              Delete
                            </button>
                          </div>
                        </>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <Dialog.Root open={createOpen} onOpenChange={setCreateOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/70 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
          <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(100vw-2rem,440px)] -translate-x-1/2 -translate-y-1/2 border border-border/20 bg-card p-6 shadow-xl outline-none">
            <div className="flex items-start justify-between gap-4">
              <div>
                <Dialog.Title className="text-lg font-bold text-foreground">Create API key</Dialog.Title>
                <Dialog.Description className="mt-1 text-sm text-muted-foreground">
                  Name your key, set an optional expiry, and choose scopes.
                </Dialog.Description>
              </div>
              <Dialog.Close className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground">
                <X className="size-5" />
              </Dialog.Close>
            </div>

            <div className="mt-6 space-y-4">
              <label className="block">
                <span className="text-xs font-semibold text-muted-foreground">Name</span>
                <input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  className="mt-1.5 w-full border border-border/30 bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                />
              </label>
              <label className="block">
                <span className="text-xs font-semibold text-muted-foreground">Expiry date (optional)</span>
                <input
                  type="datetime-local"
                  value={expiryDate}
                  onChange={(e) => setExpiryDate(e.target.value)}
                  className="mt-1.5 w-full border border-border/30 bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                />
              </label>

              <div className="space-y-3 rounded border border-border/15 bg-background/50 p-4">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium text-foreground">Control plane</p>
                    <p className="text-xs text-muted-foreground">Manage sandboxes, templates, and account APIs.</p>
                  </div>
                  <Switch.Root
                    checked={scopeControl}
                    onCheckedChange={setScopeControl}
                    className="h-6 w-11 shrink-0 rounded-full bg-muted-foreground/30 outline-none data-[state=checked]:bg-primary"
                  >
                    <Switch.Thumb className="block size-5 translate-x-0.5 rounded-full bg-background transition-transform will-change-transform data-[state=checked]:translate-x-[22px]" />
                  </Switch.Root>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium text-foreground">Data plane</p>
                    <p className="text-xs text-muted-foreground">Access sandbox proxies and workloads.</p>
                  </div>
                  <Switch.Root
                    checked={scopeData}
                    onCheckedChange={setScopeData}
                    className="h-6 w-11 shrink-0 rounded-full bg-muted-foreground/30 outline-none data-[state=checked]:bg-primary"
                  >
                    <Switch.Thumb className="block size-5 translate-x-0.5 rounded-full bg-background transition-transform will-change-transform data-[state=checked]:translate-x-[22px]" />
                  </Switch.Root>
                </div>
              </div>
            </div>

            <div className="mt-6 flex justify-end gap-2">
              <Dialog.Close asChild>
                <button
                  type="button"
                  className="border border-border/40 px-4 py-2 text-sm font-semibold text-foreground hover:bg-accent"
                >
                  Cancel
                </button>
              </Dialog.Close>
              <button
                type="button"
                disabled={createKey.isPending || (!scopeControl && !scopeData)}
                onClick={() => void handleCreate()}
                className="bg-primary px-4 py-2 text-sm font-bold text-primary-foreground hover:bg-primary/90 disabled:opacity-40"
              >
                {createKey.isPending ? "Creating…" : "Create"}
              </button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      <Dialog.Root open={!!createdSecret} onOpenChange={(o) => !o && setCreatedSecret(null)}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/70" />
          <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(100vw-2rem,480px)] -translate-x-1/2 -translate-y-1/2 border border-border/20 bg-card p-6 shadow-xl outline-none">
            <Dialog.Title className="text-lg font-bold text-foreground">Save your secret</Dialog.Title>
            <Dialog.Description className="mt-2 text-sm text-warning">
              This is the only time the full key is shown. Store it securely — it cannot be retrieved later.
            </Dialog.Description>
            <div className="mt-4 flex gap-2">
              <code className="min-w-0 flex-1 break-all rounded border border-border/30 bg-background px-3 py-2 font-mono text-xs text-foreground">
                {createdSecret}
              </code>
              <button
                type="button"
                onClick={copySecret}
                className="shrink-0 border border-border/40 px-3 py-2 text-muted-foreground hover:bg-accent hover:text-foreground"
                aria-label="Copy secret"
              >
                <Copy className="size-4" />
              </button>
            </div>
            <button
              type="button"
              onClick={() => setCreatedSecret(null)}
              className="mt-6 w-full bg-primary py-2.5 text-sm font-bold text-primary-foreground hover:bg-primary/90"
            >
              Done
            </button>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  )
}
