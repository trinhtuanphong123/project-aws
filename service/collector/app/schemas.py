from datetime import datetime, timezone
from typing import Any

import pandas as pd


RAW_COLUMNS = [
    "datetime_utc",
    "zone",
    "power_consumption_total_mw",
    "power_production_total_mw",
    "fossil_free_percentage",
    "renewable_percentage",
    "source",
    "ingested_at_utc",
    "api_response_json",
]


def normalize_record(api_data: dict[str, Any], zone: str, ingested_at_utc: str) -> dict[str, Any]:
    return {
        "datetime_utc": api_data.get("datetime"),
        "zone": api_data.get("zone", zone),
        "power_consumption_total_mw": api_data.get("powerConsumptionTotal"),
        "power_production_total_mw": api_data.get("powerProductionTotal"),
        "fossil_free_percentage": api_data.get("fossilFreePercentage"),
        "renewable_percentage": api_data.get("renewablePercentage"),
        "source": "electricitymaps",
        "ingested_at_utc": ingested_at_utc,
        "api_response_json": api_data,
    }


def records_to_dataframe(records: list[dict[str, Any]]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(columns=RAW_COLUMNS)

    df = pd.DataFrame(records)

    for col in RAW_COLUMNS:
        if col not in df.columns:
            df[col] = None

    df = df[RAW_COLUMNS].copy()

    df["datetime_utc"] = pd.to_datetime(df["datetime_utc"], utc=True, errors="coerce")
    df["ingested_at_utc"] = pd.to_datetime(df["ingested_at_utc"], utc=True, errors="coerce")

    numeric_cols = [
        "power_consumption_total_mw",
        "power_production_total_mw",
        "fossil_free_percentage",
        "renewable_percentage",
    ]

    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["datetime_utc"])
    df = df.drop_duplicates(subset=["datetime_utc", "zone"], keep="last")
    df = df.sort_values(["datetime_utc", "zone"]).reset_index(drop=True)

    return df