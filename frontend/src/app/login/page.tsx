"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, setToken } from "@/lib/api";
import { useI18n } from "@/i18n/provider";

export default function LoginPage() {
  const router = useRouter();
  const { t, dir } = useI18n();
  const [email, setEmail] = useState("admin@retnza.local");
  const [password, setPassword] = useState("admin123");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await api<{ access_token: string }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setToken(res.access_token);
      router.push("/dashboard");
    } catch {
      setError(t("login.error"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950" dir={dir}>
      <form
        onSubmit={onSubmit}
        className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900 p-8 shadow-xl"
      >
        <div className="mb-2">
          <h1 className="text-3xl font-bold tracking-tight text-white">{t("login.title")}</h1>
          <p className="mt-1 text-sm text-slate-400">{t("login.subtitle")}</p>
        </div>
        {error && (
          <div className="mb-4 rounded-lg border border-red-800 bg-red-950/50 px-4 py-2 text-sm text-red-400">
            {error}
          </div>
        )}
        <label className="block text-sm font-medium text-slate-300">{t("login.email")}</label>
        <input
          type="email"
          required
          className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2.5 text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder={t("login.emailPlaceholder")}
        />
        <label className="mt-4 block text-sm font-medium text-slate-300">{t("login.password")}</label>
        <input
          type="password"
          required
          className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2.5 text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder={t("login.passwordPlaceholder")}
        />
        <button
          type="submit"
          disabled={loading}
          className="mt-6 w-full rounded-lg bg-indigo-600 py-2.5 font-medium text-white transition-colors hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? t("login.signingIn") : t("login.signIn")}
        </button>
      </form>
    </div>
  );
}
