"use client";

import { useState } from "react";
import { useBitcoinData } from "../hooks/useBitcoinData";
import PriceChart from "../components/PriceChart";

export default function Page() {
  const [days, setDays] = useState(90);
  const { data, isLoading, error } = useBitcoinData(days);

  return (
    <main className="p-6 min-h-screen bg-gray-50">
      {/* Header */}
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">
          Bitcoin Price & Volume Dashboard
        </h1>

        {/* Day Range Selector */}
        <div className="mt-4 flex items-center gap-3">
          <label className="text-gray-700 font-medium">Select Range:</label>
          <select
            className="border border-gray-300 rounded px-3 py-2 bg-white shadow-sm text-gray-800 focus:outline-none focus:ring focus:ring-blue-300"
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
          >
            <option value={7}>7 Days</option>
            <option value={30}>30 Days</option>
            <option value={90}>90 Days</option>
          </select>
        </div>
      </header>

      {/* Content Section */}
      <section>
        {/* Error State */}
        {error && (
          <div className="text-red-600 font-medium">
            Error fetching data: {error instanceof Error ? error.message : "Unknown error"}
          </div>
        )}

        {/* Chart */}
        <PriceChart data={data || []} isLoading={isLoading} />

        {/* Empty State */}
        {!isLoading && !error && data && data.length === 0 && (
          <div className="text-gray-600 text-lg">
            No data available for this range.
          </div>
        )}
      </section>
    </main>
  );
}