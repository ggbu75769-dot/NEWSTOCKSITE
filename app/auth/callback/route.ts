import { NextResponse } from "next/server";
import { createRouteSupabaseClient } from "@/lib/supabase/server";

export async function GET(request: Request) {
  const requestUrl = new URL(request.url);
  const code = requestUrl.searchParams.get("code");
  const next = requestUrl.searchParams.get("next") ?? "/dashboard";
  const origin = requestUrl.origin;

  if (!code) {
    console.error("[auth] Missing OAuth code");
    return NextResponse.redirect(new URL("/login?error=missing_code", origin));
  }

  const supabase = await createRouteSupabaseClient();
  const { data: sessionData, error: exchangeError } = await supabase.auth.exchangeCodeForSession(code);

  if (exchangeError) {
    console.error("[auth] exchangeCodeForSession failed", exchangeError);
    return NextResponse.redirect(new URL(`/login?error=exchange_failed`, origin));
  }

  const user = sessionData?.user;

  if (!user) {
    console.error("[auth] No user returned after exchange");
    return NextResponse.redirect(new URL(`/login?error=no_user`, origin));
  }

  const profilePayload = {
    id: user.id,
    email: user.email,
    full_name: user.user_metadata?.full_name ?? null,
    avatar_url: user.user_metadata?.avatar_url ?? null,
    name: user.user_metadata?.name ?? null,
    last_sign_in_at: new Date().toISOString(),
  };

  const { error: upsertError } = await supabase
    .from("profiles")
    .upsert(profilePayload, { onConflict: "id" });

  if (upsertError) {
    console.error("[auth] profile upsert failed", upsertError);
    return NextResponse.redirect(new URL(`/login?error=profile_upsert_failed`, origin));
  }

  return NextResponse.redirect(new URL(next, origin));
}
