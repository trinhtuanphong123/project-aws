import os
from dataclasses import dataclass


@dataclass(frozen=True)
class CollectorConfig:
    aws_region: str
    s3_bucket: str
    s3_raw_prefix: str
    s3_state_prefix: str

    api_key: str
    zone: str

    fetch_lookback_hours: int
    fetch_delay_seconds: float
    request_timeout_seconds: int

    max_records_per_run: int | None


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value.strip()


def _get_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return int(value)


def _get_float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return float(value)


def _get_optional_int_env(name: str) -> int | None:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return None
    return int(value)


def load_config() -> CollectorConfig:
    return CollectorConfig(
        aws_region=os.getenv("AWS_REGION", "ap-southeast-1").strip(),
        s3_bucket=_get_required_env("S3_BUCKET"),
        s3_raw_prefix=os.getenv("S3_RAW_PREFIX", "raw/electricitymaps").strip().strip("/"),
        s3_state_prefix=os.getenv("S3_STATE_PREFIX", "state").strip().strip("/"),
        api_key=_get_required_env("ELECTRICITY_MAPS_API_KEY"),
        zone=os.getenv("ELECTRICITY_MAPS_ZONE", "VN").strip(),
        fetch_lookback_hours=_get_int_env("COLLECTOR_LOOKBACK_HOURS", 48),
        fetch_delay_seconds=_get_float_env("COLLECTOR_FETCH_DELAY_SECONDS", 0.6),
        request_timeout_seconds=_get_int_env("COLLECTOR_REQUEST_TIMEOUT_SECONDS", 20),
        max_records_per_run=_get_optional_int_env("COLLECTOR_MAX_RECORDS_PER_RUN"),
    )