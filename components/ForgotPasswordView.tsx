"use client";

import LanguageSwitcher from "@/components/LanguageSwitcher";
import ThemeToggle from "@/components/ThemeToggle";
import Link from "next/link";
import { FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";

export default function ForgotPasswordView() {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [debugResetUrl, setDebugResetUrl] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage(null);
    setSuccess(false);
    setDebugResetUrl(null);

    const normalizedEmail = email.trim().toLowerCase();
    if (!normalizedEmail) {
      setErrorMessage(t("forgotPassword.errorEmailRequired"));
      return;
    }

    setLoading(true);
    try {
      const response = await fetch("/api/auth/forgot-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: normalizedEmail }),
      });

      if (!response.ok) {
        const body = (await response.json().catch(() => ({}))) as { error?: string };
        if (body.error === "RATE_LIMITED") {
          setErrorMessage(t("forgotPassword.errorRateLimited"));
        } else {
          setErrorMessage(t("forgotPassword.errorFailed"));
        }
        return;
      }

      const body = (await response.json().catch(() => ({}))) as { debugResetUrl?: string | null };
      setDebugResetUrl(body.debugResetUrl ?? null);
      setSuccess(true);
    } catch (err) {
      console.error("[forgot-password] request failed", err);
      setErrorMessage(t("forgotPassword.errorFailed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-background text-foreground">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-20 left-1/2 h-72 w-72 -translate-x-1/2 rounded-full bg-primary/10 blur-3xl" />
      </div>

      <div className="relative mx-auto flex min-h-screen max-w-2xl items-center px-6 py-12">
        <section className="w-full rounded-3xl border border-border bg-card p-8 shadow-[0_24px_80px_rgba(15,23,42,0.12)] md:p-10">
          <div className="mb-8 flex items-center justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-muted-foreground">{t("forgotPassword.kicker")}</p>
              <h1 className="mt-2 text-3xl font-semibold text-foreground">{t("forgotPassword.title")}</h1>
              <p className="mt-2 text-sm text-muted-foreground">{t("forgotPassword.subtitle")}</p>
            </div>
            <div className="flex items-center gap-2">
              <LanguageSwitcher />
              <ThemeToggle />
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-foreground">{t("forgotPassword.emailLabel")}</span>
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                autoComplete="email"
                className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm outline-none ring-primary/20 transition focus:ring-4"
                placeholder={t("forgotPassword.emailPlaceholder")}
              />
            </label>

            {errorMessage ? (
              <p className="rounded-xl border border-rose-300/50 bg-rose-500/10 px-3 py-2 text-sm text-rose-600">{errorMessage}</p>
            ) : null}

            {success ? (
              <div className="rounded-xl border border-emerald-300/50 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700">
                <p>{t("forgotPassword.success")}</p>
                {debugResetUrl ? (
                  <p className="mt-2">
                    <a href={debugResetUrl} className="font-semibold underline">
                      {t("forgotPassword.debugLink")}
                    </a>
                  </p>
                ) : null}
              </div>
            ) : null}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
            >
              {loading ? t("search.searching") : t("forgotPassword.submit")}
            </button>
          </form>

          <div className="mt-6 text-center">
            <Link href="/login" className="text-sm font-semibold text-primary hover:underline">
              {t("forgotPassword.backToLogin")}
            </Link>
          </div>
        </section>
      </div>
    </main>
  );
}
