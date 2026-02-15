"use client";

import LanguageSwitcher from "@/components/LanguageSwitcher";
import ThemeToggle from "@/components/ThemeToggle";
import Link from "next/link";
import { FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";

type ResetPasswordViewProps = {
  token: string;
};

export default function ResetPasswordView({ token }: ResetPasswordViewProps) {
  const { t } = useTranslation();
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const hasToken = token.length > 0;

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage(null);
    setSuccess(false);

    if (!hasToken) {
      setErrorMessage(t("resetPassword.errorInvalidToken"));
      return;
    }

    if (password.length < 8) {
      setErrorMessage(t("resetPassword.errorPasswordTooShort"));
      return;
    }

    if (password !== confirmPassword) {
      setErrorMessage(t("resetPassword.errorPasswordMismatch"));
      return;
    }

    setLoading(true);
    try {
      const response = await fetch("/api/auth/reset-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, password }),
      });

      if (!response.ok) {
        const body = (await response.json().catch(() => ({}))) as { error?: string };
        if (body.error === "INVALID_TOKEN" || body.error === "EXPIRED_TOKEN") {
          setErrorMessage(t("resetPassword.errorInvalidToken"));
        } else if (body.error === "RATE_LIMITED") {
          setErrorMessage(t("resetPassword.errorRateLimited"));
        } else if (body.error === "PASSWORD_TOO_SHORT") {
          setErrorMessage(t("resetPassword.errorPasswordTooShort"));
        } else {
          setErrorMessage(t("resetPassword.errorFailed"));
        }
        return;
      }

      setSuccess(true);
      setPassword("");
      setConfirmPassword("");
    } catch (err) {
      console.error("[reset-password] request failed", err);
      setErrorMessage(t("resetPassword.errorFailed"));
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
              <p className="text-xs uppercase tracking-[0.3em] text-muted-foreground">{t("resetPassword.kicker")}</p>
              <h1 className="mt-2 text-3xl font-semibold text-foreground">{t("resetPassword.title")}</h1>
              <p className="mt-2 text-sm text-muted-foreground">{t("resetPassword.subtitle")}</p>
            </div>
            <div className="flex items-center gap-2">
              <LanguageSwitcher />
              <ThemeToggle />
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-foreground">{t("resetPassword.passwordLabel")}</span>
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="new-password"
                className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm outline-none ring-primary/20 transition focus:ring-4"
                placeholder={t("resetPassword.passwordPlaceholder")}
              />
            </label>

            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-foreground">{t("resetPassword.confirmPasswordLabel")}</span>
              <input
                type="password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                autoComplete="new-password"
                className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm outline-none ring-primary/20 transition focus:ring-4"
                placeholder={t("resetPassword.confirmPasswordPlaceholder")}
              />
            </label>

            <p className="text-xs text-muted-foreground">{t("resetPassword.passwordRule")}</p>

            {errorMessage ? (
              <p className="rounded-xl border border-rose-300/50 bg-rose-500/10 px-3 py-2 text-sm text-rose-600">{errorMessage}</p>
            ) : null}

            {success ? (
              <p className="rounded-xl border border-emerald-300/50 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700">
                {t("resetPassword.success")}
              </p>
            ) : null}

            <button
              type="submit"
              disabled={loading || !hasToken}
              className="w-full rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
            >
              {loading ? t("search.searching") : t("resetPassword.submit")}
            </button>
          </form>

          <div className="mt-6 text-center">
            <Link href="/login" className="text-sm font-semibold text-primary hover:underline">
              {t("resetPassword.backToLogin")}
            </Link>
          </div>
        </section>
      </div>
    </main>
  );
}
