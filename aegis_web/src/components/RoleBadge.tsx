import { ShieldCheck, UserCog, User } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { UserRole } from "@/api/types";

const CONFIG: Record<
  string,
  {
    label: string;
    icon: typeof User;
    variant: "accent" | "warning" | "neutral";
  }
> = {
  admin: { label: "Admin", icon: ShieldCheck, variant: "warning" },
  manager: { label: "Manager", icon: UserCog, variant: "accent" },
  employee: { label: "Employee", icon: User, variant: "neutral" },
};

export function RoleBadge({ role }: { role: UserRole | string }) {
  const cfg = CONFIG[role] ?? {
    label: role,
    icon: User,
    variant: "neutral" as const,
  };
  const Icon = cfg.icon;
  return (
    <Badge variant={cfg.variant}>
      <Icon className="h-3 w-3" />
      {cfg.label}
    </Badge>
  );
}
