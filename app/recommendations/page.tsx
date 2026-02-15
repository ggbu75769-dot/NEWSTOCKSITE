import RecommendationsView from "@/components/RecommendationsView";
import { authOptions } from "@/lib/auth";
import { getServerSession } from "next-auth";
import { redirect } from "next/navigation";

export default async function RecommendationsPage() {
  const session = await getServerSession(authOptions);
  if (!session) {
    redirect("/login?callbackUrl=/recommendations");
  }

  return (
    <RecommendationsView
      name={session.user?.name ?? null}
      email={session.user?.email ?? null}
      avatarUrl={session.user?.image ?? null}
      isLoggedIn
    />
  );
}
