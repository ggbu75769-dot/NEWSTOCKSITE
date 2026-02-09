import DashboardView from "@/components/DashboardView";
import { getServerSession } from "@/lib/supabase/server";
import { redirect } from "next/navigation";

export default async function DashboardPage() {
  const session = await getServerSession();

  if (!session) {
    redirect("/");
  }

  const user = session.user;
  const name = user.user_metadata?.full_name ?? user.user_metadata?.name ?? null;
  const avatarUrl = user.user_metadata?.avatar_url ?? null;
  const email = user.email ?? null;

  return <DashboardView name={name} email={email} avatarUrl={avatarUrl} />;
}
