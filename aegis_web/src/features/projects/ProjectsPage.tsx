import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FolderKanban, Plus, Database } from "lucide-react";
import { createProject, listProjects } from "@/api/endpoints";
import { ApiError } from "@/api/client";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { ErrorBanner } from "@/components/ErrorBanner";
import { titleize } from "@/lib/utils";

export function ProjectsPage() {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const projects = useQuery({ queryKey: ["projects"], queryFn: listProjects });

  const create = useMutation({
    mutationFn: (n: string) => createProject(n),
    onSuccess: () => {
      setName("");
      setError(null);
      qc.invalidateQueries({ queryKey: ["projects"] });
    },
    onError: (e) =>
      setError(e instanceof ApiError ? e.message : "Could not create project"),
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Projects"
        description="Each project is an isolated FAISS + BM25 retrieval index."
      />

      <Card className="p-4">
        {error && (
          <div className="mb-3">
            <ErrorBanner message={error} onDismiss={() => setError(null)} />
          </div>
        )}
        <form
          className="flex flex-col gap-2 sm:flex-row"
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim()) create.mutate(name.trim());
          }}
        >
          <Input
            placeholder="New project name…"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="flex-1"
          />
          <Button type="submit" disabled={!name.trim() || create.isPending}>
            {create.isPending ? <Spinner /> : <Plus className="h-4 w-4" />}
            Create project
          </Button>
        </form>
      </Card>

      {projects.isLoading ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-[4.5rem] w-full" />
          ))}
        </div>
      ) : projects.data && projects.data.length > 0 ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {projects.data.map((p) => (
            <Card
              key={p.project_id}
              interactive
              className="flex items-center gap-3 p-4"
            >
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-border bg-elevated text-accent">
                <FolderKanban className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <div className="truncate text-sm font-medium text-ink">
                  {p.project_name || titleize(p.project_id)}
                </div>
                <div className="mt-0.5 flex items-center gap-1 font-mono text-2xs text-ink-faint">
                  <Database className="h-3 w-3" />
                  <span className="truncate">{p.collection_name}</span>
                </div>
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={FolderKanban}
          title="No projects yet"
          description="Create your first project above, then upload documents to index them."
        />
      )}
    </div>
  );
}
