import HomeView, { RankingItem } from "@/components/HomeView";
import { authOptions } from "@/lib/auth";
import { getLocalHomeRankings } from "@/lib/localDb";
import { getServerSession } from "next-auth";

export default async function Page() {
  const today = new Date();
  const session = await getServerSession(authOptions);
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

  const localRankings = await getLocalHomeRankings(3);
  const rankings = (localRankings.length > 0 ? localRankings : fallback) as RankingItem[];

  return (
    <HomeView
      rankings={rankings}
      isLoggedIn={Boolean(session)}
      name={session?.user?.name ?? null}
      avatarUrl={session?.user?.image ?? null}
      email={session?.user?.email ?? null}
      todayIso={today.toISOString()}
    />
  );
}
