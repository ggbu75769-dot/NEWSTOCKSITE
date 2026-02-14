import HomeView, { RankingItem } from "@/components/HomeView";
import { getLocalHomeRankings } from "@/lib/localDb";

export default async function Page() {
  const today = new Date();
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
      isLoggedIn
      name={null}
      avatarUrl={null}
      email={null}
      todayIso={today.toISOString()}
    />
  );
}
