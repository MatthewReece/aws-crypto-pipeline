// index.js
const {
  AthenaClient,
  StartQueryExecutionCommand,
  GetQueryExecutionCommand,
  GetQueryResultsCommand,
} = require("@aws-sdk/client-athena");

const client = new AthenaClient({ region: process.env.AWS_REGION || "us-east-1" });

const DATABASE = process.env.ATHENA_DATABASE;
const OUTPUT_S3 = process.env.ATHENA_OUTPUT_S3;

async function waitForSuccess(executionId) {
  while (true) {
    const statusResp = await client.send(
      new GetQueryExecutionCommand({ QueryExecutionId: executionId })
    );

    const state = statusResp.QueryExecution?.Status?.State || "UNKNOWN";
    const reason = statusResp.QueryExecution?.Status?.StateChangeReason;

    if (state === "SUCCEEDED") return;
    if (state === "FAILED" || state === "CANCELLED" || state === "UNKNOWN") {
      // include Athena reason if present
      const r = reason ? `: ${reason}` : "";
      throw new Error(`Athena query failed: ${state}${r}`);
    }

    // poll
    await new Promise((res) => setTimeout(res, 500));
  }
}

async function runQuery(sql) {
  // start
  const startResp = await client.send(
    new StartQueryExecutionCommand({
      QueryString: sql,
      QueryExecutionContext: { Database: DATABASE },
      ResultConfiguration: { OutputLocation: OUTPUT_S3 },
    })
  );

  const executionId = startResp.QueryExecutionId;
  if (!executionId) throw new Error("No QueryExecutionId returned from StartQueryExecution");

  // wait for completion (or failure)
  await waitForSuccess(executionId);

  // fetch results
  const resultsResp = await client.send(
    new GetQueryResultsCommand({ QueryExecutionId: executionId })
  );

  const rows = resultsResp.ResultSet?.Rows || [];
  if (rows.length <= 1) return [];

  const headers = (rows[0].Data || []).map((col) => col?.VarCharValue || "");

  const data = rows.slice(1).map((row) => {
    const obj = {};
    (row.Data || []).forEach((col, i) => {
      const key = headers[i] || "";
      if (!key) return;
      obj[key] = col?.VarCharValue || "";
    });

    return {
      date: obj.date || "",
      price_usd: Number(obj.price_usd || 0),
      volume_usd: Number(obj.volume_usd || 0),
    };
  });

  return data;
}

exports.handler = async (event) => {
  try {
    // pull days param (string) -> number
    const raw = event.queryStringParameters?.days;
    let days = Number(raw || 90);

    if (!Number.isFinite(days) || days <= 0) days = 90;

    // clamp to the allowed set to avoid malicious/accidental huge queries
    const allowed = [7, 30, 90];
    if (!allowed.includes(days)) {
      // if the client passed e.g. 14, fallback to nearest allowed (30)
      // or simply default to 90 — choose behavior you prefer
      days = 90;
    }

    // IMPORTANT: cast date to DATE to avoid timestamp/string mismatches
    const sql = `
      SELECT
        CAST(date AS DATE) AS date,
        AVG(price_usd) AS price_usd,
        SUM(volume_usd) AS volume_usd
      FROM crypto_bitcoin_daily
      WHERE CAST(date AS DATE) >= date_add('day', -${days}, current_date)
      GROUP BY CAST(date AS DATE)
      ORDER BY CAST(date AS DATE) ASC
    `;

    const data = await runQuery(sql);

    return {
      statusCode: 200,
      headers: {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
      },
      body: JSON.stringify({ data }),
    };
  } catch (err) {
    console.error("athena-query error:", err);
    return {
      statusCode: 500,
      body: JSON.stringify({ error: err.message || String(err) }),
    };
  }
};