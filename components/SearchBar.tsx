"use client";

import { useState } from "react";
import { Search, Sparkles } from "lucide-react";
import GoogleSignInButton from "@/components/GoogleSignInButton";
import { useTranslation } from "react-i18next";

type SearchResult = {
  ticker: string;
  name: string;
  sector: string | null;
  ranking_date: string | null;
  rank: number | null;
  win_rate: number | null;
  avg_return: number | null;
  confluence_score: number | null;
};

type SearchBarProps = {
  isLoggedIn: boolean;
};

export default function SearchBar({ isLoggedIn }: SearchBarProps) {
  const { t } = useTranslation();
  const [symbol, setSymbol] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SearchResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isFocused, setIsFocused] = useState(false);

  const handleSearch = async () => {
    if (!symbol.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch(`/api/search?symbol=${encodeURIComponent(symbol.trim())}`);
      const data = await res.json();
      if (!res.ok) {
        setError(t("search.errorNoData"));
      } else {
        setResult(data);
      }
    } catch (err) {
      setError(t("search.errorFailed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full max-w-xl mx-auto opacity-0 animate-slide-up" style={{ animationDelay: "500ms", animationFillMode: "forwards" }}>
      <div
        className={`relative bg-card rounded-2xl p-2 search-elevated ${isFocused ? "ring-2 ring-primary/30" : ""}`}
      >
        <div className="flex items-center gap-3 px-4">
          <Sparkles
            className={`w-5 h-5 transition-colors duration-300 ${
              isFocused ? "text-accent" : "text-muted-foreground"
            } animate-pulse-soft`}
          />
          <input
            value={symbol}
            onChange={(event) => setSymbol(event.target.value.toUpperCase())}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            placeholder={t("search.placeholder")}
            className="flex-1 bg-transparent border-none outline-none text-foreground placeholder:text-muted-foreground font-body text-lg py-4"
          />
          <button
            onClick={handleSearch}
            disabled={loading}
            className="bg-primary hover:bg-primary/90 text-primary-foreground font-display font-semibold px-6 py-3 rounded-xl transition-all duration-200 hover:scale-105 hover:shadow-lg flex items-center gap-2 active:scale-95 disabled:opacity-60"
          >
            <Search className="w-4 h-4" />
            <span>{loading ? t("search.searching") : t("search.go")}</span>
          </button>
        </div>
      </div>

      {error && <p className="mt-4 text-sm text-destructive">{error}</p>}

      {result && (
        <div className="mt-6 rounded-2xl border border-border bg-card p-6 shadow-[0_12px_36px_rgba(15,23,42,0.12)]">
          <div className={isLoggedIn ? "" : "blur-md"}>
            <p className="text-lg font-semibold text-foreground">{result.ticker}</p>
            <p className="text-sm text-muted-foreground">{result.name}</p>
          </div>
          <div className="mt-4 grid gap-3 text-xs text-muted-foreground sm:grid-cols-3">
            <div>
              <p className="text-muted-foreground">{t("search.latestRank")}</p>
              <p className="text-base font-semibold text-foreground">{result.rank ?? "-"}</p>
            </div>
            <div>
              <p className="text-muted-foreground">{t("search.winRate")}</p>
              <p className="text-base font-semibold text-foreground">
                {result.win_rate !== null ? `${Number(result.win_rate).toFixed(1)}%` : "-"}
              </p>
            </div>
            <div>
              <p className="text-muted-foreground">{t("search.aiScore")}</p>
              <p className="text-base font-semibold text-foreground">
                {result.confluence_score !== null ? Number(result.confluence_score).toFixed(1) : "-"}
              </p>
            </div>
          </div>

          {!isLoggedIn && (
            <div className="mt-4 flex flex-col gap-2 text-xs text-muted-foreground">
              <p>{t("search.signInReveal")}</p>
              <GoogleSignInButton label={t("search.revealStock")} />
            </div>
          )}
        </div>
      )}

      <p className="text-center text-muted-foreground text-sm mt-3">
        {t("search.footer")}
      </p>
    </div>
  );
}
