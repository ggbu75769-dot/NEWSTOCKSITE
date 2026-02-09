import { Flame } from "lucide-react";

const FlameIcon = ({ size = "md" }: { size?: "sm" | "md" | "lg" }) => {
  const sizeClasses = {
    sm: "w-5 h-5",
    md: "w-7 h-7",
    lg: "w-10 h-10",
  };

  return (
    <div className="relative inline-flex">
      <Flame 
        className={`${sizeClasses[size]} text-accent animate-flame drop-shadow-lg`} 
        fill="currentColor"
        strokeWidth={1.5}
      />
      <Flame 
        className={`${sizeClasses[size]} text-fire-mid absolute inset-0 opacity-50 animate-flame blur-[1px]`} 
        fill="currentColor"
        strokeWidth={0}
        style={{ animationDelay: '0.15s' }} 
      />
    </div>
  );
};

export default FlameIcon;
