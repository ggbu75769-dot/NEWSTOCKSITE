import DynamicHeadline from "@/components/DynamicHeadline";
import StockCard from "@/components/StockCard";
import SearchBar from "@/components/SearchBar";
import { Sparkles } from "lucide-react";

const topStocks = [
  {
    rank: 1,
    name: "NVIDIA",
    ticker: "NVDA",
    winRate: 90,
    avgReturn: 5.2,
    holdingPeriod: "Feb 7 → Feb 14",
    isTop: true,
  },
  {
    rank: 2,
    name: "Bitcoin",
    ticker: "BTC",
    winRate: 85,
    avgReturn: 4.8,
    holdingPeriod: "Feb 7 → Feb 14",
    isTop: false,
  },
  {
    rank: 3,
    name: "Apple",
    ticker: "AAPL",
    winRate: 80,
    avgReturn: 3.5,
    holdingPeriod: "Feb 7 → Feb 14",
    isTop: false,
  },
];

const Index = () => {
  return (
    <div className="min-h-screen bg-background relative overflow-hidden">
      {/* Soft gradient backgrounds */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-primary/5 rounded-full blur-3xl animate-float-slow" />
        <div className="absolute bottom-0 left-0 w-[400px] h-[400px] bg-accent/5 rounded-full blur-3xl animate-float" style={{ animationDelay: '1s' }} />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-primary/3 rounded-full blur-3xl" />
      </div>

      <div className="relative z-10 container mx-auto px-4 py-12 md:py-16">
        {/* Header Badge */}
        <div className="flex justify-center mb-8 opacity-0 animate-scale-in" style={{ animationFillMode: 'forwards' }}>
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-card shadow-md border border-border">
            <Sparkles className="w-4 h-4 text-accent" />
            <span className="text-sm font-medium text-foreground">History Repeats Itself</span>
          </div>
        </div>

        {/* Headline */}
        <DynamicHeadline />

        {/* Section Title */}
        <div className="text-center mb-8 opacity-0 animate-fade-in" style={{ animationDelay: '200ms', animationFillMode: 'forwards' }}>
          <h2 className="font-display text-xl sm:text-2xl font-semibold text-foreground">
            🎯 Top 3 Picks for Next Week
          </h2>
        </div>

        {/* Stock Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-4xl mx-auto mb-16">
          {topStocks.map((stock, index) => (
            <StockCard key={stock.ticker} {...stock} delay={250 + index * 100} />
          ))}
        </div>

        {/* Search Bar */}
        <SearchBar />

        {/* Disclaimer */}
        <p className="text-center text-muted-foreground/60 text-xs mt-12 max-w-md mx-auto opacity-0 animate-fade-in" style={{ animationDelay: '700ms', animationFillMode: 'forwards' }}>
          📊 Based on historical patterns. Not financial advice.
        </p>
      </div>
    </div>
  );
};

export default Index;
