import RecommendationsView from "@/components/RecommendationsView";
import { getServerSession } from "@/lib/supabase/server";

export default async function RecommendationsPage() {
  const session = await getServerSession();
  const user = session?.user;
  const name = user?.user_metadata?.full_name ?? user?.user_metadata?.name ?? null;
  const avatarUrl = user?.user_metadata?.avatar_url ?? null;
  const email = user?.email ?? null;

  return <RecommendationsView name={name} email={email} avatarUrl={avatarUrl} isLoggedIn={Boolean(session)} />;
}
