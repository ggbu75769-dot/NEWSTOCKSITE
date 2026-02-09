"use client";

import { useEffect } from "react";
import { useTranslation } from "react-i18next";

type LanguageSwitcherProps = {
  className?: string;
};

export default function LanguageSwitcher({ className }: LanguageSwitcherProps) {
  const { i18n, t } = useTranslation();

  useEffect(() => {
    if (typeof document !== "undefined") {
      document.documentElement.lang = i18n.language;
    }
  }, [i18n.language]);

  return (
    <label className={className ?? "inline-flex items-center gap-2 text-xs font-semibold text-foreground"}>
      <span className="text-muted-foreground">{t("language.label")}</span>
      <select
        value={i18n.language}
        onChange={(event) => {
          const nextLang = event.target.value;
          i18n.changeLanguage(nextLang);
          localStorage.setItem("lang", nextLang);
        }}
        className="rounded-full border border-border bg-card px-3 py-2 text-xs font-semibold text-foreground"
      >
        <option value="ko">{t("language.korean")}</option>
        <option value="en">{t("language.english")}</option>
      </select>
    </label>
  );
}
