"use client";

import { useTranslation } from "react-i18next";

type SignOutButtonProps = {
  className?: string;
};

export default function SignOutButton({ className }: SignOutButtonProps) {
  const { t } = useTranslation();

  const handleReset = () => {
    sessionStorage.removeItem("market_override");
    window.location.href = "/";
  };

  return (
    <button
      onClick={handleReset}
      className={
        className ??
        "rounded-full border border-border bg-card px-4 py-2 text-xs font-semibold text-foreground hover:shadow-md"
      }
    >
      {t("nav.backToHome")}
    </button>
  );
}
