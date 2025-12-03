// dashboard/components/PriceChartClient.tsx
"use client";

import {
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
} from "recharts";
import dayjs from "dayjs";
import type { BitcoinRow } from "../hooks/useBitcoinData";

interface Props {
  data: BitcoinRow[];
}

export function PriceChartClient({ data }: Props) {
  // Sort by date ascending
  const sorted = [...data].sort(
    (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
  );

  return (
    <div className="w-full h-[300px] sm:h-[400px] md:h-[500px] p-4 bg-white rounded-xl shadow">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={sorted}>
          <CartesianGrid strokeDasharray="3 3" />

          <XAxis
            dataKey="date"
            tickFormatter={(d) => dayjs(d).format("MMM D")}
          />

          {/* Price axis (left) */}
          <YAxis
            yAxisId="left"
            domain={["auto", "auto"]}
            tickFormatter={(v) => `$${v.toLocaleString()}`}
          />

          {/* Volume axis (right) */}
          <YAxis
            yAxisId="right"
            orientation="right"
            domain={[0, "dataMax"]}
            tickFormatter={(v) => `${(v / 1_000_000).toFixed(1)}M`}
          />

          <Tooltip
            labelFormatter={(d) => dayjs(d).format("YYYY-MM-DD")}
            formatter={(value, name, props) => {
              if (value === null || value === undefined) return [null, name];
              if (props.dataKey === "price_usd") return [`$${value.toLocaleString()}`, "Price"];
              if (props.dataKey === "volume_usd") return [`$${value.toLocaleString()}`, "Volume"];
              return [value, name];
            }}
          />

          <Bar
            yAxisId="right"
            dataKey="volume_usd"
            name="Volume"
            barSize={16}
            fill="#a3bffa"
            radius={[4, 4, 0, 0]}
          />

          <Line
            yAxisId="left"
            type="monotone"
            dataKey="price_usd"
            name="Price"
            stroke="#4c51bf"
            strokeWidth={2}
            dot={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}