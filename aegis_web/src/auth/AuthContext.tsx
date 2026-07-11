import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  clearToken,
  decodeJwt,
  getStoredToken,
  storeToken,
} from "@/api/client";
import { login as loginRequest } from "@/api/endpoints";
import type { UserRole } from "@/api/types";

interface AuthUser {
  userId: string;
  role: UserRole;
}

interface AuthContextValue {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isReady: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function userFromToken(token: string | null): AuthUser | null {
  if (!token) return null;
  const payload = decodeJwt(token);
  if (!payload?.sub || !payload?.role) return null;
  // Reject an expired token so we don't render an authed shell that 401s.
  if (payload.exp && payload.exp * 1000 < Date.now()) return null;
  return { userId: payload.sub, role: payload.role as UserRole };
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    const restored = userFromToken(getStoredToken());
    if (!restored) clearToken();
    setUser(restored);
    setIsReady(true);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const token = await loginRequest(username, password);
    storeToken(token.access_token);
    setUser({ userId: token.user_id, role: token.user_role });
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAuthenticated: !!user,
      isReady,
      login,
      logout,
    }),
    [user, isReady, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
