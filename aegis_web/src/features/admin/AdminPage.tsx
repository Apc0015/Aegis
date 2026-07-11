import { useQuery } from "@tanstack/react-query";
import { Users, Plug, FileLock2 } from "lucide-react";
import { getAdminUsers, getConnectors, getAccessRules } from "@/api/endpoints";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/ui/page-header";
import { RoleBadge } from "@/components/RoleBadge";

function PanelHead({
  icon: Icon,
  title,
}: {
  icon: typeof Users;
  title: string;
}) {
  return (
    <div className="flex items-center gap-2 border-b border-border px-5 py-3.5">
      <Icon className="h-4 w-4 text-ink-muted" />
      <span className="text-sm font-medium text-ink">{title}</span>
    </div>
  );
}

export function AdminPage() {
  const users = useQuery({ queryKey: ["admin", "users"], queryFn: getAdminUsers });
  const connectors = useQuery({
    queryKey: ["admin", "connectors"],
    queryFn: getConnectors,
  });
  const rules = useQuery({
    queryKey: ["admin", "access-rules"],
    queryFn: getAccessRules,
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Administration"
        description="Users, connectors, and the access rules that drive the data firewall."
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <PanelHead icon={Users} title="Users" />
          <div className="divide-y divide-border">
            {users.isLoading ? (
              Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="px-5 py-3">
                  <Skeleton className="h-5 w-full" />
                </div>
              ))
            ) : (
              users.data?.map((u) => (
                <div
                  key={u.user_id}
                  className="flex items-center justify-between px-5 py-3 transition-colors hover:bg-surface/40"
                >
                  <div className="flex items-center gap-2.5">
                    <div className="flex h-7 w-7 items-center justify-center rounded-full bg-accent/12 text-2xs font-semibold text-accent">
                      {u.user_id.charAt(0).toUpperCase()}
                    </div>
                    <span className="text-sm text-ink">{u.user_id}</span>
                  </div>
                  <RoleBadge role={u.role} />
                </div>
              ))
            )}
          </div>
        </Card>

        <Card>
          <PanelHead icon={Plug} title="Connectors" />
          <div className="divide-y divide-border">
            {connectors.isLoading ? (
              Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="px-5 py-3">
                  <Skeleton className="h-5 w-full" />
                </div>
              ))
            ) : (
              Object.entries(connectors.data ?? {}).map(([name, configured]) => (
                <div
                  key={name}
                  className="flex items-center justify-between px-5 py-3 transition-colors hover:bg-surface/40"
                >
                  <span className="text-sm capitalize text-ink">{name}</span>
                  <Badge variant={configured ? "success" : "neutral"}>
                    {configured ? "Configured" : "Not configured"}
                  </Badge>
                </div>
              ))
            )}
          </div>
        </Card>
      </div>

      <Card>
        <PanelHead icon={FileLock2} title="Access rules" />
        <div className="p-4">
          {rules.isLoading ? (
            <Skeleton className="h-48 w-full" />
          ) : (
            <pre className="max-h-[28rem] overflow-auto rounded-md border border-border bg-bg/60 p-4 font-mono text-2xs leading-relaxed text-ink-muted">
              {JSON.stringify(rules.data ?? {}, null, 2)}
            </pre>
          )}
        </div>
      </Card>
    </div>
  );
}
