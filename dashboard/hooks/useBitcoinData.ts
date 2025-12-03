"use client";

import { useQuery } from "@tanstack/react-query";

export interface BitcoinRow {
  date: string;
  price_usd: number;
  volume_usd: number;
}

export function useBitcoinData(days: number) {
  const endpoint = process.env.NEXT_PUBLIC_API_ENDPOINT;

  return useQuery<BitcoinRow[], Error>({
    queryKey: ["bitcoin-data", days],
    queryFn: async () => {
      if (!endpoint) {
        throw new Error("NEXT_PUBLIC_API_ENDPOINT is not defined");
      }

      const res = await fetch(`${endpoint}/crypto?days=${days}`);

      if (!res.ok) {
        throw new Error(`Failed to fetch bitcoin data: ${res.status}`);
      }

      const json = await res.json();

      // Type assertion for safety
      if (!json.data || !Array.isArray(json.data)) {
        throw new Error("Unexpected response format from API");
      }

      return json.data as BitcoinRow[];
    },
  });
}