import io
import json
from datetime import datetime, timezone
from typing import Any

import boto3
import botocore
import pandas as pd

from app.config import CollectorConfig
from app.time_utils import to_iso_z, parse_utc_datetime


class S3IO:
    def __init__(self, config: CollectorConfig):
        self.config = config
        self.s3 = boto3.client("s3", region_name=config.aws_region)

    def object_exists(self, key: str) -> bool:
        try:
            self.s3.head_object(Bucket=self.config.s3_bucket, Key=key)
            return True
        except botocore.exceptions.ClientError as e:
            status = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if status == 404:
                return False
            raise

    def read_json(self, key: str) -> dict[str, Any] | None:
        try:
            obj = self.s3.get_object(Bucket=self.config.s3_bucket, Key=key)
            return json.loads(obj["Body"].read().decode("utf-8"))
        except botocore.exceptions.ClientError as e:
            status = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if status == 404:
                return None
            raise

    def write_json(self, key: str, data: dict[str, Any]) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.s3.put_object(
            Bucket=self.config.s3_bucket,
            Key=key,
            Body=body,
            ContentType="application/json",
        )

    def read_parquet(self, key: str) -> pd.DataFrame:
        obj = self.s3.get_object(Bucket=self.config.s3_bucket, Key=key)
        data = obj["Body"].read()
        return pd.read_parquet(io.BytesIO(data))

    def write_parquet(self, key: str, df: pd.DataFrame) -> None:
        buffer = io.BytesIO()
        df.to_parquet(buffer, index=False, engine="pyarrow")
        buffer.seek(0)

        self.s3.put_object(
            Bucket=self.config.s3_bucket,
            Key=key,
            Body=buffer.getvalue(),
            ContentType="application/octet-stream",
        )

    def raw_partition_key(self, zone: str, dt: datetime) -> str:
        dt = dt.astimezone(timezone.utc)
        return (
            f"{self.config.s3_raw_prefix}/"
            f"zone={zone}/"
            f"year={dt.year:04d}/"
            f"month={dt.month:02d}/"
            f"day={dt.day:02d}/"
            f"vn_load_{dt.year:04d}{dt.month:02d}{dt.day:02d}.parquet"
        )

    def state_key(self, zone: str) -> str:
        return f"{self.config.s3_state_prefix}/collector_state_{zone}.json"

    def read_state(self, zone: str) -> dict[str, Any] | None:
        return self.read_json(self.state_key(zone))

    def write_state(self, zone: str, last_successful_datetime_utc: datetime) -> None:
        now = datetime.now(timezone.utc)

        data = {
            "zone": zone,
            "last_successful_datetime_utc": to_iso_z(last_successful_datetime_utc),
            "updated_at_utc": to_iso_z(now),
        }

        self.write_json(self.state_key(zone), data)

    def append_raw_partition(self, zone: str, partition_dt: datetime, new_df: pd.DataFrame) -> int:
        key = self.raw_partition_key(zone, partition_dt)

        if self.object_exists(key):
            old_df = self.read_parquet(key)
            merged = pd.concat([old_df, new_df], ignore_index=True)
        else:
            merged = new_df.copy()

        merged["datetime_utc"] = pd.to_datetime(merged["datetime_utc"], utc=True, errors="coerce")
        merged = merged.dropna(subset=["datetime_utc"])
        merged = merged.drop_duplicates(subset=["datetime_utc", "zone"], keep="last")
        merged = merged.sort_values(["datetime_utc", "zone"]).reset_index(drop=True)

        self.write_parquet(key, merged)
        return len(merged)