"use client";

import SignOutButton from "@/components/SignOutButton";
import UserBadge from "@/components/UserBadge";
import ThemeToggle from "@/components/ThemeToggle";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import { fetchLatestDailyTopRecommendations } from "@/lib/recommendations/client";
import { getMarketLabelBySymbol } from "@/lib/recommendations/market";
import { StockRecommendation } from "@/lib/recommendations/types";
import { ArrowRight, BrainCircuit, Sparkles } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

type DashboardViewProps = {
  name: string | null;
  email: string | null;
  avatarUrl: string | null;
};

type Market = "KR" | "US";

type MarketInfo = {
  market: Market;
  timeLabel: string;
};

type LatestPriceRow = {
  ticker: string;
  name: string;
  close: number | null;
  change_pct: number | null;
  volume: number | null;
  trade_date: string;
  market: Market;
  currency: string;
};

const getKstInfo = (): MarketInfo => {
  const formatter = new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Seoul",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });

  const parts = formatter.formatToParts(new Date());
  const hourPart = parts.find((part) => part.type === "hour")?.value ?? "00";
  const minutePart = parts.find((part) => part.type === "minute")?.value ?? "00";
  const hour = Number(hourPart);
  const market: Market = hour >= 6 && hour < 16 ? "KR" : "US";

  return {
    market,
    timeLabel: `${hourPart}:${minutePart}`,
  };
};

export default function DashboardView({ name, email, avatarUrl }: DashboardViewProps) {
  const { t, i18n } = useTranslation();
  const [autoMarket, setAutoMarket] = useState<Market>("KR");
  const [kstTime, setKstTime] = useState("00:00");
  const [overrideMarket, setOverrideMarket] = useState<Market | null>(null);
  const [overview, setOverview] = useState<LatestPriceRow[]>([]);
  const [movers, setMovers] = useState<LatestPriceRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [topRecommendations, setTopRecommendations] = useState<StockRecommendation[]>([]);
  const lang = i18n.language === "en" ? "en" : "ko";

  useEffect(() => {
    let active = true;

    fetchLatestDailyTopRecommendations({ language: lang, limit: 3 })
      .then((items) => {
        if (!active) return;
        setTopRecommendations(items);
      })
      .catch((err) => {
        console.error("[dashboard] failed to fetch recommendations", err);
        if (!active) return;
        setTopRecommendations([]);
      });

    return () => {
      active = false;
    };
  }, [lang]);

  useEffect(() => {
    const stored = sessionStorage.getItem("market_override");
    if (stored === "KR" || stored === "US") {
      setOverrideMarket(stored);
    }
  }, []);

  useEffect(() => {
    const update = () => {
      const info = getKstInfo();
      setAutoMarket(info.market);
      setKstTime(info.timeLabel);
    };

    update();
    const interval = setInterval(update, 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  const activeMarket = overrideMarket ?? autoMarket;

  const formatPrice = useCallback(
    (value: number | null, currency: string | null) => {
      if (value === null || Number.isNaN(value)) return "-";
      const resolvedCurrency = currency ?? (activeMarket === "KR" ? "KRW" : "USD");
      const locale = i18n.language === "en" ? "en-US" : "ko-KR";
      return new Intl.NumberFormat(locale, {
        style: "currency",
        currency: resolvedCurrency,
        maximumFractionDigits: resolvedCurrency === "KRW" ? 0 : 2,
      }).format(value);
    },
    [activeMarket, i18n.language]
  );

  const formatChange = useCallback((value: number | null) => {
    if (value === null || Number.isNaN(value)) return "-";
    const sign = value > 0 ? "+" : "";
    return `${sign}${value.toFixed(2)}%`;
  }, []);

  const formatRate = useCallback((value: number) => {
    const sign = value >= 0 ? "+" : "";
    return `${sign}${value.toFixed(2)}%`;
  }, []);

  const scoreTone = useCallback((score: number) => {
    if (score >= 90) return "text-emerald-600 bg-emerald-500/10 border-emerald-500/20";
    if (score >= 80) return "text-primary bg-primary/10 border-primary/20";
    return "text-amber-600 bg-amber-500/10 border-amber-500/20";
  }, []);

  const fetchMarketData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/market?market=${activeMarket}&limit=6`, {
        cache: "no-store",
      });
      const payload = await response.json();
      if (!response.ok) {
        setError(String(payload?.error ?? "Failed to load market data"));
        setOverview([]);
        setMovers([]);
        setLoading(false);
        return;
      }

      const rows = (payload?.items ?? []) as LatestPriceRow[];
      setOverview(rows.slice(0, 2));
      setMovers(rows.slice(2, 6));
      setLastUpdated(rows[0]?.trade_date ?? null);
      setLoading(false);
    } catch {
      setError("Failed to load market data");
      setOverview([]);
      setMovers([]);
      setLoading(false);
    }
  }, [activeMarket]);

  useEffect(() => {
    fetchMarketData();
  }, [fetchMarketData]);

  useEffect(() => {
    const interval = setInterval(fetchMarketData, 60 * 1000);
    return () => clearInterval(interval);
  }, [fetchMarketData]);

  const handleOverride = (market: Market) => {
    setOverrideMarket(market);
    sessionStorage.setItem("market_override", market);
  };

  const clearOverride = () => {
    setOverrideMarket(null);
    sessionStorage.removeItem("market_override");
  };

  return (
    <main className="min-h-screen bg-background text-foreground">
      <div className="mx-auto max-w-6xl px-6 py-16">
        <div className="flex flex-col gap-6 rounded-3xl border border-border bg-card p-10 shadow-[0_24px_80px_rgba(15,23,42,0.12)]">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-4">
              <UserBadge name={name} email={email} avatarUrl={avatarUrl} />
              <div className="flex items-center gap-2">
                <LanguageSwitcher />
                <ThemeToggle />
              </div>
            </div>
            <SignOutButton />
          </div>

          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-muted-foreground">{t("dashboard.title")}</p>
            <h1 className="mt-3 text-3xl font-semibold text-foreground">
              {t("dashboard.welcome", { name: name ?? t("user.fallback") })}
            </h1>
            <p className="mt-3 text-muted-foreground">{t("dashboard.subtitle")}</p>
          </div>

          <div className="rounded-2xl border border-border bg-background p-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div>
                <h2 className="text-lg font-semibold text-foreground">{t("dashboard.marketTitle")}</h2>
                <p className="text-sm text-muted-foreground">{t("dashboard.marketSubtitle")}</p>
                <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                  <span>{t("dashboard.marketNow", { time: kstTime })}</span>
                  {overrideMarket ? (
                    <button
                      onClick={clearOverride}
                      className="rounded-full border border-border bg-card px-2 py-1 text-[10px] font-semibold text-foreground"
                    >
                      {t("dashboard.marketAuto")}
                    </button>
                  ) : null}
                  {lastUpdated ? (
                    <span>{t("dashboard.lastUpdate", { date: lastUpdated })}</span>
                  ) : null}
                </div>
              </div>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => handleOverride("KR")}
                  className={`rounded-full px-4 py-2 text-sm font-semibold border transition-all ${
                    activeMarket === "KR"
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-border bg-card text-foreground"
                  }`}
                >
                  {t("dashboard.marketKorean")}
                </button>
                <button
                  onClick={() => handleOverride("US")}
                  className={`rounded-full px-4 py-2 text-sm font-semibold border transition-all ${
                    activeMarket === "US"
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-border bg-card text-foreground"
                  }`}
                >
                  {t("dashboard.marketUS")}
                </button>
              </div>
            </div>

            <div className="mt-6 grid gap-4 md:grid-cols-2">
              <div className="rounded-2xl border border-border bg-card p-5">
                <p className="text-xs uppercase tracking-[0.3em] text-muted-foreground">{t("dashboard.overview")}</p>
                {loading ? (
                  <p className="mt-4 text-sm text-muted-foreground">{t("dashboard.loading")}</p>
                ) : overview.length === 0 ? (
                  <p className="mt-4 text-sm text-muted-foreground">{t("dashboard.noData")}</p>
                ) : (
                  <div className="mt-4 grid gap-4">
                    {overview.map((item) => (
                      <div key={item.ticker} className="flex items-center justify-between">
                        <div>
                          <p className="text-sm font-semibold text-foreground">{item.name}</p>
                          <p className="text-xs text-muted-foreground">{item.ticker}</p>
                        </div>
                        <div className="text-right">
                          <p className="text-lg font-semibold text-foreground">
                            {formatPrice(item.close, item.currency)}
                          </p>
                          <p
                            className={`text-xs ${
                              item.change_pct !== null && item.change_pct < 0
                                ? "text-rose-500"
                                : "text-emerald-600"
                            }`}
                          >
                            {formatChange(item.change_pct)}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="rounded-2xl border border-border bg-card p-5">
                <p className="text-xs uppercase tracking-[0.3em] text-muted-foreground">{t("dashboard.movers")}</p>
                {loading ? (
                  <p className="mt-4 text-sm text-muted-foreground">{t("dashboard.loading")}</p>
                ) : movers.length === 0 ? (
                  <p className="mt-4 text-sm text-muted-foreground">{t("dashboard.noData")}</p>
                ) : (
                  <div className="mt-4 grid gap-3">
                    {movers.map((item) => (
                      <div key={item.ticker} className="flex items-center justify-between">
                        <div>
                          <p className="text-sm font-semibold text-foreground">{item.name}</p>
                          <p className="text-xs text-muted-foreground">{item.ticker}</p>
                        </div>
                        <div className="text-right">
                          <p className="text-sm font-semibold text-foreground">
                            {formatPrice(item.close, item.currency)}
                          </p>
                          <span
                            className={`text-xs font-semibold ${
                              item.change_pct !== null && item.change_pct < 0
                                ? "text-rose-500"
                                : "text-emerald-600"
                            }`}
                          >
                            {formatChange(item.change_pct)}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {error ? <p className="mt-4 text-xs text-destructive">{error}</p> : null}
          </div>

          <section className="rounded-2xl border border-border bg-background p-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.3em] text-muted-foreground">
                  {t("dashboard.aiTopPicksKicker")}
                </p>
                <h2 className="mt-2 text-xl font-semibold text-foreground">{t("dashboard.aiTopPicksTitle")}</h2>
                <p className="mt-1 text-sm text-muted-foreground">{t("dashboard.aiTopPicksSubtitle")}</p>
              </div>
              <Link
                href="/recommendations"
                className="inline-flex items-center justify-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-5 py-2 text-sm font-semibold text-primary transition hover:bg-primary/20"
              >
                {t("dashboard.viewAllRecommendations")}
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>

            <div className="mt-6 grid gap-4 md:grid-cols-3">
              {topRecommendations.map((item, index) => {
                const marketLabel = getMarketLabelBySymbol(item.symbol, lang);
                return (
                  <article
                    key={item.id}
                    className="card-elevated rounded-2xl p-5"
                    style={{ animationDelay: `${index * 80}ms` }}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-lg font-bold text-foreground">{item.name}</p>
                        {marketLabel ? (
                          <p className="mt-1 text-xs font-medium text-muted-foreground">{marketLabel}</p>
                        ) : null}
                      </div>
                      <span
                        className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-semibold ${scoreTone(item.aiScore)}`}
                      >
                        <BrainCircuit className="h-3.5 w-3.5" />
                        {t("dashboard.aiScoreLabel")} {item.aiScore}
                      </span>
                    </div>

                    <div className="mt-5 flex items-end justify-between">
                      <p className="text-2xl font-semibold text-foreground">
                        {formatPrice(item.currentPrice, activeMarket === "KR" ? "KRW" : "USD")}
                      </p>
                      <p
                        className={`text-sm font-semibold ${
                          item.fluctuationRate >= 0 ? "text-emerald-600" : "text-rose-500"
                        }`}
                      >
                        {formatRate(item.fluctuationRate)}
                      </p>
                    </div>

                    <p className="mt-4 max-h-16 overflow-hidden text-sm text-muted-foreground">{item.reasoning}</p>
                    <div className="mt-4 inline-flex items-center gap-1 text-xs font-semibold text-primary">
                      <Sparkles className="h-3.5 w-3.5" />
                      {t("dashboard.modelSignal")}
                    </div>
                  </article>
                );
              })}
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}
