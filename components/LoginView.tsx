"use client";

import AuthPanel from "@/components/AuthPanel";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import Link from "next/link";
import { useTranslation } from "react-i18next";

type LoginViewProps = {
  errorKey: string | null;
  nextTarget: string;
};

export default function LoginView({ errorKey, nextTarget }: LoginViewProps) {
  const { t } = useTranslation();

  return (
    <div className="min-h-screen bg-background relative overflow-hidden">
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-primary/5 rounded-full blur-3xl animate-float-slow" />
        <div className="absolute bottom-0 left-0 w-[400px] h-[400px] bg-accent/5 rounded-full blur-3xl animate-float" />
      </div>

      <div className="absolute top-6 right-6 z-20">
        <LanguageSwitcher />
      </div>

      <div className="relative z-10 container mx-auto px-4 py-16">
        <div className="max-w-lg mx-auto">
          <div className="text-center mb-8">
            <p className="text-[11px] uppercase tracking-[0.4em] text-muted-foreground">{t("login.oauthLabel")}</p>
            <h1 className="mt-4 font-display text-3xl sm:text-4xl font-bold text-foreground">{t("login.title")}</h1>
            <p className="mt-3 text-sm text-muted-foreground">{t("login.subtitle")}</p>
          </div>

          {errorKey && (
            <div className="mb-6 rounded-2xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
              {t(errorKey)}
            </div>
          )}

          <AuthPanel next={nextTarget} />

          <div className="mt-4 text-center text-xs text-muted-foreground">
            {t("login.redirectNote", { target: nextTarget })}
          </div>

          <div className="mt-8 text-center">
            <Link href="/" className="text-sm font-semibold text-foreground hover:underline">
              {t("nav.backToHome")}
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
