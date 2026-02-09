"use client";

import { createClientSupabaseClient } from "@/lib/supabase/client";
import { Auth } from "@supabase/auth-ui-react";
import { ThemeSupa } from "@supabase/auth-ui-shared";
import { useTranslation } from "react-i18next";

type AuthPanelProps = {
  next?: string;
};

export default function AuthPanel({ next = "/dashboard" }: AuthPanelProps) {
  const supabase = createClientSupabaseClient();
  const { t } = useTranslation();

  const redirectTo =
    typeof window !== "undefined"
      ? `${window.location.origin}/auth/callback?next=${encodeURIComponent(next)}`
      : undefined;

  return (
    <div className="rounded-3xl border border-border bg-card p-8 shadow-[0_24px_80px_rgba(15,23,42,0.12)]">
      <p className="text-sm uppercase tracking-[0.3em] text-muted-foreground">{t("auth.signInPanel")}</p>
      <div className="mt-6">
        <Auth
          supabaseClient={supabase}
          providers={["google"]}
          redirectTo={redirectTo}
          appearance={{
            theme: ThemeSupa,
            variables: {
              default: {
                colors: {
                  brand: "#10b981",
                  brandAccent: "#fb923c",
                },
              },
            },
          }}
          theme="default"
        />
      </div>
    </div>
  );
}
