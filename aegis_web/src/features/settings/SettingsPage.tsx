import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Cpu, Search } from "lucide-react";
import { getHealth, listModels } from "@/api/endpoints";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Badge, StatusDot } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/ui/page-header";

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between px-5 py-3">
      <span className="text-[0.8125rem] text-ink-muted">{label}</span>
      <span className="font-mono text-[0.8125rem] text-ink">{value}</span>
    </div>
  );
}

export function SettingsPage() {
  const health = useQuery({ queryKey: ["health"], queryFn: getHealth, retry: false });

  const [provider, setProvider] = useState("openrouter");
  const [apiKey, setApiKey] = useState("");
  const [enabled, setEnabled] = useState(false);

  const models = useQuery({
    queryKey: ["models", provider, apiKey],
    queryFn: () => listModels(provider, apiKey),
    enabled,
    retry: false,
  });

  const h = health.data;
  const tone =
    h?.status === "ok"
      ? "success"
      : h?.status === "degraded"
        ? "warning"
        : h?.status === "error"
          ? "danger"
          : "muted";

  return (
    <div className="space-y-6">
      <PageHeader
        title="Settings"
        description="Runtime configuration is set server-side via environment variables. This reflects the live backend."
      />

      <Card>
        <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
          <span className="text-sm font-medium text-ink">Live configuration</span>
          {h && (
            <span className="flex items-center gap-2">
              <StatusDot tone={tone} pulse={tone === "success"} />
              <Badge
                variant={
                  tone === "success"
                    ? "success"
                    : tone === "warning"
                      ? "warning"
                      : "danger"
                }
              >
                {h.status}
              </Badge>
            </span>
          )}
        </div>
        {h ? (
          <div className="divide-y divide-border">
            <Row label="Version" value={h.version} />
            <Row label="LLM provider" value={h.llm_provider} />
            <Row label="LLM model" value={h.llm_model} />
            <Row label="Embedding provider" value={h.embed_provider} />
            <Row
              label="Database"
              value={
                <span className={h.db_connected ? "text-success" : "text-danger"}>
                  {h.db_connected ? "connected" : "offline"}
                </span>
              }
            />
            <Row
              label="Vector store"
              value={
                <span className={h.vector_store_ok ? "text-success" : "text-danger"}>
                  {h.vector_store_ok ? "ok" : "error"}
                </span>
              }
            />
          </div>
        ) : (
          <div className="space-y-px p-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        )}
      </Card>

      <Card>
        <div className="flex items-center gap-2 border-b border-border px-5 py-3.5">
          <Cpu className="h-4 w-4 text-ink-muted" />
          <span className="text-sm font-medium text-ink">
            Browse available models
          </span>
        </div>
        <div className="space-y-3 p-5">
          <div className="flex flex-wrap gap-2">
            <Select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              className="w-44"
            >
              <option value="openrouter">OpenRouter (free)</option>
              <option value="ollama">Ollama (local)</option>
            </Select>
            {provider === "openrouter" && (
              <Input
                placeholder="OpenRouter API key (optional)"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                className="max-w-xs flex-1"
                type="password"
              />
            )}
            <Button
              onClick={() => {
                setEnabled(true);
                models.refetch();
              }}
              disabled={models.isFetching}
            >
              {models.isFetching ? <Spinner /> : <Search className="h-4 w-4" />}
              Fetch
            </Button>
          </div>

          {enabled && (
            <div className="max-h-80 overflow-y-auto rounded-md border border-border">
              {models.isFetching ? (
                <div className="space-y-px p-2">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <Skeleton key={i} className="h-11 w-full" />
                  ))}
                </div>
              ) : models.data && models.data.length > 0 ? (
                <div className="divide-y divide-border">
                  {models.data.map((m) => (
                    <div
                      key={m.id}
                      className="px-4 py-2.5 transition-colors hover:bg-surface/40"
                    >
                      <div className="text-[0.8125rem] text-ink">{m.name}</div>
                      <div className="font-mono text-2xs text-ink-faint">
                        {m.id}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="p-4 text-sm text-ink-faint">
                  No models returned (provider unreachable or no free models).
                </p>
              )}
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
