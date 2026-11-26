import { createContext, useCallback, useContext, useState } from "react";
import { loginUser, STORAGE_KEYS } from "../api/client";

const AuthContext = createContext(null);

function normalizeRole(raw) {
  const val = (raw || "").trim().toUpperCase();
  if (val === "ADMIN" || val === "OPERATOR" || val === "VIEWER") {
    return val;
  }
  if (val === "ANALYST") return "VIEWER";
  return "OPERATOR";
}

function readInitialAuth() {
  try {
    const token = localStorage.getItem(STORAGE_KEYS.token) || null;
    const role = normalizeRole(localStorage.getItem(STORAGE_KEYS.role) || "OPERATOR");
    const username =
      localStorage.getItem(STORAGE_KEYS.username) || `demo-${role.toLowerCase()}`;
    return {
      token,
      role,
      username,
      authMode: token ? "bearer" : "demo",
    };
  } catch {
    return {
      token: null,
      role: "OPERATOR",
      username: "demo-operator",
      authMode: "demo",
    };
  }
}

export function AuthProvider({ children }) {
  const [auth, setAuth] = useState(readInitialAuth);

  const switchDemoRole = useCallback((nextRole) => {
    const role = normalizeRole(nextRole);
    const username = `demo-${role.toLowerCase()}`;
    try {
      localStorage.removeItem(STORAGE_KEYS.token);
      localStorage.setItem(STORAGE_KEYS.role, role);
      localStorage.setItem(STORAGE_KEYS.username, username);
    } catch {
      // Ignore storage failures in restricted contexts
    }
    setAuth({ token: null, role, username, authMode: "demo" });
  }, []);

  const login = useCallback(async (username, password) => {
    const res = await loginUser(username, password);
    if (!res.ok || !res.data) {
      return { ok: false, error: res.error || "Login failed" };
    }
    const { access_token: token, user } = res.data;
    const role = normalizeRole(user?.role);
    const resolvedName = user?.username || username;
    try {
      localStorage.setItem(STORAGE_KEYS.token, token);
      localStorage.setItem(STORAGE_KEYS.role, role);
      localStorage.setItem(STORAGE_KEYS.username, resolvedName);
    } catch {
      // Ignore storage errors
    }
    setAuth({ token, role, username: resolvedName, authMode: "bearer" });
    return { ok: true, user };
  }, []);

  const logout = useCallback(() => {
    switchDemoRole("OPERATOR");
  }, [switchDemoRole]);

  const value = {
    ...auth,
    isViewer: auth.role === "VIEWER",
    isOperator: auth.role === "OPERATOR",
    isAdmin: auth.role === "ADMIN",
    canOperate: auth.role === "OPERATOR" || auth.role === "ADMIN",
    switchDemoRole,
    login,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return ctx;
}
