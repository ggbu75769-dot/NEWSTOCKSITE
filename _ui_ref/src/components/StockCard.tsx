import { TrendingUp, Calendar } from "lucide-react";
import FlameIcon from "./FlameIcon";

interface StockCardProps {
  rank: number;
  name: string;
  ticker: string;
  winRate: number;
  avgReturn: number;
  holdingPeriod: string;
  isTop?: boolean;
  delay?: number;
}

const StockCard = ({
  rank,
  name,
  ticker,
  winRate,
  avgReturn,
  holdingPeriod,
  isTop = false,
  delay = 0,
}: StockCardProps) => {
  const getRankEmoji = () => {
    if (rank === 1) return "🥇";
    if (rank === 2) return "🥈";
    if (rank === 3) return "🥉";
    return `#${rank}`;
  };

  return (
    <div
      className={`relative rounded-2xl p-6 cursor-pointer opacity-0 animate-slide-up ${
        isTop
          ? "card-top animate-float-slow"
          : "card-elevated"
      }`}
      style={{ animationDelay: `${delay}ms`, animationFillMode: 'forwards' }}
    >
      {/* Rank Badge */}
      <div className="flex items-center justify-between mb-4">
        <span className="text-3xl">{getRankEmoji()}</span>
        {isTop && <FlameIcon size="lg" />}
      </div>

      {/* Stock Name & Ticker */}
      <div className="mb-6">
        <h3 className="font-display text-2xl font-bold text-foreground mb-1">
          {name}
        </h3>
        <span className="inline-block px-3 py-1 rounded-full bg-secondary text-muted-foreground text-sm font-medium">
          {ticker}
        </span>
      </div>

      {/* Big Numbers */}
      <div className="grid grid-cols-2 gap-4 mb-4">
        {/* Win Rate */}
        <div className="text-center p-3 rounded-xl bg-primary/10">
          <div className={`font-display text-4xl font-bold ${isTop ? "text-gradient-fire" : "text-primary"}`}>
            {winRate}%
          </div>
          <div className="text-xs text-muted-foreground mt-1 flex items-center justify-center gap-1">
            <FlameIcon size="sm" />
            Win Rate
          </div>
        </div>

        {/* Avg Return */}
        <div className="text-center p-3 rounded-xl bg-primary/10">
          <div className="font-display text-4xl font-bold text-primary flex items-center justify-center">
            <TrendingUp className="w-6 h-6 mr-1" />
            {avgReturn}%
          </div>
          <div className="text-xs text-muted-foreground mt-1">
            Avg Return
          </div>
        </div>
      </div>

      {/* Holding Period Badge */}
      <div className="flex items-center justify-center gap-2 p-3 rounded-xl bg-secondary">
        <Calendar className="w-4 h-4 text-muted-foreground" />
        <span className="text-sm font-medium text-foreground">{holdingPeriod}</span>
      </div>

      {/* Floating indicator for top card */}
      {isTop && (
        <div className="absolute -top-2 -right-2 px-3 py-1 bg-accent text-accent-foreground text-xs font-bold rounded-full shadow-lg animate-bounce-soft">
          HOT 🔥
        </div>
      )}
    </div>
  );
};

export default StockCard;
