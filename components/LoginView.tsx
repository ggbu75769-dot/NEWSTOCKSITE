"use client";

import LanguageSwitcher from "@/components/LanguageSwitcher";
import ThemeToggle from "@/components/ThemeToggle";
import { ArrowRight, LockKeyhole, UserPlus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { signIn } from "next-auth/react";
import { FormEvent, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

type LoginViewProps = {
  callbackUrl: string;
};

type AuthMode = "signin" | "signup";

export default function LoginView({ callbackUrl }: LoginViewProps) {
  const { t } = useTranslation();
  const router = useRouter();
  const [mode, setMode] = useState<AuthMode>("signin");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loadingCredentials, setLoadingCredentials] = useState(false);
  const [loadingGoogle, setLoadingGoogle] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const isSignup = mode === "signup";
  const isLoading = loadingCredentials || loadingGoogle;

  const submitLabel = useMemo(
    () => (isSignup ? t("login.submitSignUp") : t("login.submitSignIn")),
    [isSignup, t]
  );

  const translateRegisterError = (errorCode?: string) => {
    switch (errorCode) {
      case "NAME_REQUIRED":
        return t("login.errorNameRequired");
      case "EMAIL_INVALID":
        return t("login.errorEmailInvalid");
      case "PASSWORD_TOO_SHORT":
        return t("login.errorPasswordTooShort");
      case "EMAIL_EXISTS":
        return t("login.errorEmailExists");
      case "RATE_LIMITED":
        return t("login.errorRateLimited");
      default:
        return t("login.errorRegisterFailed");
    }
  };

  const handleGoogleSignIn = async () => {
    try {
      setErrorMessage(null);
      setLoadingGoogle(true);
      await signIn("google", { callbackUrl });
    } catch (err) {
      console.error("[login] google sign-in failed", err);
      setErrorMessage(t("login.errorGoogleSignInFailed"));
      setLoadingGoogle(false);
    }
  };

  const handleCredentialSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage(null);

    const normalizedEmail = email.trim().toLowerCase();

    if (!normalizedEmail) {
      setErrorMessage(t("login.errorEmailRequired"));
      return;
    }

    if (password.length < 8) {
      setErrorMessage(t("login.errorPasswordTooShort"));
      return;
    }

    setLoadingCredentials(true);

    try {
      if (isSignup) {
        if (!name.trim()) {
          setErrorMessage(t("login.errorNameRequired"));
          return;
        }

        if (password !== confirmPassword) {
          setErrorMessage(t("login.errorPasswordMismatch"));
          return;
        }

        const registerResponse = await fetch("/api/auth/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: name.trim(),
            email: normalizedEmail,
            password,
          }),
        });

        if (!registerResponse.ok) {
          const body = (await registerResponse.json().catch(() => ({}))) as { error?: string };
          setErrorMessage(translateRegisterError(body.error));
          return;
        }
      }

      const result = await signIn("credentials", {
        email: normalizedEmail,
        password,
        callbackUrl,
        redirect: false,
      });

      if (result?.error) {
        setErrorMessage(t("login.errorInvalidCredentials"));
        return;
      }

      router.push(result?.url ?? callbackUrl);
      router.refresh();
    } catch (err) {
      console.error("[login] credentials auth failed", err);
      setErrorMessage(t("login.errorDefault"));
    } finally {
      setLoadingCredentials(false);
    }
  };

  return (
    <main className="min-h-screen bg-background text-foreground">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-20 left-1/2 h-72 w-72 -translate-x-1/2 rounded-full bg-primary/10 blur-3xl" />
        <div className="absolute bottom-0 right-0 h-64 w-64 rounded-full bg-accent/10 blur-3xl" />
      </div>

      <div className="relative mx-auto flex min-h-screen max-w-3xl items-center px-6 py-12">
        <section className="w-full rounded-3xl border border-border bg-card p-8 shadow-[0_24px_80px_rgba(15,23,42,0.12)] md:p-10">
          <div className="mb-8 flex items-center justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-muted-foreground">{t("auth.signInPanel")}</p>
              <h1 className="mt-2 text-3xl font-semibold text-foreground">{t("login.title")}</h1>
              <p className="mt-2 text-sm text-muted-foreground">{t("login.subtitle")}</p>
            </div>

            <LanguageSwitcher />
            <ThemeToggle />
          </div>

          <div className="grid grid-cols-2 gap-2 rounded-2xl bg-muted p-1">
            <button
              type="button"
              onClick={() => {
                setMode("signin");
                setErrorMessage(null);
              }}
              className={`rounded-xl px-4 py-2.5 text-sm font-semibold transition ${
                mode === "signin" ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <span className="inline-flex items-center gap-2">
                <LockKeyhole className="h-4 w-4" />
                {t("login.tabSignIn")}
              </span>
            </button>
            <button
              type="button"
              onClick={() => {
                setMode("signup");
                setErrorMessage(null);
              }}
              className={`rounded-xl px-4 py-2.5 text-sm font-semibold transition ${
                mode === "signup" ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <span className="inline-flex items-center gap-2">
                <UserPlus className="h-4 w-4" />
                {t("login.tabSignUp")}
              </span>
            </button>
          </div>

          <form onSubmit={handleCredentialSubmit} className="mt-6 space-y-4">
            {isSignup ? (
              <label className="block">
                <span className="mb-1.5 block text-sm font-medium text-foreground">{t("login.nameLabel")}</span>
                <input
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  autoComplete="name"
                  className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm outline-none ring-primary/20 transition focus:ring-4"
                  placeholder={t("login.namePlaceholder")}
                />
              </label>
            ) : null}

            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-foreground">{t("login.emailLabel")}</span>
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                autoComplete="email"
                className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm outline-none ring-primary/20 transition focus:ring-4"
                placeholder={t("login.emailPlaceholder")}
              />
            </label>

            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-foreground">{t("login.passwordLabel")}</span>
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete={isSignup ? "new-password" : "current-password"}
                className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm outline-none ring-primary/20 transition focus:ring-4"
                placeholder={t("login.passwordPlaceholder")}
              />
            </label>

            {!isSignup ? (
              <div className="flex justify-end">
                <Link href="/forgot-password" className="text-xs font-semibold text-primary hover:underline">
                  {t("login.forgotPassword")}
                </Link>
              </div>
            ) : null}

            {isSignup ? (
              <label className="block">
                <span className="mb-1.5 block text-sm font-medium text-foreground">{t("login.confirmPasswordLabel")}</span>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  autoComplete="new-password"
                  className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm outline-none ring-primary/20 transition focus:ring-4"
                  placeholder={t("login.confirmPasswordPlaceholder")}
                />
              </label>
            ) : null}

            <p className="text-xs text-muted-foreground">{t("login.passwordRule")}</p>

            {errorMessage ? (
              <p className="rounded-xl border border-rose-300/50 bg-rose-500/10 px-3 py-2 text-sm text-rose-600">{errorMessage}</p>
            ) : null}

            <button
              type="submit"
              disabled={isLoading}
              className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
            >
              {loadingCredentials ? t("search.searching") : submitLabel}
              <ArrowRight className="h-4 w-4" />
            </button>
          </form>

          <div className="my-6 flex items-center gap-3">
            <div className="h-px flex-1 bg-border" />
            <span className="text-xs uppercase tracking-[0.2em] text-muted-foreground">{t("login.orContinue")}</span>
            <div className="h-px flex-1 bg-border" />
          </div>

          <button
            onClick={handleGoogleSignIn}
            disabled={isLoading}
            className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm font-semibold text-foreground hover:bg-muted disabled:opacity-60"
          >
            {loadingGoogle ? `${t("search.searching")}` : t("login.oauthLabel")}
          </button>
        </section>
      </div>
    </main>
  );
}
