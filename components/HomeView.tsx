"use client";

import SearchBar from "@/components/SearchBar";
import SignOutButton from "@/components/SignOutButton";
import StockCard from "@/components/StockCard";
import ThemeToggle from "@/components/ThemeToggle";
import UserBadge from "@/components/UserBadge";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import HeroSection from "@/components/HeroSection";
import { fetchRecommendations } from "@/lib/recommendations/client";
import { getMarketLabelBySymbol, inferCurrencyBySymbol } from "@/lib/recommendations/market";
import { StockRecommendation } from "@/lib/recommendations/types";
import { ArrowRight, BrainCircuit, Sparkles } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

export type RankingItem = {
  rank: number;
  win_rate: number;
  avg_return: number;
  confluence_score: number;
  ticker: string;
  name: string;
};

type HomeViewProps = {
  rankings: RankingItem[];
  isLoggedIn: boolean;
  name: string | null;
  avatarUrl: string | null;
  email: string | null;
  todayIso: string;
};

const formatHoldingPeriod = (date: Date, locale: string) => {
  const start = date.toLocaleDateString(locale, { month: "short", day: "numeric" });
  const endDate = new Date(date);
  endDate.setDate(endDate.getDate() + 7);
  const end = endDate.toLocaleDateString(locale, { month: "short", day: "numeric" });
  return `${start} - ${end}`;
};

export default function HomeView({
  rankings,
  isLoggedIn,
  name,
  avatarUrl,
  email,
  todayIso,
}: HomeViewProps) {
  const { t, i18n } = useTranslation();
  const today = new Date(todayIso);
  const locale = i18n.language === "en" ? "en-US" : "ko-KR";
  const insightDate = today.toLocaleDateString(locale, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  const lang = i18n.language === "en" ? "en" : "ko";
  const [topRecommendations, setTopRecommendations] = useState<StockRecommendation[]>([]);

  useEffect(() => {
    let active = true;

    fetchRecommendations({ language: lang, limit: 3 })
      .then((items) => {
        if (!active) return;
        setTopRecommendations(items);
      })
      .catch((err) => {
        console.error("[home] failed to fetch recommendations", err);
        if (!active) return;
        setTopRecommendations([]);
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

  const scoreTone = (score: number) => {
    if (score >= 90) return "text-emerald-600 bg-emerald-500/10 border-emerald-500/20";
    if (score >= 80) return "text-primary bg-primary/10 border-primary/20";
    return "text-amber-600 bg-amber-500/10 border-amber-500/20";
  };

  return (
    <div className="min-h-screen bg-background relative overflow-hidden">
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-primary/5 rounded-full blur-3xl animate-float-slow" />
        <div
          className="absolute bottom-0 left-0 w-[400px] h-[400px] bg-accent/5 rounded-full blur-3xl animate-float"
          style={{ animationDelay: "1s" }}
        />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-primary/3 rounded-full blur-3xl" />
      </div>

      <div className="relative z-10 container mx-auto px-4 py-3 md:py-4">
        <div className="flex items-center justify-between gap-4 mb-3">
          <div className="flex items-center gap-3">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-card shadow-md border border-border">
              <Sparkles className="w-4 h-4 text-accent" />
              <span className="text-sm font-medium text-foreground whitespace-pre-line">{t("home.tagline")}</span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <LanguageSwitcher />
            <ThemeToggle />
            {isLoggedIn ? (
              <div className="flex items-center gap-4">
                <UserBadge name={name} email={email} avatarUrl={avatarUrl} />
                <SignOutButton />
              </div>
            ) : (
              <Link
                href="/dashboard"
                className="rounded-full border border-border bg-card px-5 py-2 text-sm font-medium text-foreground hover:shadow-md"
              >
                {t("nav.signIn")}
              </Link>
            )}
          </div>
        </div>

        <HeroSection />

        <div className="mt-4 mb-5 flex flex-col gap-3 sm:flex-row sm:justify-center">
          {isLoggedIn ? (
            <Link
              href="/dashboard"
              className="rounded-full bg-primary px-6 py-3 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
            >
              {t("home.viewDashboard")}
            </Link>
          ) : (
            <Link
              href="/dashboard"
              className="rounded-full bg-primary px-6 py-3 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
            >
              {t("home.startSignals")}
            </Link>
          )}
          <a
            href="#how-it-works"
            className="rounded-full border border-border px-6 py-3 text-sm font-semibold text-foreground hover:shadow-md"
          >
            {t("home.seeHowItWorks")}
          </a>
        </div>

        <div
          className="text-center mb-4 opacity-0 animate-fade-in"
          style={{ animationDelay: "200ms", animationFillMode: "forwards" }}
        >
          <p className="text-sm sm:text-base font-semibold text-muted-foreground">{insightDate}</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 max-w-4xl mx-auto mb-8">
          {rankings.map((item, index) => (
            <StockCard
              key={item.rank}
              rank={item.rank}
              ticker={item.ticker}
              name={item.name}
              aiScore={item.confluence_score}
              avgReturn={item.avg_return}
              holdingPeriod={formatHoldingPeriod(today, locale)}
              isTop={item.rank === 1}
              delay={250 + index * 120}
              isLoggedIn={isLoggedIn}
            />
          ))}
        </div>

        <section className="mb-8 rounded-3xl border border-border bg-card p-8 shadow-[0_24px_80px_rgba(15,23,42,0.12)]">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-muted-foreground">{t("home.aiTopPicksKicker")}</p>
              <h2 className="mt-2 text-2xl font-semibold text-foreground">{t("home.aiTopPicksTitle")}</h2>
              <p className="mt-1 text-sm text-muted-foreground">{t("home.aiTopPicksSubtitle")}</p>
            </div>
            <Link
              href="/recommendations"
              className="inline-flex items-center justify-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-5 py-2 text-sm font-semibold text-primary transition hover:bg-primary/20"
            >
              {t("home.viewAllRecommendations")}
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-3">
            {topRecommendations.map((item) => {
              const marketLabel = getMarketLabelBySymbol(item.symbol, lang);
              return (
                <article key={item.id} className="card-elevated rounded-2xl p-5">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-lg font-bold text-foreground">{item.name}</p>
                      {marketLabel ? <p className="mt-1 text-xs font-medium text-muted-foreground">{marketLabel}</p> : null}
                    </div>
                    <span
                      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-semibold ${scoreTone(item.aiScore)}`}
                    >
                      <BrainCircuit className="h-3.5 w-3.5" />
                      {t("home.aiScoreLabel")} {item.aiScore}
                    </span>
                  </div>

                  <div className="mt-5 flex items-end justify-between">
                    <p className="text-2xl font-semibold text-foreground">{formatPrice(item.currentPrice, item.symbol)}</p>
                    <p className={`text-sm font-semibold ${item.fluctuationRate >= 0 ? "text-emerald-600" : "text-rose-500"}`}>
                      {formatFluctuation(item.fluctuationRate)}
                    </p>
                  </div>

                  <p className="mt-4 max-h-16 overflow-hidden text-sm text-muted-foreground">{item.reasoning}</p>
                </article>
              );
            })}
          </div>
        </section>

        <SearchBar />

        <section
          id="how-it-works"
          className="mt-16 rounded-3xl border border-border bg-card p-10 shadow-[0_24px_80px_rgba(15,23,42,0.12)]"
        >
          <p className="text-[11px] uppercase tracking-[0.4em] text-muted-foreground">{t("home.howItWorks")}</p>
          <div className="mt-6 grid gap-6 md:grid-cols-3">
            <div className="rounded-2xl border border-border bg-background p-6">
              <p className="text-xs uppercase tracking-[0.3em] text-muted-foreground">
                {t("home.stepLabel", { step: 1 })}
              </p>
              <h3 className="mt-3 text-lg font-semibold">{t("home.step1Title")}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{t("home.step1Body")}</p>
            </div>
            <div className="rounded-2xl border border-border bg-background p-6">
              <p className="text-xs uppercase tracking-[0.3em] text-muted-foreground">
                {t("home.stepLabel", { step: 2 })}
              </p>
              <h3 className="mt-3 text-lg font-semibold">{t("home.step2Title")}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{t("home.step2Body")}</p>
            </div>
            <div className="rounded-2xl border border-border bg-background p-6">
              <p className="text-xs uppercase tracking-[0.3em] text-muted-foreground">
                {t("home.stepLabel", { step: 3 })}
              </p>
              <h3 className="mt-3 text-lg font-semibold">{t("home.step3Title")}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{t("home.step3Body")}</p>
            </div>
          </div>
        </section>

        {!isLoggedIn && (
          <div id="auth-section" className="mt-10 scroll-mt-24">
            <div className="rounded-3xl border border-border bg-card p-10 text-center shadow-[0_24px_80px_rgba(15,23,42,0.12)]">
              <p className="text-[11px] uppercase tracking-[0.4em] text-muted-foreground">{t("home.getFullAccess")}</p>
              <h3 className="mt-4 font-display text-2xl font-semibold text-foreground whitespace-pre-line">
                {t("home.signInToUnlock")}
              </h3>
              <p className="mt-2 text-sm text-muted-foreground whitespace-pre-line">{t("home.googleOnly")}</p>
              <div className="mt-6 flex justify-center">
                <Link
                  href="/dashboard"
                  className="rounded-full bg-primary px-6 py-3 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
                >
                  {t("nav.goToLogin")}
                </Link>
              </div>
            </div>
          </div>
        )}

        <section className="mt-16 rounded-3xl border border-border bg-card p-10 shadow-[0_24px_80px_rgba(15,23,42,0.12)]">
          <p className="text-[11px] uppercase tracking-[0.4em] text-muted-foreground">{t("pricing.kicker")}</p>
          <div className="mt-4 flex flex-col gap-6 md:flex-row md:items-start md:justify-between">
            <div>
              <h3 className="font-display text-2xl font-semibold text-foreground whitespace-pre-line">
                {t("pricing.title")}
              </h3>
              <p className="mt-2 text-sm text-muted-foreground whitespace-pre-line">{t("pricing.subtitle")}</p>
            </div>
            <Link
              href="/dashboard"
              className="rounded-full bg-primary px-6 py-3 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
            >
              {t("pricing.primaryCta")}
            </Link>
          </div>

          <div className="mt-8 grid gap-6 md:grid-cols-3">
            <div className="rounded-2xl border border-border bg-background p-6">
              <p className="text-xs uppercase tracking-[0.3em] text-muted-foreground">{t("pricing.planFree.label")}</p>
              <p className="mt-3 text-3xl font-semibold text-foreground">{t("pricing.planFree.price")}</p>
              <p className="mt-2 text-sm text-muted-foreground">{t("pricing.planFree.desc")}</p>
              <ul className="mt-4 space-y-2 text-sm text-muted-foreground">
                <li>{t("pricing.planFree.b1")}</li>
                <li>{t("pricing.planFree.b2")}</li>
                <li>{t("pricing.planFree.b3")}</li>
              </ul>
            </div>
            <div className="rounded-2xl border border-primary bg-primary/5 p-6 shadow-[0_20px_60px_rgba(16,185,129,0.15)]">
              <p className="text-xs uppercase tracking-[0.3em] text-primary">{t("pricing.planPro.label")}</p>
              <p className="mt-3 text-3xl font-semibold text-foreground">{t("pricing.planPro.price")}</p>
              <p className="mt-2 text-sm text-muted-foreground">{t("pricing.planPro.desc")}</p>
              <ul className="mt-4 space-y-2 text-sm text-muted-foreground">
                <li>{t("pricing.planPro.b1")}</li>
                <li>{t("pricing.planPro.b2")}</li>
                <li>{t("pricing.planPro.b3")}</li>
              </ul>
              <div className="mt-6">
                <Link
                  href="/dashboard"
                  className="inline-flex rounded-full bg-primary px-5 py-2 text-xs font-semibold text-primary-foreground hover:bg-primary/90"
                >
                  {t("pricing.secondaryCta")}
                </Link>
              </div>
            </div>
            <div className="rounded-2xl border border-border bg-background p-6">
              <p className="text-xs uppercase tracking-[0.3em] text-muted-foreground">{t("pricing.planTeam.label")}</p>
              <p className="mt-3 text-3xl font-semibold text-foreground">{t("pricing.planTeam.price")}</p>
              <p className="mt-2 text-sm text-muted-foreground">{t("pricing.planTeam.desc")}</p>
              <ul className="mt-4 space-y-2 text-sm text-muted-foreground">
                <li>{t("pricing.planTeam.b1")}</li>
                <li>{t("pricing.planTeam.b2")}</li>
                <li>{t("pricing.planTeam.b3")}</li>
              </ul>
            </div>
          </div>
        </section>

        <p
          className="text-center text-muted-foreground/60 text-xs mt-12 max-w-md mx-auto opacity-0 animate-fade-in"
          style={{ animationDelay: "700ms", animationFillMode: "forwards" }}
        >
          {t("home.basedOnHistory")}
        </p>
      </div>
    </div>
  );
}
