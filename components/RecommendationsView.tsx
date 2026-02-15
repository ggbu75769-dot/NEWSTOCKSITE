"use client";

import LanguageSwitcher from "@/components/LanguageSwitcher";
import SignOutButton from "@/components/SignOutButton";
import ThemeToggle from "@/components/ThemeToggle";
import UserBadge from "@/components/UserBadge";
import { fetchDailyRecommendations } from "@/lib/recommendations/client";
import { getMarketLabelBySymbol, inferCurrencyBySymbol } from "@/lib/recommendations/market";
import { DailyRecommendationResponse } from "@/lib/recommendations/types";
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
const maxReturnTone = (value: number | null) => {
  if (value === null || Number.isNaN(value)) return "text-muted-foreground";
  return value >= 0 ? "text-emerald-600" : "text-rose-500";
};

const DEFAULT_START_DATE = "2026-01-01";

export default function RecommendationsView({ name, email, avatarUrl, isLoggedIn }: RecommendationsViewProps) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language === "en" ? "en" : "ko";
  const [days, setDays] = useState<DailyRecommendationResponse["days"]>([]);
  const [source, setSource] = useState<DailyRecommendationResponse["source"] | null>(null);
  const [selectedDate, setSelectedDate] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const locale = i18n.language === "en" ? "en-US" : "ko-KR";

  useEffect(() => {
    let active = true;
    setLoading(true);

    fetchDailyRecommendations({
      language: lang,
      startDate: DEFAULT_START_DATE,
      limitPerDay: 5,
    })
      .then((payload) => {
        if (!active) return;
        setDays(payload.days);
        setSource(payload.source);
        setSelectedDate((prev) => {
          if (prev && payload.days.some((day) => day.date === prev)) return prev;
          return payload.days[0]?.date ?? "";
        });
        setLoading(false);
      })
      .catch((err) => {
        console.error("[recommendations] failed to fetch daily recommendations", err);
        if (!active) return;
        setDays([]);
        setSource(null);
        setSelectedDate("");
        setLoading(false);
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

  const formatTradingValue = (value: number | null, symbol: string) => {
    if (value === null || Number.isNaN(value)) return "-";
    const currency = inferCurrencyBySymbol(symbol);
    if (currency === "KRW") {
      const eok = Math.round(value / 100_000_000);
      const grouped = new Intl.NumberFormat(locale).format(eok);
      return lang === "en" ? `${grouped} eok` : `${grouped}억`;
    }
    return new Intl.NumberFormat(locale, {
      style: "currency",
      currency,
      maximumFractionDigits: 2,
    }).format(value);
  };
  const formatMaxReturn = (value: number | null) => {
    if (value === null || Number.isNaN(value)) return "-";
    const pct = value * 100;
    const sign = pct >= 0 ? "+" : "";
    return `${sign}${pct.toFixed(2)}%`;
  };
  const formatDate = (isoDate: string) => {
    const date = new Date(`${isoDate}T00:00:00`);
    if (Number.isNaN(date.getTime())) return isoDate;
    return date.toLocaleDateString(locale, {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
  };

  const selectedDay = days.find((day) => day.date === selectedDate) ?? null;
  const rows = selectedDay?.items ?? [];

  return (
    <main className="min-h-screen bg-background text-foreground">
      <div className="mx-auto max-w-[96rem] px-6 py-16">
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
                  href="/dashboard"
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
            {source?.startDate && source?.endDate ? (
              <p className="mt-2 text-xs text-muted-foreground">
                {t("recommendations.rangeLabel")} {source.startDate} ~ {source.endDate}
              </p>
            ) : null}
            {!loading && days.length > 0 ? (
              <div className="mt-4 flex items-center gap-3">
                <label htmlFor="recommendation-date" className="text-sm font-medium text-foreground">
                  {t("recommendations.dateFilterLabel")}
                </label>
                <select
                  id="recommendation-date"
                  value={selectedDate}
                  onChange={(event) => setSelectedDate(event.target.value)}
                  className="rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-primary/30"
                >
                  {days.map((day) => (
                    <option key={day.date} value={day.date}>
                      {formatDate(day.date)}
                    </option>
                  ))}
                </select>
              </div>
            ) : null}

            <div className="mt-6 overflow-x-auto rounded-2xl border border-border bg-card">
              <table className="min-w-full divide-y divide-border text-sm">
                <thead className="bg-background">
                  <tr>
                    <th className="px-4 py-3 text-left font-semibold text-muted-foreground whitespace-nowrap">
                      {t("recommendations.table.date")}
                    </th>
                    <th className="px-4 py-3 text-left font-semibold text-muted-foreground">
                      {t("recommendations.table.rank")}
                    </th>
                    <th className="px-4 py-3 text-left font-semibold text-muted-foreground whitespace-nowrap">
                      {t("recommendations.table.symbol")}
                    </th>
                    <th className="px-4 py-3 text-left font-semibold text-muted-foreground">
                      {t("recommendations.table.price")}
                    </th>
                    <th className="px-4 py-3 text-left font-semibold text-muted-foreground">
                      {t("recommendations.table.tradingValue")}
                    </th>
                    <th className="px-4 py-3 text-left font-semibold text-muted-foreground">
                      {t("recommendations.table.aiScore")}
                    </th>
                    <th className="px-4 py-3 text-left font-semibold text-muted-foreground whitespace-nowrap">
                      {t("recommendations.table.maxReturn")}
                    </th>
                    <th className="px-4 py-3 text-left font-semibold text-muted-foreground">
                      {t("recommendations.table.reasoning")}
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {loading ? (
                    <tr>
                      <td colSpan={8} className="px-4 py-8 text-center text-muted-foreground">
                        {t("recommendations.loading")}
                      </td>
                    </tr>
                  ) : null}
                  {!loading && rows.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="px-4 py-8 text-center text-muted-foreground">
                        {t("recommendations.empty")}
                      </td>
                    </tr>
                  ) : null}
                  {rows.map((item) => {
                    const marketLabel = getMarketLabelBySymbol(item.symbol, lang);
                    return (
                      <tr key={item.id} className="align-top">
                        <td className="px-4 py-4 font-medium text-foreground whitespace-nowrap">{formatDate(item.date)}</td>
                        <td className="px-4 py-4 font-semibold text-foreground">#{item.rank}</td>
                        <td className="px-4 py-4 whitespace-nowrap">
                          <p className="text-base font-semibold text-foreground whitespace-nowrap">{item.name}</p>
                          {marketLabel ? <p className="mt-1 text-xs font-medium text-muted-foreground whitespace-nowrap">{marketLabel}</p> : null}
                        </td>
                        <td className="px-4 py-4 font-medium text-foreground">
                          {formatPrice(item.currentPrice, item.symbol)}
                        </td>
                        <td className="px-4 py-4 font-medium text-foreground">
                          {formatTradingValue(item.tradingValue, item.symbol)}
                        </td>
                        <td className="px-4 py-4">
                          <span
                            className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-semibold ${scoreTone(item.aiScore)}`}
                          >
                            <BrainCircuit className="h-3.5 w-3.5" />
                            {item.aiScore}
                          </span>
                        </td>
                        <td className={`px-4 py-4 font-semibold whitespace-nowrap ${maxReturnTone(item.maxReturnSinceBuy)}`}>
                          {formatMaxReturn(item.maxReturnSinceBuy)}
                          {item.maxReturnPeakDate ? (
                            <span className="ml-1 text-xs text-muted-foreground">({item.maxReturnPeakDate})</span>
                          ) : null}
                        </td>
                        <td className="max-w-xl px-4 py-4 text-muted-foreground">
                          {item.reasoning}
                        </td>
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
