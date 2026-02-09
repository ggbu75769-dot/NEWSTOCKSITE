import { cookies } from "next/headers";
import { createServerClient } from "@supabase/ssr";
import { cache } from "react";

const getEnv = () => {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (!supabaseUrl || !supabaseKey) {
    throw new Error("Missing NEXT_PUBLIC_SUPABASE_URL or NEXT_PUBLIC_SUPABASE_ANON_KEY");
  }

  return { supabaseUrl, supabaseKey };
};

export const createServerSupabaseClient = async () => {
  const cookieStore = await cookies();
  const { supabaseUrl, supabaseKey } = getEnv();

  return createServerClient(supabaseUrl, supabaseKey, {
    cookies: {
      get(name) {
        return cookieStore.get(name)?.value;
      },
      set() {
        // Server Components cannot set cookies. Use route handlers for auth mutations.
      },
      remove() {
        // Server Components cannot remove cookies. Use route handlers for auth mutations.
      },
    },
  });
};

export const createRouteSupabaseClient = async () => {
  const cookieStore = await cookies();
  const { supabaseUrl, supabaseKey } = getEnv();

  return createServerClient(supabaseUrl, supabaseKey, {
    cookies: {
      get(name) {
        return cookieStore.get(name)?.value;
      },
      set(name, value, options) {
        cookieStore.set({ name, value, ...options });
      },
      remove(name, options) {
        cookieStore.set({ name, value: "", ...options, maxAge: 0 });
      },
    },
  });
};

export const getServerSession = cache(async () => {
  try {
    const supabase = await createServerSupabaseClient();
    const {
      data: { session },
      error,
    } = await supabase.auth.getSession();
    if (error) {
      console.error("[auth] getSession failed", error);
      return null;
    }
    return session ?? null;
  } catch (err) {
    console.error("[auth] getServerSession exception", err);
    return null;
  }
});
