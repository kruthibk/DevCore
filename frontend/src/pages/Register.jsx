import { useState } from "react";
import { Loader2, ShieldCheck, UserPlus } from "lucide-react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Register() {
  const { isAuthenticated, register } = useAuth();
  const navigate = useNavigate();

  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (username.trim().length < 3) {
      setError("Username must be at least 3 characters.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setBusy(true);
    setError(null);
    const res = await register(username.trim(), email.trim(), password);
    setBusy(false);

    if (res.ok) {
      navigate("/", { replace: true });
    } else {
      setError(res.error || "Registration failed.");
    }
  };

  return (
    <div className="min-h-[75vh] flex items-center justify-center p-4">
      <div className="w-full max-w-md rounded-xl border border-slate-800 bg-[#090f1e] p-6 space-y-5 shadow-2xl">
        <div className="flex items-center gap-3 border-b border-slate-800 pb-4">
          <div className="w-10 h-10 rounded-lg border border-cyan-500/30 bg-cyan-500/10 flex items-center justify-center text-cyan-400 shrink-0">
            <UserPlus className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-slate-100">
              Register Operator Account
            </h2>
            <p className="text-[11px] font-mono text-slate-400">
              Self-registered accounts receive OPERATOR role automatically
            </p>
          </div>
        </div>

        {error && (
          <div className="rounded border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3.5">
          <div>
            <label
              htmlFor="reg-username"
              className="block text-[10px] font-mono uppercase tracking-wider text-slate-400 mb-1"
            >
              Username
            </label>
            <input
              id="reg-username"
              type="text"
              required
              minLength={3}
              maxLength={50}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="e.g. flight_ops_01"
              className="w-full rounded border border-slate-700 bg-[#050913] px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:outline-none focus:border-cyan-500"
            />
          </div>

          <div>
            <label
              htmlFor="reg-email"
              className="block text-[10px] font-mono uppercase tracking-wider text-slate-400 mb-1"
            >
              Email Address
            </label>
            <input
              id="reg-email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="operator@devcore.space"
              className="w-full rounded border border-slate-700 bg-[#050913] px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:outline-none focus:border-cyan-500"
            />
          </div>

          <div>
            <label
              htmlFor="reg-password"
              className="block text-[10px] font-mono uppercase tracking-wider text-slate-400 mb-1"
            >
              Password (min 8 characters)
            </label>
            <input
              id="reg-password"
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Create strong password"
              className="w-full rounded border border-slate-700 bg-[#050913] px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:outline-none focus:border-cyan-500"
            />
          </div>

          <div>
            <label
              htmlFor="reg-confirm"
              className="block text-[10px] font-mono uppercase tracking-wider text-slate-400 mb-1"
            >
              Confirm Password
            </label>
            <input
              id="reg-confirm"
              type="password"
              required
              minLength={8}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Re-enter password"
              className="w-full rounded border border-slate-700 bg-[#050913] px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:outline-none focus:border-cyan-500"
            />
          </div>

          <button
            type="submit"
            disabled={busy}
            className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded border border-cyan-500/50 bg-cyan-500/20 hover:bg-cyan-500/30 text-xs font-mono font-semibold text-cyan-100 disabled:opacity-50"
          >
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <UserPlus className="w-4 h-4" />}
            <span>{busy ? "Creating Account..." : "Register Operator"}</span>
          </button>
        </form>

        <div className="pt-3 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
          <span className="flex items-center gap-1.5 text-[11px] font-mono text-slate-500">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span>Role: OPERATOR</span>
          </span>
          <Link to="/login" className="text-cyan-400 hover:text-cyan-300 font-mono">
            Already registered? Sign In →
          </Link>
        </div>
      </div>
    </div>
  );
}
