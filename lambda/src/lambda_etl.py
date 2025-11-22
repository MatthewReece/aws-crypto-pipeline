import os
import logging
from datetime import datetime
import json

import awswrangler as wr
import pandas as pd
import requests
import boto3

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Hardcode the coin ID for Bitcoin
BITCOIN_ID = "bitcoin"

def fetch_single_coin_market_data(coin_id: str, api_key: str = None) -> pd.DataFrame:
    """
    Fetches market data for a single, specified cryptocurrency ID from CoinGecko.

    Args:
        coin_id (str): The unique CoinGecko ID of the cryptocurrency (e.g., "bitcoin").
        api_key (str, optional): The CoinGecko API key. Defaults to None.

    Returns:
        pd.DataFrame: A DataFrame containing the market data for the specified coin.
    """
    logger.info(f"Fetching market data for coin ID: {coin_id}")
    api_url = "https://api.coingecko.com/api/v3/coins/markets"
    
    # Use the 'ids' parameter to filter for only the target coin
    params = {
        "vs_currency": "usd",
        "ids": coin_id,
        "order": "market_cap_desc", 
        "per_page": 1,              # Request only one result
        "page": 1,
        "sparkline": "false",
    }
    
    headers = {}
    if api_key:
        # Note: The free API often requires this key header or parameter if provided.
        headers["x-cg-demo-api-key"] = api_key
        
    try:
        response = requests.get(api_url, params=params, headers=headers)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)
        data = response.json()
        
        if not data:
            logger.warning(f"API returned no data for coin ID: {coin_id}")
            return pd.DataFrame() # Return empty DataFrame if nothing found
            
        logger.info(f"Successfully fetched data for {data[0].get('name', 'N/A')}.")
        return pd.DataFrame(data)
    
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed for {coin_id}: {e}")
        raise

def lambda_handler(event, context):
    """
    The main entry point for the AWS Lambda function.

    It fetches Bitcoin market data, adds a timestamp, and stores it in S3.
    """
    try:
        # Get environment variables
        s3_bucket = os.environ["S3_BUCKET"]
        s3_prefix = os.environ["S3_PREFIX"]
        file_format = os.environ.get("FILE_FORMAT", "parquet")
        api_key_secret_name = os.environ.get("COINGECKO_API_KEY_SECRET_NAME")

        api_key = None
        if api_key_secret_name:
            logger.info(f"Fetching API key from Secrets Manager secret: {api_key_secret_name}")
            try:
                # Initialize Secrets Manager client and retrieve the secret string
                secrets_client = boto3.client("secretsmanager")
                get_secret_value_response = secrets_client.get_secret_value(
                    SecretId=api_key_secret_name
                )
                secret = get_secret_value_response["SecretString"]
                # The secret value is stored as a JSON string, so we parse it
                api_key = json.loads(secret)["COINGECKO_API_KEY"]
                logger.info("Successfully retrieved CoinGecko API key.")
            except Exception as e:
                logger.warning(f"Could not retrieve API key from Secrets Manager: {e}. Proceeding without API key.")

        # ETL Process
        df = fetch_single_coin_market_data(BITCOIN_ID, api_key=api_key)

        if df.empty:
            logger.error("No data frame returned for Bitcoin. Aborting load step.")
            return {"statusCode": 204, "body": "No data returned from API."}

        # Add a processing timestamp
        df["processing_timestamp"] = datetime.utcnow()

        # Determine the date for partitioning. Use date from event if provided, otherwise use current UTC date.
        if "date" in event:
            logger.info(f"Using historical date from event: {event['date']}")
            run_date = datetime.strptime(event["date"], "%Y-%m-%d")
        else:
            logger.info("Using current UTC date for partitioning.")
            run_date = datetime.utcnow()

        # Generate partition columns for a data lake structure
        partition_cols = ["year", "month", "day"]
        df["year"] = run_date.year
        df["month"] = run_date.month
        df["day"] = run_date.day

        # Update the S3 prefix to be specific to Bitcoin (optional, but good practice)
        # We'll stick to the environment S3_PREFIX for now, but ensure the path works.
        s3_path = f"s3://{s3_bucket}/{s3_prefix}"

        logger.info(f"Writing data for {BITCOIN_ID} to S3 at {s3_path} in {file_format} format.")

        # Use AWS Data Wrangler to write the DataFrame to S3
        result = wr.s3.to_parquet(
            df=df,
            path=s3_path,
            dataset=True,
            partition_cols=partition_cols,
            mode="overwrite_partitions",
        )

        logger.info(f"Successfully wrote {len(result['paths'])} file(s) to S3.")
        return {"statusCode": 200, "body": f"Data successfully written to {result['paths'][0]}"}

    except Exception as e:
        logger.error(f"An error occurred in lambda_handler: {e}")
        return {"statusCode": 500, "body": f"An error occurred: {str(e)}"}