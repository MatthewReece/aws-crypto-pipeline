import os
import json
import requests
import pandas as pd
from datetime import datetime
import awswrangler as wr
import boto3

# -------------------------------
# Configuration
# -------------------------------
BITCOIN_ID = "bitcoin"
S3_BUCKET = os.environ.get("S3_BUCKET")        # e.g., "my-data-lake"
S3_PREFIX = os.environ.get("S3_PREFIX", "raw/coingecko")
API_KEY_SECRET_NAME = os.environ.get("COINGECKO_API_KEY_SECRET_NAME")

# -------------------------------
# Retrieve CoinGecko API key (optional)
# -------------------------------
api_key = None
if API_KEY_SECRET_NAME:
    secrets_client = boto3.client("secretsmanager")
    secret_value = secrets_client.get_secret_value(SecretId=API_KEY_SECRET_NAME)
    api_key = json.loads(secret_value["SecretString"])["COINGECKO_API_KEY"]

headers = {"x-cg-api-key": api_key} if api_key else {}

# -------------------------------
# Function to fetch Bitcoin data for a given date
# -------------------------------
def fetch_bitcoin_data(target_date: str):
    """
    target_date: "YYYY-MM-DD"
    """
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "ids": BITCOIN_ID,
        "order": "market_cap_desc",
        "per_page": 1,
        "page": 1,
        "sparkline": "false",
        "date": target_date  # Optional; not all endpoints support historical
    }

    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    data = response.json()
    if not data:
        raise ValueError(f"No data returned for {target_date}")

    row = data[0]
    df = pd.DataFrame([{
        "id": row["id"],
        "symbol": row["symbol"],
        "name": row["name"],
        "price_usd": float(row["current_price"]),
        "volume_usd": float(row["total_volume"]),
        "market_cap_usd": float(row["market_cap"]),
        "last_updated": row["last_updated"],
        "date": target_date,
        "year": int(target_date[:4]),
        "month": int(target_date[5:7]),
        "day": int(target_date[8:10])
    }])
    return df

# -------------------------------
# Save to S3
# -------------------------------
def save_to_s3(df: pd.DataFrame):
    s3_path = f"s3://{S3_BUCKET}/{S3_PREFIX}"
    wr.s3.to_parquet(
        df=df,
        path=s3_path,
        dataset=True,
        partition_cols=["year", "month", "day"],
        mode="append"
    )
    print(f"Saved data for {df.at[0, 'date']} to S3 at {s3_path}")

# -------------------------------
# Main execution
# -------------------------------
if name == "main":
    # CHANGE THIS DATE for each backfill
    target_date = input("Enter date to backfill (YYYY-MM-DD): ").strip()

    df = fetch_bitcoin_data(target_date)
    print(df[["date", "price_usd", "volume_usd"]])
    save_to_s3(df)