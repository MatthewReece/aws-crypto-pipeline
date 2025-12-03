#!/usr/bin/env python3
"""
Direct backfill: fetch CoinGecko historical daily data and write parquet files directly
to S3 in the same layout as the ETL Lambda:

s3://aws-crypto-pipeline-data-lake-2025/raw/coingecko/{year}/{month}/{day}/...

This bypasses Lambda for backfill, but produces identical files so Athena will read them.
"""

import os
import time
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

import boto3
import requests
import pandas as pd
import awswrangler as wr

# -------- CONFIG ----------
BUCKET = "aws-crypto-pipeline-data-lake-2025"
PREFIX = "raw/coingecko"   # will produce s3://BUCKET/PREFIX/{year}/{month}/{day}/...
COIN_ID = "bitcoin"

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
SECRET_NAME = os.environ.get("COINGECKO_API_KEY_SECRET_NAME")  # name or ARN in Secrets Manager

# Rate-limit settings (CoinGecko free tier ~ 30/minute)
DELAY_BETWEEN_REQUESTS = float(os.environ.get("DELAY_BETWEEN_REQUESTS", "3.0"))
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "6"))
RETRY_BACKOFF_BASE = int(os.environ.get("RETRY_BACKOFF_BASE", "5"))  # seconds multiplier

# Backfill date range settings: either DAYS or START_DATE/END_DATE
DAYS = int(os.environ.get("DAYS", "90"))  # fallback if START/END not provided
START_DATE = os.environ.get("START_DATE")  # YYYY-MM-DD
END_DATE = os.environ.get("END_DATE")      # YYYY-MM-DD

# Logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("backfill")

# ---------------- Helpers ----------------
def get_api_key_from_secrets(secret_name: Optional[str]) -> Optional[str]:
    if not secret_name:
        logger.info("No COINGECKO_API_KEY_SECRET_NAME provided; proceeding without API key.")
        return None
    try:
        sm = boto3.client("secretsmanager", region_name=AWS_REGION)
        resp = sm.get_secret_value(SecretId=secret_name)
        secret_string = resp.get("SecretString", "{}")
        payload = json.loads(secret_string)
        return payload.get("COINGECKO_API_KEY")
    except Exception as e:
        logger.warning(f"Could not read secret {secret_name}: {e}. Proceeding without API key.")
        return None

def fetch_historical_day(date_obj: datetime, api_key: Optional[str]) -> Dict[str, Any]:
    """
    Fetch /coins/{id}/history?date=DD-MM-YYYY
    Returns a dict like {"date": "YYYY-MM-DD", "price_usd": float or None, "volume_usd": float or None, "market_cap_usd": float or None, "last_updated": str or None}
    """
    date_param = date_obj.strftime("%d-%m-%Y")
    url = f"https://api.coingecko.com/api/v3/coins/{COIN_ID}/history"
    headers = {"x-cg-api-key": api_key} if api_key else {}
    params = {"date": date_param, "localization": "false"}

    attempt = 0
    while attempt < MAX_RETRIES:
        attempt += 1
        try:
            logger.info(f"Fetching historical {COIN_ID} for {date_obj.date()} (attempt {attempt})")
            resp = requests.get(url, params=params, headers=headers, timeout=30)
            if resp.status_code == 429:
                wait = RETRY_BACKOFF_BASE * attempt
                logger.warning(f"Rate limited (429). Sleeping {wait}s then retrying.")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            market = data.get("market_data", {}) or {}
            price = market.get("current_price", {}).get("usd")
            volume = market.get("total_volume", {}).get("usd")
            mcap = market.get("market_cap", {}).get("usd")
            last_updated = data.get("last_updated") or market.get("last_updated")
            # Respect delay even after success
            time.sleep(DELAY_BETWEEN_REQUESTS)
            return {
                "date": date_obj.strftime("%Y-%m-%d"),
                "price_usd": price,
                "volume_usd": volume,
                "market_cap_usd": mcap,
                "last_updated": last_updated,
            }
        except requests.RequestException as e:
            backoff = RETRY_BACKOFF_BASE * attempt
            logger.warning(f"Network error: {e}. Backing off {backoff}s (attempt {attempt}).")
            time.sleep(backoff)
        except Exception as e:
            logger.exception(f"Unexpected error fetching {date_obj.date()}: {e}")
            time.sleep(RETRY_BACKOFF_BASE * attempt)

    logger.error(f"Failed to fetch historical for {date_obj.date()} after {MAX_RETRIES} attempts")
    return {"date": date_obj.strftime("%Y-%m-%d"), "price_usd": None, "volume_usd": None, "market_cap_usd": None, "last_updated": None}

def build_dataframe_from_payload(payload: Dict[str, Any], run_date: datetime) -> pd.DataFrame:
    """
    Build a 1-row DataFrame matching your ETL schema.
    Columns: id, symbol, name, price_usd, volume_usd, market_cap_usd, last_updated, date, year, month, day, processing_timestamp
    """
    df = pd.DataFrame([{
        "id": COIN_ID,
        "symbol": "btc",
        "name": "Bitcoin",
        "price_usd": payload.get("price_usd"),
        "volume_usd": payload.get("volume_usd"),
        "market_cap_usd": payload.get("market_cap_usd"),
        "last_updated": payload.get("last_updated") or run_date.isoformat(),
        "date": run_date,  # datetime type (pyarrow/pandas will write this)
        "year": run_date.year,
        "month": run_date.month,
        "day": run_date.day,
        "processing_timestamp": datetime.now(timezone.utc)
    }])
    return df

def write_parquet_to_s3(df: pd.DataFrame):
    """
    Use awswrangler to write into dataset with partitions year/month/day
    Same options as your lambda_etl.py
    """
    s3_path = f"s3://{BUCKET}/{PREFIX}"
    # Use 'overwrite_partitions' so same-day runs replace the partition
    logger.info(f"Writing parquet to {s3_path} partitioned by year/month/day")
    wr.s3.to_parquet(
        df=df,
        path=s3_path,
        dataset=True,
        partition_cols=["year", "month", "day"],
        mode="overwrite_partitions"
    )

# ---------------- Main ----------------
def parse_date_range():
    if START_DATE and END_DATE:
        start = datetime.strptime(START_DATE, "%Y-%m-%d").date()
        end = datetime.strptime(END_DATE, "%Y-%m-%d").date()
    elif START_DATE and not END_DATE:
        start = datetime.strptime(START_DATE, "%Y-%m-%d").date()
        end = datetime.now(timezone.utc).date()
    elif not START_DATE and END_DATE:
        end = datetime.strptime(END_DATE, "%Y-%m-%d").date()
        start = end - timedelta(days=DAYS - 1)
    else:
        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=DAYS - 1)
    return start, end

def main():
    api_key = get_api_key_from_secrets(SECRET_NAME)
    start_date, end_date = parse_date_range()
    logger.info(f"Backfilling from {start_date} to {end_date} (inclusive)")

    curr = start_date
    succeeded = 0
    failed = 0

    while curr <= end_date:
        run_dt = datetime(curr.year, curr.month, curr.day, tzinfo=timezone.utc)
        payload = fetch_historical_day(run_dt, api_key)
        if payload["price_usd"] is None:
            logger.error(f"No price for {curr}; skipping write.")
            failed += 1
        else:
            df = build_dataframe_from_payload(payload, run_dt)
            try:
                write_parquet_to_s3(df)
                logger.info(f"Wrote partition for {curr} price={payload['price_usd']}")
                succeeded += 1
            except Exception as e:
                logger.exception(f"Failed to write parquet for {curr}: {e}")
                failed += 1
        curr = curr + timedelta(days=1)

    logger.info(f"Backfill finished. succeeded={succeeded}, failed={failed}")

if __name__ == "__main__":
    main()