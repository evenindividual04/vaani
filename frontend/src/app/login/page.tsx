"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await login(username, password);
      router.replace("/");
    } catch (err: any) {
      setError(err.message ?? "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0A0A0A]">
      <div
        className="w-full max-w-sm rounded-xl p-6"
        style={{ background: "rgba(12,16,23,0.8)", border: "1px solid rgba(255,255,255,0.06)" }}
      >
        <div className="mb-6">
          <div className="text-xs font-mono uppercase tracking-[0.2em]" style={{ color: "#4A5568" }}>
            Vaani
          </div>
          <h1 className="text-xl font-bold mt-2" style={{ color: "#F0F4F8" }}>
            Sign in
          </h1>
          <p className="text-xs font-mono mt-1" style={{ color: "#4A5568" }}>
            Use your admin credentials to continue.
          </p>
        </div>

        <form className="space-y-4" onSubmit={handleSubmit}>
          <div className="space-y-1.5">
            <label className="text-[10px] font-mono uppercase tracking-wider" style={{ color: "#4A5568" }}>
              Username
            </label>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="input-dark w-full"
              placeholder="admin"
              autoComplete="username"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-[10px] font-mono uppercase tracking-wider" style={{ color: "#4A5568" }}>
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input-dark w-full"
              placeholder="••••••••"
              autoComplete="current-password"
            />
          </div>

          {error && (
            <div
              className="px-3 py-2 rounded text-[10px] font-mono"
              style={{ background: "rgba(255,69,69,0.1)", color: "#FF4545", border: "1px solid rgba(255,69,69,0.2)" }}
            >
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="btn-teal w-full font-bold shadow-glow-teal"
            style={{ padding: "10px 16px" }}
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}
