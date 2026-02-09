import { useMemo } from "react";
import { TrendingUp } from "lucide-react";

const sampleStockData: Record<string, { stock: string; ticker: string; rises: number; years: number }> = {
  "02-06": { stock: "Apple", ticker: "AAPL", rises: 8, years: 10 },
  "02-07": { stock: "Samsung", ticker: "005930.KS", rises: 9, years: 10 },
  "02-08": { stock: "Tesla", ticker: "TSLA", rises: 7, years: 10 },
  "02-09": { stock: "Microsoft", ticker: "MSFT", rises: 8, years: 10 },
  "02-10": { stock: "Amazon", ticker: "AMZN", rises: 9, years: 10 },
};

const DynamicHeadline = () => {
  const { formattedDate, stockData } = useMemo(() => {
    const now = new Date();
    const month = String(now.getMonth() + 1).padStart(2, "0");
    const day = String(now.getDate()).padStart(2, "0");
    const dateKey = `${month}-${day}`;
    
    const monthNames = [
      "Jan", "Feb", "Mar", "Apr", "May", "Jun",
      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
    ];
    
    const formatted = `${monthNames[now.getMonth()]} ${now.getDate()}`;
    const data = sampleStockData[dateKey] || { stock: "NVIDIA", ticker: "NVDA", rises: 9, years: 10 };
    
    return { formattedDate: formatted, stockData: data };
  }, []);

  return (
    <div className="text-center mb-10 opacity-0 animate-fade-in" style={{ animationDelay: '100ms', animationFillMode: 'forwards' }}>
      {/* Date Badge */}
      <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-accent/10 text-accent font-semibold text-sm mb-6 animate-bounce-soft">
        <span>📅</span>
        <span>{formattedDate}</span>
      </div>
      
      {/* Main Headline */}
      <h1 className="font-display text-4xl sm:text-5xl md:text-6xl font-bold text-foreground leading-tight mb-4">
        <span className="text-gradient-gain">{stockData.stock}</span> rose
        <br />
        <span className="inline-flex items-center gap-2">
          <span className="text-gradient-fire text-5xl sm:text-6xl md:text-7xl">{stockData.rises}/{stockData.years}</span>
          <TrendingUp className="w-10 h-10 sm:w-12 sm:h-12 text-primary animate-float" />
        </span>
        <br />
        <span className="text-muted-foreground text-2xl sm:text-3xl font-medium">years on this day</span>
      </h1>
    </div>
  );
};

export default DynamicHeadline;
