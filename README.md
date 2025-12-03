Bitcoin Data Pipeline & Dashboard

A serverless Bitcoin price and volume dashboard built with AWS Lambda, S3, Athena, and Next.js. Displays historical and real-time Bitcoin data in responsive charts.

⸻

Project Overview

This project fetches Bitcoin data from the CoinGecko API, processes it with AWS Lambda, stores it in S3 (partitioned by date), queries it with Athena, and visualizes it in a responsive Next.js frontend.

Features:
• Historical backfill of Bitcoin data.
• Multiple timeframe selection: 7, 30, 90 days.
• Interactive charts for price and volume.
• Fully serverless and cloud-hosted.
• Efficient data fetching and caching with TanStack (React Query).

⸻

Architecture

1. CoinGecko API → fetches historical and current market data.
2. AWS Lambda ETL → processes and writes data to S3 in Parquet format.
3. S3 Data Lake → stores raw and processed data.
4. Athena → queries partitioned data efficiently.
5. Next.js Dashboard → fetches data from API using TanStack React Query and renders charts with Recharts.
6. CloudFront + S3 Hosting → serves the static site globally.
   ⸻

Tech Stack
• Backend / ETL: Python, AWS Lambda, AWS S3, AWS Athena
• Frontend: Next.js, React, TypeScript, Recharts, TailwindCSS, TanStack React Query
• Hosting: S3 + CloudFront
• Data Format: Parquet (Athena-optimized)

⸻

Folder Structure

.
├── lambda/ # ETL Lambda scripts
├── terraform/ # Infrastructure as code (IAM, Lambda, S3, Athena)
├── dashboard/ # Next.js frontend
│ ├── components/ # React components (PriceChart, hooks, etc.)
│ ├── hooks/ # Custom hooks (useBitcoinData)
│ └── app/ # Next.js pages
└── README.md # Project documentation

⸻

Deployment Steps 1. Add your API endpoint to .env.production:

NEXT_PUBLIC_API_ENDPOINT=https://your-api-endpoint

    2.	Build the Next.js dashboard:

npm install
npm run build

    3.	Export the static site:

npm run build

Note: In Next.js 16+, next export is replaced with output: 'export' in next.config.js.

    4.	Upload the out/ folder to your S3 bucket.
    5.	Create a CloudFront distribution with the S3 bucket as origin.
    6.	Set index.html as the default root object.
    7.	Access your dashboard via the CloudFront URL.

⸻

Usage
• Select the timeframe (7, 30, 90 days) from the dropdown.
• Hover over the chart to see exact price and volume values.
• Data is automatically updated via scheduled Lambda ETL.
• Efficient caching and fetching via TanStack React Query ensures minimal API calls.
⸻

Notes
• Data is partitioned by year/month/day for optimized Athena queries.
• CloudFront ensures fast global delivery.
• Client-side chart rendering prevents SSR issues in Next.js.
