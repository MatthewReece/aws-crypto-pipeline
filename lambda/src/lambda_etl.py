# lambda_etl.py
import os
import logging
from datetime import datetime
import json

import awswrangler as wr
import pandas as pd
import requests
import boto3

# -------------------------------
# Logging
# -------------------------------
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# -------------------------------
# Constants
# -------------------------------
BITCOIN_ID = "bitcoin"

# -------------------------------
# Fetch current market data from CoinGecko
# -------------------------------
def fetch_single_coin_market_data(coin_id: str, api_key: str = None) -> pd.DataFrame:
    """
    Fetches current market data for a single cryptocurrency from CoinGecko and maps it to our schema.
    """
    logger.info(f"Fetching market data for coin ID: {coin_id}")
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "ids": coin_id,
        "order": "market_cap_desc",
        "per_page": 1,
        "page": 1,
        "sparkline": "false"
    }
    headers = {"x-cg-api-key": api_key} if api_key else {}

    resp = requests.get(url, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if not data:
        logger.warning(f"No data returned for {coin_id}")
        return pd.DataFrame()

    df = pd.DataFrame(data)
    df = df.assign(
        price_usd=df["current_price"].astype(float),
        volume_usd=df["total_volume"].astype(float),
        market_cap_usd=df["market_cap"].astype(float)
    )
    df = df[["id", "symbol", "name", "price_usd", "volume_usd", "market_cap_usd", "last_updated"]]
    return df

# -------------------------------
# Lambda handler
# -------------------------------
def lambda_handler(event, context):
    try:
        # Environment variables
        s3_bucket = os.environ["S3_BUCKET"]
        s3_prefix = os.environ["S3_PREFIX"]
        api_key_secret_name = os.environ.get("COINGECKO_API_KEY_SECRET_NAME")

        # Retrieve API key from Secrets Manager (optional)
        api_key = None
        if api_key_secret_name:
            try:
                secrets_client = boto3.client("secretsmanager")
                secret_value = secrets_client.get_secret_value(SecretId=api_key_secret_name)
                api_key = json.loads(secret_value["SecretString"]).get("COINGECKO_API_KEY")
                logger.info("Retrieved CoinGecko API key from Secrets Manager")
            except Exception as e:
                logger.warning(f"Could not retrieve API key: {e}. Proceeding without key.")

        # Determine run date
        if "date" in event:
            run_date = datetime.strptime(event["date"], "%Y-%m-%d")
            logger.info(f"Backfill mode for {event['date']}")
        else:
            run_date = datetime.utcnow()
            logger.info("Live mode")

        # If historical data provided, STRICTLY use it (no fallback)
        if "historical_data" in event:
            hist = event["historical_data"]
            price = hist.get("price_usd")
            volume = hist.get("volume_usd")
            market_cap = hist.get("market_cap_usd")

            # Validate required fields
            if price is None:
                logger.error(f"Historical data missing price for {event.get('date')}. Aborting write.")
                return {"statusCode": 400, "body": "Historical data missing price_usd"}

            # Build dataframe from historical data (single row)
            df = pd.DataFrame([{
                "id": "bitcoin",
                "symbol": "btc",
                "name": "Bitcoin",
                "price_usd": float(price),
                "volume_usd": float(volume) if volume is not None else None,
                "market_cap_usd": float(market_cap) if market_cap is not None else None,
                "last_updated": f"{event.get('date')}T00:00:00Z"
            }])

        else:
            # Live mode: fetch current snapshot
            df = fetch_single_coin_market_data(BITCOIN_ID, api_key=api_key)
            if df.empty:
                logger.error("No data returned from CoinGecko in live mode. Aborting.")
                return {"statusCode": 204, "body": "No data returned from API"}

        # Add date and partition columns
        # Store `date` as date (not full timestamp) to match Athena DATE semantics
        df["date"] = pd.to_datetime(run_date).normalize()
        df["year"] = int(run_date.year)
        df["month"] = int(run_date.month)
        df["day"] = int(run_date.day)
        df["processing_timestamp"] = datetime.utcnow()

        # S3 path
        s3_path = f"s3://{s3_bucket}/{s3_prefix}"

        # Write to S3 using awswrangler (overwrite partition for that day)
        result = wr.s3.to_parquet(
            df=df,
            path=s3_path,
            dataset=True,
            partition_cols=["year", "month", "day"],
            mode="overwrite_partitions"
        )

        logger.info(f"Wrote {len(result.get('paths', []))} files to {s3_path}")
        return {"statusCode": 200, "body": f"Data written to {result.get('paths', [s3_path])[0]}"}

    except Exception as e:
        logger.exception(f"Error in lambda_handler: {e}")
        return {"statusCode": 500, "body": str(e)}