import LoginView from "@/components/LoginView";
import { getServerSession } from "@/lib/supabase/server";
import { redirect } from "next/navigation";

type LoginPageProps = {
  searchParams?:
    | {
        error?: string;
        next?: string;
      }
    | Promise<{
        error?: string;
        next?: string;
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

  const resolvedSearchParams = await Promise.resolve(searchParams);
  const errorKey = getErrorKey(resolvedSearchParams?.error);
  const nextTarget = resolvedSearchParams?.next ?? "/dashboard";

  return <LoginView errorKey={errorKey} nextTarget={nextTarget} />;
}
