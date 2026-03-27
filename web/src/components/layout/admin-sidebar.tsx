import { NavLink } from "react-router"
import { cn } from "@/lib/utils"

const adminNavItems = [
  { to: "/internal/admin/metering", label: "Admin Metering" },
  { to: "/internal/audit", label: "Audit Events" },
]

export function AdminSidebar() {
  return (
    <aside className="flex h-screen w-64 shrink-0 flex-col border-r border-sidebar-border bg-sidebar">
      <div className="flex items-center gap-3 px-6 py-6">
        <div className="flex size-8 items-center justify-center rounded-md bg-primary">
          <span className="text-base font-bold text-primary-foreground">T</span>
        </div>
        <div className="flex flex-col">
          <span className="text-sm font-semibold text-primary">Treadstone</span>
          <span className="text-[11px] text-muted-foreground">Admin Console</span>
        </div>
      </div>

      <nav className="flex flex-1 flex-col pt-4">
        {adminNavItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 px-5 py-3 text-[13px] transition-colors",
                isActive
                  ? "bg-sidebar-accent font-medium text-foreground"
                  : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-foreground",
              )
            }
          >
            {({ isActive }) => (
              <>
                <span
                  className={cn(
                    "inline-block size-1.5 shrink-0 rounded-full",
                    isActive ? "bg-primary" : "bg-muted-foreground/50",
                  )}
                />
                {item.label}
              </>
            )}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
