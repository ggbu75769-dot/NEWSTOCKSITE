import LoginView from "@/components/LoginView";
import { getServerSession } from "@/lib/supabase/server";
import { redirect } from "next/navigation";

type LoginPageProps = {
  searchParams?: Promise<{
    error?: string | string[];
    next?: string | string[];
  }>;
};

const getErrorKey = (error?: string) => {
  if (!error) return null;
  switch (error) {
    case "missing_code":
      return "login.errorMissingCode";
    case "exchange_failed":
      return "login.errorExchangeFailed";
    case "no_user":
      return "login.errorNoUser";
    case "profile_upsert_failed":
      return "login.errorProfileUpsertFailed";
    case "google_sign_in_failed":
      return "login.errorGoogleSignInFailed";
    default:
      return "login.errorDefault";
  }
};

export default async function LoginPage({ searchParams }: LoginPageProps) {
  const session = await getServerSession();

  if (session) {
    redirect("/dashboard");
  }

  const resolvedSearchParams = searchParams ? await searchParams : undefined;
  const errorValue = Array.isArray(resolvedSearchParams?.error)
    ? resolvedSearchParams?.error[0]
    : resolvedSearchParams?.error;
  const nextValue = Array.isArray(resolvedSearchParams?.next)
    ? resolvedSearchParams?.next[0]
    : resolvedSearchParams?.next;

  const errorKey = getErrorKey(errorValue);
  const nextTarget = nextValue ?? "/dashboard";

  return <LoginView errorKey={errorKey} nextTarget={nextTarget} />;
}
