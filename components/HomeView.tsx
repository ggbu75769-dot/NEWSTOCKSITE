"use client";

import SearchBar from "@/components/SearchBar";
import SignOutButton from "@/components/SignOutButton";
import StockCard from "@/components/StockCard";
import ThemeToggle from "@/components/ThemeToggle";
import UserBadge from "@/components/UserBadge";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import { Sparkles, TrendingUp } from "lucide-react";
import Link from "next/link";
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

const formatDate = (date: Date, locale: string) =>
  date.toLocaleDateString(locale, {
    month: "short",
    day: "numeric",
  });

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
  const top = rankings[0];
  const heroName = isLoggedIn ? top?.name ?? t("home.mysteryStock") : t("home.mysteryStock");

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

      <div className="relative z-10 container mx-auto px-4 py-12 md:py-16">
        <div className="flex items-center justify-between gap-4 mb-6">
          <div className="flex items-center gap-3">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-card shadow-md border border-border">
              <Sparkles className="w-4 h-4 text-accent" />
              <span className="text-sm font-medium text-foreground">{t("home.tagline")}</span>
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
                href="/login?next=/dashboard"
                className="rounded-full border border-border bg-card px-5 py-2 text-sm font-medium text-foreground hover:shadow-md"
              >
                {t("nav.signIn")}
              </Link>
            )}
          </div>
        </div>

        <div
          className="text-center mb-10 opacity-0 animate-fade-in"
          style={{ animationDelay: "100ms", animationFillMode: "forwards" }}
        >
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-accent/10 text-accent font-semibold text-sm mb-6 animate-bounce-soft">
            <span>{formatDate(today, locale)}</span>
          </div>

          <h1 className="font-display text-4xl sm:text-5xl md:text-6xl font-bold text-foreground leading-tight mb-4">
            <span className="text-gradient-gain">{t("home.heroPrefix", { name: heroName })}</span> {t("home.heroRise")}
            <br />
            <span className="inline-flex items-center gap-2">
              <span className="text-gradient-fire text-5xl sm:text-6xl md:text-7xl">
                {t("home.heroScore", { score: "9/10" })}
              </span>
              <span className="text-muted-foreground text-lg sm:text-xl">{t("home.heroSuffix")}</span>
              <TrendingUp className="w-10 h-10 sm:w-12 sm:h-12 text-primary animate-float" />
            </span>
            <br />
            <span className="text-muted-foreground text-2xl sm:text-3xl font-medium">
              {t("home.heroSubtitle")}
            </span>
          </h1>

          <div className="mt-6 flex flex-col gap-4 sm:flex-row sm:justify-center">
            {isLoggedIn ? (
              <Link
                href="/dashboard"
                className="rounded-full bg-primary px-6 py-3 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
              >
                {t("home.viewDashboard")}
              </Link>
            ) : (
              <Link
                href="/login?next=/dashboard"
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
        </div>

        <div
          className="text-center mb-8 opacity-0 animate-fade-in"
          style={{ animationDelay: "200ms", animationFillMode: "forwards" }}
        >
          <h2 className="font-display text-xl sm:text-2xl font-semibold text-foreground">{t("home.topPicks")}</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-4xl mx-auto mb-16">
          {rankings.map((item, index) => (
            <StockCard
              key={item.rank}
              rank={item.rank}
              ticker={item.ticker}
              name={item.name}
              winRate={item.win_rate}
              avgReturn={item.avg_return}
              holdingPeriod={formatHoldingPeriod(today, locale)}
              isTop={item.rank === 1}
              delay={250 + index * 120}
              isLoggedIn={isLoggedIn}
            />
          ))}
        </div>

        <SearchBar isLoggedIn={isLoggedIn} />

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
              <h3 className="mt-4 font-display text-2xl font-semibold text-foreground">{t("home.signInToUnlock")}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{t("home.googleOnly")}</p>
              <div className="mt-6 flex justify-center">
                <Link
                  href="/login?next=/dashboard"
                  className="rounded-full bg-primary px-6 py-3 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
                >
                  {t("nav.goToLogin")}
                </Link>
              </div>
            </div>
          </div>
        )}

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
