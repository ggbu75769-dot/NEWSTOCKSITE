import { useState } from "react";
import { Search, Sparkles } from "lucide-react";

const SearchBar = () => {
  const [ticker, setTicker] = useState("");
  const [isFocused, setIsFocused] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (ticker.trim()) {
      console.log("Searching for:", ticker.toUpperCase());
    }
  };

  return (
    <form 
      onSubmit={handleSubmit} 
      className="w-full max-w-xl mx-auto opacity-0 animate-slide-up"
      style={{ animationDelay: '500ms', animationFillMode: 'forwards' }}
    >
      <div
        className={`relative bg-card rounded-2xl p-2 search-elevated ${
          isFocused ? "ring-2 ring-primary/30" : ""
        }`}
      >
        <div className="flex items-center gap-3 px-4">
          <Sparkles className={`w-5 h-5 transition-colors duration-300 ${isFocused ? "text-accent" : "text-muted-foreground"} animate-pulse-soft`} />
          <input
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            placeholder="Enter ticker (e.g., AAPL)"
            className="flex-1 bg-transparent border-none outline-none text-foreground placeholder:text-muted-foreground font-body text-lg py-4"
          />
          <button
            type="submit"
            className="bg-primary hover:bg-primary/90 text-primary-foreground font-display font-semibold px-6 py-3 rounded-xl transition-all duration-200 hover:scale-105 hover:shadow-lg flex items-center gap-2 active:scale-95"
          >
            <Search className="w-4 h-4" />
            <span>Go</span>
          </button>
        </div>
      </div>
      
      <p className="text-center text-muted-foreground text-sm mt-3">
        Discover your stock's historical destiny ✨
      </p>
    </form>
  );
};

export default SearchBar;
