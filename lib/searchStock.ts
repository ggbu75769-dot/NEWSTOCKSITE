export type SupabaseRpcClient = {
  rpc: (
    fn: string,
    args: Record<string, unknown>
  ) => PromiseLike<{
    data: unknown;
    error: { message: string } | null;
  }>;
};

export async function searchStock(supabase: SupabaseRpcClient, symbol: string) {
  const { data, error } = await supabase.rpc("search_stock_public", {
    p_symbol: symbol,
  });

  if (error || !data || !Array.isArray(data) || data.length === 0) {
    return null;
  }

  return data[0];
}
