"use client";

import { createClientSupabaseClient } from "@/lib/supabase/client";
import { useTranslation } from "react-i18next";

type SignOutButtonProps = {
  className?: string;
};

export default function SignOutButton({ className }: SignOutButtonProps) {
  const supabase = createClientSupabaseClient();
  const { t } = useTranslation();

  const handleSignOut = async () => {
    await supabase.auth.signOut();
    window.location.href = "/";
  };

  return (
    <button
      onClick={handleSignOut}
      className={
        className ??
        "rounded-full border border-border bg-card px-4 py-2 text-xs font-semibold text-foreground hover:shadow-md"
      }
    >
      {t("nav.signOut")}
    </button>
  );
}
