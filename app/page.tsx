import HomeView, { RankingItem } from "@/components/HomeView";
import { createServerSupabaseClient, getServerSession } from "@/lib/supabase/server";

export default async function Page() {
  const supabase = await createServerSupabaseClient();
  const today = new Date();
  const rankingDate = today.toISOString().slice(0, 10);

  const session = await getServerSession();

  const { data } = await supabase
    .from("daily_rankings_public")
    .select("rank, win_rate, avg_return, confluence_score, ticker, name")
    .eq("ranking_date", rankingDate)
    .order("rank", { ascending: true });

  const fallback: RankingItem[] = [
    {
      rank: 1,
      win_rate: 92.1,
      avg_return: 5.2,
      confluence_score: 97.0,
      ticker: "NVDA",
      name: "NVIDIA",
    },
    {
      rank: 2,
      win_rate: 85.4,
      avg_return: 4.8,
      confluence_score: 90.3,
      ticker: "BTC",
      name: "Bitcoin",
    },
    {
      rank: 3,
      win_rate: 80.7,
      avg_return: 3.5,
      confluence_score: 86.2,
      ticker: "AAPL",
      name: "Apple",
    },
  ];

  const rankings = (data && data.length > 0 ? data : fallback) as RankingItem[];
  const isLoggedIn = Boolean(session);
  const user = session?.user;
  const name = user?.user_metadata?.full_name ?? user?.user_metadata?.name ?? null;
  const avatarUrl = user?.user_metadata?.avatar_url ?? null;
  const email = user?.email ?? null;

  return (
    <HomeView
      rankings={rankings}
      isLoggedIn={isLoggedIn}
      name={name}
      avatarUrl={avatarUrl}
      email={email}
      todayIso={today.toISOString()}
    />
  );
}
