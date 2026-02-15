import DashboardView from "@/components/DashboardView";
import { authOptions } from "@/lib/auth";
import { getServerSession } from "next-auth";
import { redirect } from "next/navigation";

export default async function DashboardPage() {
  const session = await getServerSession(authOptions);
  if (!session) {
    redirect("/login?callbackUrl=/dashboard");
  }

  return (
    <DashboardView
      name={session.user?.name ?? null}
      email={session.user?.email ?? null}
      avatarUrl={session.user?.image ?? null}
    />
  );
}
