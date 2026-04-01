import { useState, useMemo } from "react"
import { Link, useNavigate } from "react-router"
import {
  Plus,
  Search,
  ChevronLeft,
  ChevronRight,
  MoreHorizontal,
  Square,
  Play,
  Trash2,
  ExternalLink,
  HardDrive,
} from "lucide-react"
import * as DropdownMenu from "@radix-ui/react-dropdown-menu"
import * as Dialog from "@radix-ui/react-dialog"
import { toast } from "sonner"
import { useSandboxes, useStartSandbox, useStopSandbox, useDeleteSandbox, type Sandbox } from "@/api/sandboxes"
import { cn } from "@/lib/utils"
import { formatMinutes } from "@/lib/format-time"
import { SandboxEndpointsCell } from "@/components/sandbox-endpoints"
import { DOCS_SANDBOX_ENDPOINTS } from "@/lib/sandbox-endpoints-meta"
import { DOC } from "@/lib/console-docs"
import { HelpIcon } from "@/components/ui/help-icon"

const PAGE_SIZE = 8

function formatRelativeTime(dateStr: string): string {
  const now = Date.now()
  const then = new Date(dateStr).getTime()
  const diffMs = now - then
  const mins = Math.floor(diffMs / 60_000)
  if (mins < 1) return "just now"
  if (mins < 60) return `${mins} min${mins === 1 ? "" : "s"} ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`
  const days = Math.floor(hours / 24)
  return `${days} day${days === 1 ? "" : "s"} ago`
}

function StatusDot({ status }: { status: string }) {
  const isReady = status === "ready"
  const isCreating = status === "creating"
  const isActiveLabel = isReady || isCreating
  return (
    <div className="flex items-center gap-2">
      <span
        className={cn(
          "inline-block size-1.5 rounded-full",
          isReady && "bg-primary",
          isCreating && "bg-amber-500",
          !isReady && !isCreating && "bg-muted-foreground/60",
        )}
      />
      <span
        className={cn(
          "text-xs font-medium capitalize",
          isActiveLabel ? "text-foreground" : "text-muted-foreground",
        )}
      >
        {status === "ready" ? "Running" : status}
      </span>
    </div>
  )
}

const TABLE_COLUMNS = [
  {
    key: "id",
    label: "Sandbox",
    className: "w-[14%]",
    help: "APIs use the stable sandbox id. The display name is optional.",
    helpLink: { href: DOC.sandboxLifecycle.keyFields, label: "Key fields" },
  },
  {
    key: "status",
    label: "Status",
    className: "w-[8%]",
    help: `Running: the sandbox is active and accepting connections.
Creating: startup in progress.
Stopped: the sandbox has been paused and is not consuming compute.`,
    helpLink: { href: DOC.sandboxLifecycle.inTheConsole, label: "Sandbox lifecycle" },
  },
  {
    key: "template",
    label: "Template",
    className: "w-[13%]",
    help: "The base image used to create this sandbox. The disk icon indicates persistent storage is enabled — data survives restarts.",
    helpLink: { href: DOC.sandboxLifecycle.keyFields, label: "Key fields" },
  },
  { key: "created_at", label: "Created At", className: "w-[12%]" },
  {
    key: "lifecycle",
    label: "Lifecycle",
    className: "w-[16%]",
    help: `Auto-stop: the sandbox is stopped automatically after this period of inactivity.
Auto-delete: the sandbox is permanently deleted after this duration once stopped.`,
    helpLink: { href: DOC.sandboxLifecycle.inTheConsole, label: "Lifecycle in Console" },
  },
  {
    key: "web_url",
    label: "Endpoints",
    className: "w-[29%]",
    help: `Web: opens the workspace in your browser. MCP: copies a JSON snippet for MCP clients (URL + API key placeholder—replace with a key from Settings → API Keys). Proxy: copy the data-plane base URL for HTTP with your API key.`,
    helpLink: { href: DOCS_SANDBOX_ENDPOINTS, label: "Sandbox endpoints" },
  },
  { key: "actions", label: "", className: "w-[8%]" },
] as const

function DeleteConfirmDialog({
  sandbox,
  open,
  onClose,
}: {
  sandbox: Sandbox
  open: boolean
  onClose: () => void
}) {
  const [input, setInput] = useState("")
  const deleteSandbox = useDeleteSandbox()
  const confirmName = sandbox.name || sandbox.id
  const isCreating = sandbox.status === "creating"

  async function handleDelete() {
    try {
      await deleteSandbox.mutateAsync(sandbox.id)
      toast.success("Sandbox deleted.")
      onClose()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to delete sandbox.")
    }
  }

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(o) => {
        if (!o) {
          setInput("")
          onClose()
        }
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/70 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(100vw-2rem,420px)] -translate-x-1/2 -translate-y-1/2 border border-border/20 bg-card p-6 shadow-xl outline-none data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0">
          <Dialog.Title className="text-base font-bold text-foreground">
            {isCreating ? "Cancel provisioning" : "Delete Sandbox"}
          </Dialog.Title>
          <Dialog.Description className="mt-2 text-sm text-muted-foreground">
            {isCreating
              ? "Provisioning will stop and the sandbox will be permanently removed. Type "
              : "This action is irreversible. Type "}
            <span className="font-mono font-bold text-foreground">{confirmName}</span> to confirm.
          </Dialog.Description>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={confirmName}
            className="mt-4 w-full border border-border/30 bg-background px-3 py-2 font-mono text-sm text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-red-900/60"
          />
          <div className="mt-4 flex justify-end gap-2">
            <Dialog.Close className="border border-border/40 bg-secondary px-4 py-2 text-sm font-semibold text-secondary-foreground transition-colors hover:bg-secondary/80">
              Cancel
            </Dialog.Close>
            <button
              type="button"
              onClick={() => void handleDelete()}
              disabled={input !== confirmName || deleteSandbox.isPending}
              className="border border-red-950/80 bg-red-950/90 px-4 py-2 text-sm font-bold text-red-200/95 transition-colors hover:border-red-900/70 hover:bg-red-900/85 disabled:opacity-40"
            >
              {isCreating ? "Cancel provisioning" : "Delete"}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

function SandboxRowActions({ sandbox }: { sandbox: Sandbox }) {
  const navigate = useNavigate()
  const [deleteOpen, setDeleteOpen] = useState(false)
  const stopSandbox = useStopSandbox()
  const startSandbox = useStartSandbox()

  const isReady = sandbox.status === "ready"
  const isCreating = sandbox.status === "creating"
  const canStart = sandbox.status === "stopped" || sandbox.status === "error"
  const canDelete = isCreating || sandbox.status === "stopped" || sandbox.status === "error"

  async function handleStop() {
    try {
      await stopSandbox.mutateAsync(sandbox.id)
      toast.success("Sandbox stopped.")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to stop sandbox.")
    }
  }

  async function handleStart() {
    try {
      await startSandbox.mutateAsync(sandbox.id)
      toast.success("Starting sandbox…")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to start sandbox.")
    }
  }

  return (
    <>
      <DropdownMenu.Root>
        <DropdownMenu.Trigger asChild>
          <button
            type="button"
            aria-label="Open sandbox actions"
            className="flex size-7 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus:outline-none data-[state=open]:bg-accent data-[state=open]:text-foreground"
          >
            <MoreHorizontal className="size-4" aria-hidden />
          </button>
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content
            align="end"
            sideOffset={4}
            className="z-50 min-w-[160px] border border-border/20 bg-card py-1 shadow-xl"
          >
            <DropdownMenu.Item
              onClick={() => void navigate(`/app/sandboxes/${sandbox.id}`)}
              className="flex cursor-pointer items-center gap-2 px-3 py-2 text-xs text-foreground outline-none hover:bg-accent focus:bg-accent"
            >
              <ExternalLink className="size-3.5 text-muted-foreground" />
              View Details
            </DropdownMenu.Item>

            <DropdownMenu.Separator className="my-1 border-t border-border/15" />

            {isReady && (
              <DropdownMenu.Item
                onClick={() => void handleStop()}
                disabled={stopSandbox.isPending}
                className="flex cursor-pointer items-center gap-2 px-3 py-2 text-xs text-foreground outline-none hover:bg-accent focus:bg-accent disabled:pointer-events-none disabled:opacity-40"
              >
                <Square className="size-3.5 text-muted-foreground" />
                Stop
              </DropdownMenu.Item>
            )}
            {canStart && (
              <DropdownMenu.Item
                onClick={() => void handleStart()}
                disabled={startSandbox.isPending}
                className="flex cursor-pointer items-center gap-2 px-3 py-2 text-xs text-foreground outline-none hover:bg-accent focus:bg-accent disabled:pointer-events-none disabled:opacity-40"
              >
                <Play className="size-3.5 text-muted-foreground" />
                Start
              </DropdownMenu.Item>
            )}

            {canDelete && (
              <>
                {(isReady || canStart) && (
                  <DropdownMenu.Separator className="my-1 border-t border-border/15" />
                )}
                <DropdownMenu.Item
                  onClick={() => setDeleteOpen(true)}
                  className="flex cursor-pointer items-center gap-2 px-3 py-2 text-xs text-destructive outline-none hover:bg-destructive/10 focus:bg-destructive/10"
                >
                  <Trash2 className="size-3.5" />
                  {isCreating ? "Cancel provisioning" : "Delete"}
                </DropdownMenu.Item>
              </>
            )}
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>

      <DeleteConfirmDialog
        sandbox={sandbox}
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
      />
    </>
  )
}

function SandboxTable({ sandboxes }: { sandboxes: Sandbox[] }) {
  const [filter, setFilter] = useState("")
  const [page, setPage] = useState(0)

  const filtered = useMemo(() => {
    if (!filter) return sandboxes
    const q = filter.toLowerCase()
    return sandboxes.filter(
      (s) => s.id.toLowerCase().includes(q) || s.name.toLowerCase().includes(q),
    )
  }, [sandboxes, filter])

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE)
  const pageItems = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)

  return (
    <div className="border border-border/15 bg-black">
      <div className="flex items-center justify-between border-b border-border/15 bg-card px-6 py-4">
        <h3 className="text-xs font-bold uppercase tracking-[1.2px] text-muted-foreground">
          Recent Sandboxes
        </h3>
        <div className="relative">
          <Search className="absolute left-2 top-1/2 size-3 -translate-y-1/2 text-muted-foreground/60" />
          <input
            type="text"
            placeholder="Filter by name or ID..."
            value={filter}
            onChange={(e) => {
              setFilter(e.target.value)
              setPage(0)
            }}
            className="h-8 w-48 bg-background pl-7 pr-3 text-[11px] text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
      </div>

      <table className="w-full table-fixed">
        <colgroup>
          {TABLE_COLUMNS.map((col) => (
            <col key={col.key} className={col.className} />
          ))}
        </colgroup>
        <thead>
          <tr className="border-b border-border/15 bg-card">
            {TABLE_COLUMNS.map((col) => (
              <th
                key={col.key}
                className={cn(
                  "px-6 py-3 text-left text-[10px] font-bold uppercase tracking-[1px] text-muted-foreground",
                  col.className,
                )}
              >
                {"help" in col && col.help ? (
                  <div className="flex items-center gap-1">
                    {col.label}
                    <HelpIcon
                      content={col.help}
                      link={
                        "helpLink" in col
                          ? (col as { helpLink?: { href: string; label?: string } }).helpLink
                          : undefined
                      }
                      side="top"
                    />
                  </div>
                ) : (
                  col.label
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {pageItems.length === 0 ? (
            <tr>
              <td colSpan={7} className="px-6 py-12 text-center text-sm text-muted-foreground">
                {filter ? "No sandboxes match your filter." : "No sandboxes yet."}
              </td>
            </tr>
          ) : (
            pageItems.map((sandbox, idx) => (
              <tr
                key={sandbox.id}
                className={cn(
                  "transition-colors hover:bg-card/50",
                  idx > 0 && "border-t border-border/5",
                )}
              >
                <td className="px-6 py-4">
                  <div className="flex flex-col gap-0.5">
                    <Link
                      to={`/app/sandboxes/${sandbox.id}`}
                      className="font-mono text-xs font-medium text-primary"
                    >
                      {sandbox.name || sandbox.id}
                    </Link>
                    {sandbox.name && (
                      <span className="font-mono text-[10px] text-muted-foreground/50">
                        {sandbox.id}
                      </span>
                    )}
                  </div>
                </td>
                <td className="px-6 py-4">
                  <StatusDot status={sandbox.status} />
                </td>
                <td className="px-6 py-4">
                  <div className="flex flex-col gap-1">
                    <span className="text-xs text-muted-foreground">{sandbox.template}</span>
                    {sandbox.persist ? (
                      <span className="inline-flex items-center gap-1 text-[10px] text-primary/70">
                        <HardDrive className="size-2.5 shrink-0" />
                        {sandbox.storage_size ? sandbox.storage_size.replace("i", "") : "PV"}
                      </span>
                    ) : (
                      <span className="text-[10px] text-muted-foreground/40">No persistent storage</span>
                    )}
                  </div>
                </td>
                <td className="px-6 py-4 text-xs text-muted-foreground">
                  {formatRelativeTime(sandbox.created_at)}
                </td>
                <td className="px-6 py-4">
                  <div className="flex flex-col gap-1.5">
                    <div className="flex items-baseline gap-1.5">
                      <span className="text-xs tabular-nums text-muted-foreground">
                        {formatMinutes(sandbox.auto_stop_interval)}
                      </span>
                      <span className="text-[10px] text-muted-foreground/50">auto-stop</span>
                    </div>
                    <div className="flex items-baseline gap-1.5">
                      <span className="text-xs tabular-nums text-muted-foreground">
                        {sandbox.auto_delete_interval === -1 ? "—" : formatMinutes(sandbox.auto_delete_interval)}
                      </span>
                      <span className="text-[10px] text-muted-foreground/50">auto-del</span>
                    </div>
                  </div>
                </td>
                <td className="min-w-0 max-w-0 px-6 py-4 align-top">
                  <SandboxEndpointsCell sandbox={sandbox} />
                </td>
                <td className="px-4 py-4">
                  <SandboxRowActions sandbox={sandbox} />
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      <div className="flex items-center justify-between border-t border-border/15 bg-card px-6 py-3">
        <span className="text-[10px] uppercase tracking-[1px] text-muted-foreground">
          Showing {pageItems.length} of {filtered.length} sandboxes
        </span>
        <div className="flex gap-1">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="flex size-8 items-center justify-center border border-border/30 text-muted-foreground transition-colors hover:text-foreground disabled:opacity-30"
          >
            <ChevronLeft className="size-3" />
          </button>
          <button
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            className="flex size-8 items-center justify-center border border-border/30 text-muted-foreground transition-colors hover:text-foreground disabled:opacity-30"
          >
            <ChevronRight className="size-3" />
          </button>
        </div>
      </div>
    </div>
  )
}

export function SandboxesPage() {
  const { data: sandboxData, isLoading } = useSandboxes()
  const sandboxes = sandboxData?.items ?? []

  return (
    <div className="flex flex-col gap-10">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-4xl font-bold tracking-tight text-foreground">Sandboxes</h1>
          <p className="mt-1 flex flex-wrap items-center gap-2 text-base text-muted-foreground">
            <span>Create and manage isolated sandbox environments for AI agents.</span>
            <HelpIcon
              content="This table matches the lifecycle and URLs described in the docs: status, auto-stop, and Web / MCP / Proxy endpoints."
              link={{ href: DOC.sandboxLifecycle.inTheConsole, label: "Sandbox lifecycle" }}
              side="right"
            />
          </p>
        </div>
        <Link
          to="/app/sandboxes/new"
          className="flex items-center gap-2 bg-primary px-6 py-2.5 font-bold text-primary-foreground transition-colors hover:bg-primary/90"
        >
          <Plus className="size-4" />
          Create Sandbox
        </Link>
      </div>

      {isLoading ? (
        <div className="border border-border/15 bg-card px-6 py-12 text-center text-sm text-muted-foreground">
          Loading sandboxes…
        </div>
      ) : (
        <SandboxTable sandboxes={sandboxes} />
      )}
    </div>
  )
}
