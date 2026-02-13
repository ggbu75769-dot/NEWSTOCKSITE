"use client";

import { Calendar, Flame, Lock, TrendingUp, UserPlus, Sparkles } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

export type StockCardProps = {
  rank: number;
  ticker: string;
  name: string;
  aiScore: number;
  avgReturn: number;
  holdingPeriod: string;
  isTop?: boolean;
  delay?: number;
  isLoggedIn: boolean;
};

const getRankLabel = (rank: number, t: (key: string) => string) => {
  if (rank === 1) return t("stockCard.rankTop");
  if (rank === 2) return t("stockCard.rankRunnerUp");
  if (rank === 3) return t("stockCard.rankThird");
  return `#${rank}`;
};

const getLockedCta = (rank: number, t: (key: string) => string) => {
  if (rank === 2) {
    return {
      title: t("stockCard.lockedSecondTitle"),
      body: t("stockCard.lockedSecondBody"),
      icon: Sparkles,
    };
  }
  if (rank === 3) {
    return {
      title: t("stockCard.lockedThirdTitle"),
      body: t("stockCard.lockedThirdBody"),
      icon: UserPlus,
    };
  }
  return {
    title: t("stockCard.lockedTopTitle"),
    body: t("stockCard.lockedTopBody"),
    icon: Lock,
  };
};

export default function StockCard({
  rank,
  ticker,
  name,
  aiScore,
  avgReturn,
  holdingPeriod,
  isTop = false,
  delay = 0,
  isLoggedIn,
}: StockCardProps) {
  const { t } = useTranslation();
  const isUnlocked = isLoggedIn || rank === 1;
  const isLocked = !isUnlocked;
  const lockedCta = getLockedCta(rank, t);
  const LockedIcon = lockedCta.icon;
  const [hasAuthSection, setHasAuthSection] = useState(false);

  useEffect(() => {
    setHasAuthSection(Boolean(document.getElementById("auth-section")));
  }, []);

  const openPrompt = useCallback(() => {
    if (isLocked && hasAuthSection) {
      const authSection = document.getElementById("auth-section");
      if (authSection) {
        authSection.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }
  }, [isLocked, hasAuthSection]);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLDivElement>) => {
      if (!isLocked) return;
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openPrompt();
      }
    },
    [isLocked, openPrompt]
  );

  return (
    <div
      className={`relative rounded-2xl p-6 opacity-0 animate-slide-up-soft ${
        isTop ? "card-top animate-float-slow" : "card-elevated"
      } ${isLocked && hasAuthSection ? "cursor-pointer" : ""}`}
      style={{ animationDelay: `${delay}ms`, animationFillMode: "forwards" }}
      onClick={isLocked && hasAuthSection ? openPrompt : undefined}
      onKeyDown={isLocked && hasAuthSection ? handleKeyDown : undefined}
      role={isLocked && hasAuthSection ? "button" : undefined}
      tabIndex={isLocked && hasAuthSection ? 0 : -1}
      aria-disabled={isLocked ? false : undefined}
    >
      <div className={isLocked ? "blur-md select-none" : ""}>
        <div className="flex items-center justify-between mb-4">
          <span className="text-sm font-semibold text-muted-foreground">
            {getRankLabel(rank, t)}
          </span>
          {isTop && <Flame className="w-6 h-6 text-accent animate-flame" />}
        </div>

        <div className="mb-6">
          <h3 className="font-display text-2xl font-bold text-foreground mb-1">{name}</h3>
          <span className="inline-block px-3 py-1 rounded-full bg-secondary text-muted-foreground text-sm font-medium">
            {ticker}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-4 mb-4">
          <div className="text-center p-3 rounded-xl bg-primary/10">
            <div className={`font-display text-4xl font-bold ${isTop ? "text-gradient-fire" : "text-primary"}`}>
              {aiScore.toFixed(0)}
            </div>
            <div className="text-xs text-muted-foreground mt-1 flex items-center justify-center gap-1">
              <Flame className="w-3 h-3 text-accent" />
              {t("stockCard.aiScore")}
            </div>
          </div>

          <div className="text-center p-3 rounded-xl bg-primary/10">
            <div className="font-display text-4xl font-bold text-primary flex items-center justify-center">
              <TrendingUp className="w-6 h-6 mr-1" />
              {avgReturn.toFixed(1)}%
            </div>
            <div className="text-xs text-muted-foreground mt-1">{t("stockCard.avgReturn")}</div>
          </div>
        </div>

        <div className="flex items-center justify-center gap-2 p-3 rounded-xl bg-secondary">
          <Calendar className="w-4 h-4 text-muted-foreground" />
          <span className="text-sm font-medium text-foreground">{holdingPeriod}</span>
        </div>
      </div>

      {isLocked && (
        <div className="absolute inset-0 rounded-2xl bg-background/70 backdrop-blur-[2px] flex flex-col items-center justify-center gap-3 text-center opacity-0 animate-fade-in">
          <div className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-xs font-semibold text-foreground shadow-sm">
            <LockedIcon className="w-3 h-3" />
            {lockedCta.title}
          </div>
          <p className="text-sm font-semibold text-foreground">{lockedCta.body}</p>
          <span className="text-xs text-muted-foreground">{t("stockCard.lockedHint")}</span>
        </div>
      )}

      {isTop && (
        <div className="absolute -top-2 -right-2 px-3 py-1 bg-accent text-accent-foreground text-xs font-bold rounded-full shadow-lg animate-bounce-soft">
          {t("stockCard.focus")}
        </div>
      )}
    </div>
  );
}
