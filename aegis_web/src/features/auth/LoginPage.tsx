import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { ArrowRight, Lock, ShieldCheck, ScrollText } from "lucide-react";
import { useAuth } from "@/auth/AuthContext";
import { ApiError } from "@/api/client";
import { AegisLogo } from "@/components/AegisLogo";
import { ErrorBanner } from "@/components/ErrorBanner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";

const TRUST = [
  { icon: Lock, label: "Role-based access" },
  { icon: ShieldCheck, label: "Data firewall" },
  { icon: ScrollText, label: "Fully audited" },
];

export function LoginPage() {
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const location = useLocation() as { state?: { from?: { pathname: string } } };

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (isAuthenticated) return <Navigate to="/chat" replace />;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(username.trim(), password);
      navigate(location.state?.from?.pathname ?? "/chat", { replace: true });
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 401
          ? "Incorrect username or password."
          : err instanceof ApiError
            ? err.message
            : "Cannot reach the Aegis server.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="w-full max-w-[26rem] animate-fade-up">
        <div className="mb-8 flex justify-center">
          <AegisLogo className="scale-110" />
        </div>

        <div className="relative overflow-hidden rounded-xl border border-border bg-card">
          {/* top accent hairline */}
          <div
            className="h-px w-full bg-gradient-to-r from-transparent via-accent/70 to-transparent"
            aria-hidden
          />
          <div className="p-7">
            <div className="mb-6 space-y-1">
              <h1 className="text-lg font-semibold tracking-tight text-ink">
                Sign in
              </h1>
              <p className="text-[0.8125rem] text-ink-muted">
                Access your private RAG workspace.
              </p>
            </div>

            <form onSubmit={onSubmit} className="space-y-4">
              {error && (
                <ErrorBanner message={error} onDismiss={() => setError(null)} />
              )}
              <div className="space-y-1.5">
                <Label htmlFor="username">Username</Label>
                <Input
                  id="username"
                  autoComplete="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  autoFocus
                  placeholder="you@company"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  placeholder="••••••••"
                />
              </div>
              <Button
                type="submit"
                size="lg"
                className="w-full"
                disabled={loading}
              >
                {loading ? <Spinner /> : null}
                Sign in
                {!loading && <ArrowRight className="h-4 w-4" />}
              </Button>
            </form>
          </div>

          <div className="grid grid-cols-3 divide-x divide-border border-t border-border bg-surface/50">
            {TRUST.map(({ icon: Icon, label }) => (
              <div
                key={label}
                className="flex flex-col items-center gap-1.5 px-2 py-3 text-center"
              >
                <Icon className="h-3.5 w-3.5 text-accent" />
                <span className="text-2xs leading-tight text-ink-faint">
                  {label}
                </span>
              </div>
            ))}
          </div>
        </div>

        <p className="mt-6 text-center font-mono text-2xs uppercase tracking-[0.14em] text-ink-faint/70">
          RAG · Governed · Audited
        </p>
      </div>
    </div>
  );
}
