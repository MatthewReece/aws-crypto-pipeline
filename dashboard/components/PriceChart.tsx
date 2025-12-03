// dashboard/components/PriceChart.tsx
import dynamic from "next/dynamic";
import { BitcoinRow } from "../hooks/useBitcoinData";

interface Props {
  data: BitcoinRow[];
  isLoading: boolean;
}

// Loading placeholder for SSR
const LoadingPlaceholder = () => (
  <div className="w-full min-h-[300px] sm:min-h-[400px] md:min-h-[500px] bg-white rounded-xl shadow p-4 flex items-center justify-center text-gray-500">
    Loading Chart...
  </div>
);

// Dynamic import: client-side only
const PriceChartClient = dynamic(
  () => import("./PriceChartClient").then((mod) => mod.PriceChartClient),
  { ssr: false, loading: () => <LoadingPlaceholder /> }
);

export default function PriceChart({ data, isLoading }: Props) {
  if (isLoading) {
    return <LoadingPlaceholder />;
  }

  return <PriceChartClient data={data} />;
}