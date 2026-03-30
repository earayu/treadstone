import { NavLink } from "react-router"
import {
  Box,
  Key,
  BarChart3,
  Settings,
  ShieldCheck,
  FileText,
  Activity,
  Users,
  LayoutDashboard,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useCurrentUser } from "@/hooks/use-auth"
import { TreadstoneSymbol } from "@/components/brand/logo"

const navItems = [
  { to: "/app", icon: Box, label: "Sandboxes", end: true },
  { to: "/app/api-keys", icon: Key, label: "API Keys" },
  { to: "/app/usage", icon: BarChart3, label: "Usage" },
  { to: "/app/settings", icon: Settings, label: "Settings" },
]

const adminNavItems = [
  { to: "/internal/admin/overview", icon: LayoutDashboard, label: "Overview" },
  { to: "/internal/admin/users", icon: Users, label: "User Management" },
  { to: "/internal/admin/metering", icon: Activity, label: "Admin Metering" },
  { to: "/internal/audit", icon: FileText, label: "Audit Events" },
]

export function Sidebar() {
  const { data: user } = useCurrentUser()
  const isAdmin = user?.role === "admin"

  return (
    <aside className="flex h-screen w-64 shrink-0 flex-col border-r border-sidebar-border bg-sidebar">
      <div className="flex items-center gap-3 px-6 py-6">
        <div className="flex size-8 items-center justify-center bg-primary">
          <TreadstoneSymbol className="size-4 text-primary-foreground" />
        </div>
        <span className="text-xl font-bold tracking-tight text-primary">
          Treadstone
        </span>
      </div>

      <nav className="flex flex-1 flex-col pt-4">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 border-l-2 px-4 py-3 text-sm transition-colors",
                isActive
                  ? "border-primary bg-sidebar-accent font-bold text-primary"
                  : "border-transparent text-muted-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-foreground",
              )
            }
          >
            <item.icon className="size-4 shrink-0" />
            {item.label}
          </NavLink>
        ))}

        {isAdmin && (
          <div className="mt-4">
            <div className="flex items-center gap-2 px-4 py-2">
              <ShieldCheck className="size-3.5 text-muted-foreground/70" />
              <span className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground/70">
                Admin
              </span>
            </div>
            {adminNavItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-3 border-l-2 px-4 py-3 text-sm transition-colors",
                    isActive
                      ? "border-primary bg-sidebar-accent font-bold text-primary"
                      : "border-transparent text-muted-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-foreground",
                  )
                }
              >
                <item.icon className="size-4 shrink-0" />
                {item.label}
              </NavLink>
            ))}
          </div>
        )}
      </nav>
    </aside>
  )
}
