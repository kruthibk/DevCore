import { createContext, useCallback, useContext, useEffect, useState } from "react";
import {
  fetchAuthMe,
  loginUser,
  logoutUser,
  registerUser,
  STORAGE_KEYS,
} from "../api/client";

const AuthContext = createContext(null);

function normalizeRole(raw) {
  const val = (raw || "").trim().toUpperCase();
  if (val === "ADMIN" || val === "OPERATOR" || val === "VIEWER") {
    return val;
  }
  if (val === "ANALYST") return "VIEWER";
  return "OPERATOR";
}

function readStoredToken() {
  try {
    return localStorage.getItem(STORAGE_KEYS.token) || null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const [token, setToken] = useState(readStoredToken);
  const [user, setUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(() => Boolean(readStoredToken()));
  const [authNotice, setAuthNotice] = useState(null);

  const clearSession = useCallback((notice = null) => {
    try {
      localStorage.removeItem(STORAGE_KEYS.token);
    } catch {
      // Ignore storage failures
    }
    setToken(null);
    setUser(null);
    setAuthLoading(false);
    if (notice) {
      setAuthNotice(notice);
    }
  }, []);

  const loadCurrentUser = useCallback(async () => {
    const activeToken = readStoredToken();
    if (!activeToken) {
      setUser(null);
      setAuthLoading(false);
      return;
    }
    setAuthLoading(true);
    const res = await fetchAuthMe();
    if (res.ok && res.data?.user) {
      setUser(res.data.user);
      setAuthNotice(null);
    } else if (res.statusCode === 401 || res.statusCode === 403) {
      clearSession(res.error || "Session expired or revoked. Please sign in again.");
    }
    setAuthLoading(false);
  }, [clearSession]);

  useEffect(() => {
    loadCurrentUser();
  }, [loadCurrentUser]);

  useEffect(() => {
    const onUnauthorized = (evt) => {
      clearSession(evt?.detail || "Authentication expired or revoked. Please sign in.");
    };
    window.addEventListener("sat_triage:unauthorized", onUnauthorized);
    return () => window.removeEventListener("sat_triage:unauthorized", onUnauthorized);
  }, [clearSession]);

  const login = useCallback(async (username, password) => {
    setAuthNotice(null);
    const res = await loginUser(username, password);
    if (!res.ok || !res.data) {
      return { ok: false, error: res.error || "Invalid credentials" };
    }
    const { access_token: nextToken, user: loggedUser } = res.data;
    try {
      localStorage.setItem(STORAGE_KEYS.token, nextToken);
    } catch {
      // Ignore storage errors
    }
    setToken(nextToken);
    setUser(loggedUser);
    return { ok: true, user: loggedUser };
  }, []);

  const register = useCallback(async (username, email, password) => {
    setAuthNotice(null);
    const res = await registerUser(username, email, password);
    if (!res.ok || !res.data) {
      return { ok: false, error: res.error || "Registration failed" };
    }
    const { access_token: nextToken, user: newUser } = res.data;
    try {
      localStorage.setItem(STORAGE_KEYS.token, nextToken);
    } catch {
      // Ignore storage errors
    }
    setToken(nextToken);
    setUser(newUser);
    return { ok: true, user: newUser };
  }, []);

  const logout = useCallback(async () => {
    if (readStoredToken()) {
      await logoutUser();
    }
    clearSession(null);
  }, [clearSession]);

  const role = user ? normalizeRole(user.role) : null;
  const isAuthenticated = Boolean(token && user);

  const value = {
    token,
    user,
    role,
    username: user?.username || null,
    isAuthenticated,
    authLoading,
    authNotice,
    clearAuthNotice: () => setAuthNotice(null),
    isAdmin: role === "ADMIN",
    isOperator: role === "OPERATOR",
    canOperate: role === "OPERATOR" || role === "ADMIN",
    login,
    register,
    logout,
    refreshProfile: loadCurrentUser,
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
