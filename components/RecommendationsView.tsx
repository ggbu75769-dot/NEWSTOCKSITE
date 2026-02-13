"use client";

import LanguageSwitcher from "@/components/LanguageSwitcher";
import SignOutButton from "@/components/SignOutButton";
import ThemeToggle from "@/components/ThemeToggle";
import UserBadge from "@/components/UserBadge";
import { fetchRecommendations } from "@/lib/recommendations/client";
import { getMarketLabelBySymbol, inferCurrencyBySymbol } from "@/lib/recommendations/market";
import { StockRecommendation } from "@/lib/recommendations/types";
import { ArrowLeft, BrainCircuit } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

type RecommendationsViewProps = {
  name: string | null;
  email: string | null;
  avatarUrl: string | null;
  isLoggedIn: boolean;
};

const scoreTone = (score: number) => {
  if (score >= 90) return "text-emerald-600 bg-emerald-500/10 border-emerald-500/20";
  if (score >= 80) return "text-primary bg-primary/10 border-primary/20";
  return "text-amber-600 bg-amber-500/10 border-amber-500/20";
};

const fluctuationTone = (value: number) => (value >= 0 ? "text-emerald-600" : "text-rose-500");

export default function RecommendationsView({ name, email, avatarUrl, isLoggedIn }: RecommendationsViewProps) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language === "en" ? "en" : "ko";
  const [rows, setRows] = useState<StockRecommendation[]>([]);
  const locale = i18n.language === "en" ? "en-US" : "ko-KR";

  useEffect(() => {
    let active = true;

    fetchRecommendations({ language: lang })
      .then((items) => {
        if (!active) return;
        setRows(items);
      })
      .catch((err) => {
        console.error("[recommendations] failed to fetch recommendations", err);
        if (!active) return;
        setRows([]);
      });

    return () => {
      active = false;
    };
  }, [lang]);

  const formatPrice = (value: number, symbol: string) => {
    const currency = inferCurrencyBySymbol(symbol);
    return new Intl.NumberFormat(locale, {
      style: "currency",
      currency,
      maximumFractionDigits: currency === "KRW" ? 0 : 2,
    }).format(value);
  };

  const formatFluctuation = (value: number) => {
    const sign = value >= 0 ? "+" : "";
    return `${sign}${value.toFixed(2)}%`;
  };

  return (
    <main className="min-h-screen bg-background text-foreground">
      <div className="mx-auto max-w-7xl px-6 py-16">
        <div className="flex flex-col gap-6 rounded-3xl border border-border bg-card p-10 shadow-[0_24px_80px_rgba(15,23,42,0.12)]">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-4">
              {isLoggedIn ? (
                <UserBadge name={name} email={email} avatarUrl={avatarUrl} />
              ) : (
                <Link
                  href="/"
                  className="inline-flex items-center gap-2 rounded-full border border-border bg-background px-4 py-2 text-sm font-semibold text-foreground hover:shadow-md"
                >
                  <ArrowLeft className="h-4 w-4" />
                  {t("nav.backToHome")}
                </Link>
              )}
              <div className="flex items-center gap-2">
                <LanguageSwitcher />
                <ThemeToggle />
              </div>
            </div>
            <div className="flex items-center gap-3">
              {isLoggedIn ? (
                <>
                  <Link
                    href="/dashboard"
                    className="inline-flex items-center gap-2 rounded-full border border-border bg-background px-4 py-2 text-sm font-semibold text-foreground hover:shadow-md"
                  >
                    <ArrowLeft className="h-4 w-4" />
                    {t("recommendations.backToDashboard")}
                  </Link>
                  <SignOutButton />
                </>
              ) : (
                <Link
                  href="/login?next=/recommendations"
                  className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-4 py-2 text-sm font-semibold text-primary hover:bg-primary/20"
                >
                  {t("nav.signIn")}
                </Link>
              )}
            </div>
          </div>

          <section className="rounded-2xl border border-border bg-background p-6">
            <p className="text-xs uppercase tracking-[0.3em] text-muted-foreground">
              {t("recommendations.kicker")}
            </p>
            <h1 className="mt-2 text-3xl font-semibold text-foreground">{t("recommendations.title")}</h1>
            <p className="mt-2 text-sm text-muted-foreground">{t("recommendations.subtitle")}</p>

            <div className="mt-6 overflow-x-auto rounded-2xl border border-border bg-card">
              <table className="min-w-full divide-y divide-border text-sm">
                <thead className="bg-background">
                  <tr>
                    <th className="px-4 py-3 text-left font-semibold text-muted-foreground">
                      {t("recommendations.table.symbol")}
                    </th>
                    <th className="px-4 py-3 text-left font-semibold text-muted-foreground">
                      {t("recommendations.table.price")}
                    </th>
                    <th className="px-4 py-3 text-left font-semibold text-muted-foreground">
                      {t("recommendations.table.fluctuation")}
                    </th>
                    <th className="px-4 py-3 text-left font-semibold text-muted-foreground">
                      {t("recommendations.table.aiScore")}
                    </th>
                    <th className="px-4 py-3 text-left font-semibold text-muted-foreground">
                      {t("recommendations.table.reasoning")}
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {rows.map((item) => {
                    const marketLabel = getMarketLabelBySymbol(item.symbol, lang);
                    return (
                      <tr key={item.id} className="align-top">
                        <td className="px-4 py-4">
                          <p className="text-base font-semibold text-foreground">{item.name}</p>
                          {marketLabel ? <p className="mt-1 text-xs font-medium text-muted-foreground">{marketLabel}</p> : null}
                        </td>
                        <td className="px-4 py-4 font-medium text-foreground">
                          {formatPrice(item.currentPrice, item.symbol)}
                        </td>
                        <td className={`px-4 py-4 font-semibold ${fluctuationTone(item.fluctuationRate)}`}>
                          {formatFluctuation(item.fluctuationRate)}
                        </td>
                        <td className="px-4 py-4">
                          <span
                            className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-semibold ${scoreTone(item.aiScore)}`}
                          >
                            <BrainCircuit className="h-3.5 w-3.5" />
                            {item.aiScore}
                          </span>
                        </td>
                        <td className="max-w-xl px-4 py-4 text-muted-foreground">{item.reasoning}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}
