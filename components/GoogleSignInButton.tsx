"use client";

import { createClientSupabaseClient } from "@/lib/supabase/client";
import { useTranslation } from "react-i18next";

type GoogleSignInButtonProps = {
  label?: string;
  className?: string;
  next?: string;
};

export default function GoogleSignInButton({
  label,
  className,
  next,
}: GoogleSignInButtonProps) {
  const supabase = createClientSupabaseClient();
  const { t } = useTranslation();
  const resolvedLabel = label ?? t("auth.signInWithGoogle");

  const handleSignIn = async () => {
    try {
      const redirectTo = next
        ? `${window.location.origin}/auth/callback?next=${encodeURIComponent(next)}`
        : `${window.location.origin}/auth/callback`;
      const { error } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: {
          redirectTo,
        },
      });
      if (error) {
        console.error("[auth] Google sign-in failed", error);
        window.location.href = "/login?error=google_sign_in_failed";
      }
    } catch (err) {
      console.error("[auth] Google sign-in exception", err);
      window.location.href = "/login?error=google_sign_in_failed";
    }
  };

  return (
    <button
      onClick={handleSignIn}
      className={
        className ??
        "rounded-full border border-border bg-card px-5 py-2 text-sm font-medium text-foreground hover:shadow-md"
      }
    >
      {resolvedLabel}
    </button>
  );
}
