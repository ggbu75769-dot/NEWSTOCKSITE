import LoginView from "@/components/LoginView";
import { authOptions } from "@/lib/auth";
import { getServerSession } from "next-auth";
import { redirect } from "next/navigation";

type LoginPageProps = {
  searchParams?: Promise<{
    callbackUrl?: string;
  }>;
};

function normalizeCallbackUrl(raw: string | undefined): string {
  if (!raw) return "/dashboard";
  if (!raw.startsWith("/")) return "/dashboard";
  return raw;
}

export default async function LoginPage({ searchParams }: LoginPageProps) {
  const session = await getServerSession(authOptions);
  const resolvedSearchParams = searchParams ? await searchParams : undefined;
  const callbackUrl = normalizeCallbackUrl(resolvedSearchParams?.callbackUrl);

  if (session) {
    redirect(callbackUrl);
  }

  return <LoginView callbackUrl={callbackUrl} />;
}
