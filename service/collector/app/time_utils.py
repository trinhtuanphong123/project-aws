from datetime import datetime, timezone, timedelta


def utc_now_floor_hour() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(minute=0, second=0, microsecond=0)


def parse_utc_datetime(value: str) -> datetime:
    value = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def to_api_datetime(dt: datetime) -> str:
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M")


def to_iso_z(dt: datetime) -> str:
    dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def hourly_range(start_inclusive: datetime, end_inclusive: datetime) -> list[datetime]:
    start = start_inclusive.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    end = end_inclusive.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)

    if end < start:
        return []

    out = []
    cur = start
    while cur <= end:
        out.append(cur)
        cur += timedelta(hours=1)
    return out