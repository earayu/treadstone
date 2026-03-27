import { NavLink } from "react-router"
import {
  LayoutDashboard,
  Box,
  Key,
  BarChart3,
  Settings,
  Layers,
} from "lucide-react"
import { cn } from "@/lib/utils"

const navItems = [
  { to: "/app", icon: LayoutDashboard, label: "Dashboard", end: true },
  { to: "/app/templates", icon: Layers, label: "Templates" },
  { to: "/app/sandboxes", icon: Box, label: "Sandboxes" },
  { to: "/app/api-keys", icon: Key, label: "API Keys" },
  { to: "/app/usage", icon: BarChart3, label: "Usage" },
  { to: "/app/settings", icon: Settings, label: "Settings" },
]

export function Sidebar() {
  return (
    <aside className="flex h-screen w-56 flex-col border-r border-sidebar-border bg-sidebar">
      <div className="flex h-14 items-center px-4">
        <span className="text-lg font-semibold tracking-tight text-sidebar-foreground">
          Treadstone
        </span>
      </div>

      <nav className="flex-1 space-y-0.5 px-2 py-2">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                isActive
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-foreground",
              )
            }
          >
            <item.icon className="h-4 w-4 shrink-0" />
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
