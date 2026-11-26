import { useState } from "react";
import { AlertTriangle, KeyRound, Loader2, Satellite, ShieldCheck } from "lucide-react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const { isAuthenticated, authNotice, clearAuthNotice, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const redirectTo = location.state?.from || "/";

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  if (isAuthenticated) {
    return <Navigate to={redirectTo} replace />;
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username.trim() || !password) {
      setError("Enter both username and password.");
      return;
    }
    setBusy(true);
    setError(null);
    clearAuthNotice();
    const res = await login(username.trim(), password);
    setBusy(false);
    if (res.ok) {
      navigate(redirectTo, { replace: true });
    } else {
      setError(res.error || "Authentication failed.");
    }
  };

  return (
    <div className="min-h-[75vh] flex items-center justify-center p-4">
      <div className="w-full max-w-md rounded-xl border border-slate-800 bg-[#090f1e] p-6 space-y-5 shadow-2xl">
        <div className="flex items-center gap-3 border-b border-slate-800 pb-4">
          <div className="w-10 h-10 rounded-lg border border-cyan-500/30 bg-cyan-500/10 flex items-center justify-center text-cyan-400 shrink-0">
            <Satellite className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-slate-100">
              SAT-TRIAGE Operator Sign In
            </h2>
            <p className="text-[11px] font-mono text-slate-400">
              Authenticated JWT session required for Verification Wall &amp; Triage
            </p>
          </div>
        </div>

        {authNotice && (
          <div className="rounded border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-200 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
            <span>{authNotice}</span>
          </div>
        )}

        {error && (
          <div className="rounded border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="login-username"
              className="block text-[10px] font-mono uppercase tracking-wider text-slate-400 mb-1"
            >
              Username
            </label>
            <input
              id="login-username"
              type="text"
              autoComplete="username"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter your operator or admin username"
              className="w-full rounded border border-slate-700 bg-[#050913] px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:outline-none focus:border-cyan-500"
            />
          </div>

          <div>
            <label
              htmlFor="login-password"
              className="block text-[10px] font-mono uppercase tracking-wider text-slate-400 mb-1"
            >
              Password
            </label>
            <input
              id="login-password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter password"
              className="w-full rounded border border-slate-700 bg-[#050913] px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:outline-none focus:border-cyan-500"
            />
          </div>

          <button
            type="submit"
            disabled={busy}
            className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded border border-cyan-500/50 bg-cyan-500/20 hover:bg-cyan-500/30 text-xs font-mono font-semibold text-cyan-100 disabled:opacity-50"
          >
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <KeyRound className="w-4 h-4" />}
            <span>{busy ? "Authenticating..." : "Sign In"}</span>
          </button>
        </form>

        <div className="pt-3 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
          <span className="flex items-center gap-1.5 text-[11px] font-mono text-slate-500">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span>Bcrypt + Revocable JWT</span>
          </span>
          <Link to="/register" className="text-cyan-400 hover:text-cyan-300 font-mono">
            Create Operator Account →
          </Link>
        </div>
      </div>
    </div>
  );
}
