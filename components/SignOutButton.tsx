"use client";

import { signOut } from "next-auth/react";
import { useTranslation } from "react-i18next";

type SignOutButtonProps = {
  className?: string;
};

export default function SignOutButton({ className }: SignOutButtonProps) {
  const { t } = useTranslation();

  const handleReset = async () => {
    sessionStorage.removeItem("market_override");
    await signOut({ callbackUrl: "/" });
  };

  return (
    <button
      onClick={handleReset}
      className={
        className ??
        "rounded-full border border-border bg-card px-4 py-2 text-xs font-semibold text-foreground hover:shadow-md"
      }
    >
      {t("nav.signOut")}
    </button>
  );
}
