import { NavLink } from "react-router-dom";
import {
  MessageSquare,
  LayoutDashboard,
  FileText,
  FolderKanban,
  ScrollText,
  ShieldCheck,
  Settings,
  type LucideIcon,
} from "lucide-react";
import { AegisLogo } from "@/components/AegisLogo";
import { useAuth } from "@/auth/AuthContext";
import { cn } from "@/lib/utils";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  adminOnly?: boolean;
}

const GROUPS: { label: string; items: NavItem[] }[] = [
  {
    label: "Workspace",
    items: [
      { to: "/chat", label: "Chat", icon: MessageSquare },
      { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { to: "/documents", label: "Documents", icon: FileText },
      { to: "/projects", label: "Projects", icon: FolderKanban },
    ],
  },
  {
    label: "Governance",
    items: [
      { to: "/audit", label: "Audit log", icon: ScrollText, adminOnly: true },
      { to: "/admin", label: "Administration", icon: ShieldCheck, adminOnly: true },
    ],
  },
  {
    label: "Account",
    items: [{ to: "/settings", label: "Settings", icon: Settings }],
  },
];

function NavRow({ item, onNavigate }: { item: NavItem; onNavigate?: () => void }) {
  const Icon = item.icon;
  return (
    <NavLink
      to={item.to}
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          "group relative flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors duration-150",
          isActive
            ? "bg-accent/12 text-ink"
            : "text-ink-muted hover:bg-surface hover:text-ink",
        )
      }
    >
      {({ isActive }) => (
        <>
          <span
            className={cn(
              "absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-full bg-accent transition-opacity duration-150",
              isActive ? "opacity-100" : "opacity-0",
            )}
            aria-hidden
          />
          <Icon
            className={cn(
              "h-[1.05rem] w-[1.05rem] shrink-0 transition-colors",
              isActive ? "text-accent" : "text-ink-faint group-hover:text-ink-muted",
            )}
          />
          {item.label}
        </>
      )}
    </NavLink>
  );
}

export function Sidebar({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const initial = user?.userId?.charAt(0).toUpperCase() ?? "?";

  return (
    <>
      {/* Mobile backdrop */}
      <div
        className={cn(
          "fixed inset-0 z-30 bg-black/50 backdrop-blur-sm transition-opacity duration-200 lg:hidden",
          open ? "opacity-100" : "pointer-events-none opacity-0",
        )}
        onClick={onClose}
        aria-hidden
      />

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-border bg-surface transition-transform duration-200 ease-out-quart lg:static lg:z-auto lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex h-16 items-center border-b border-border px-5">
          <AegisLogo />
        </div>

        <nav className="flex flex-1 flex-col gap-6 overflow-y-auto px-3 py-5">
          {GROUPS.map((group) => {
            const items = group.items.filter((i) => !i.adminOnly || isAdmin);
            if (items.length === 0) return null;
            return (
              <div key={group.label} className="space-y-1">
                <div className="px-3 pb-1 font-mono text-2xs uppercase tracking-[0.14em] text-ink-faint/70">
                  {group.label}
                </div>
                {items.map((item) => (
                  <NavRow key={item.to} item={item} onNavigate={onClose} />
                ))}
              </div>
            );
          })}
        </nav>

        <div className="border-t border-border p-3">
          <div className="flex items-center gap-3 rounded-md px-2 py-1.5">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent/15 text-[0.8125rem] font-semibold text-accent">
              {initial}
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-[0.8125rem] font-medium text-ink">
                {user?.userId}
              </div>
              <div className="truncate text-2xs capitalize text-ink-faint">
                {user?.role}
              </div>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
