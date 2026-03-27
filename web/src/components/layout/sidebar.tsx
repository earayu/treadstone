import { NavLink } from "react-router"
import { Box, Key, BarChart3, Settings } from "lucide-react"
import { cn } from "@/lib/utils"

const navItems = [
  { to: "/app", icon: Box, label: "Sandboxes", end: true },
  { to: "/app/api-keys", icon: Key, label: "API Keys" },
  { to: "/app/usage", icon: BarChart3, label: "Usage" },
  { to: "/app/settings", icon: Settings, label: "Settings" },
]

export function Sidebar() {
  return (
    <aside className="flex h-screen w-64 shrink-0 flex-col border-r border-sidebar-border bg-sidebar">
      <div className="flex items-center gap-3 px-6 py-6">
        <div className="flex size-8 items-center justify-center bg-primary">
          <Box className="size-4 text-primary-foreground" />
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
      </nav>
    </aside>
  )
}
