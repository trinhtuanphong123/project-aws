import argparse
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv

from app.config import load_config
from app.client import ElectricityMapsClient
from app.s3_io import S3IO
from app.schemas import normalize_record, records_to_dataframe
from app.time_utils import utc_now_floor_hour, hourly_range, parse_utc_datetime, to_iso_z


def determine_fetch_window(mode: str, start: str | None, end: str | None, s3io: S3IO, zone: str, lookback_hours: int):
    now_hour = utc_now_floor_hour()

    if mode == "range":
        if not start or not end:
            raise RuntimeError("mode=range requires --start and --end")
        start_dt = parse_utc_datetime(start)
        end_dt = parse_utc_datetime(end)
        return start_dt, end_dt

    if mode == "backfill":
        if not start:
            raise RuntimeError("mode=backfill requires --start")
        start_dt = parse_utc_datetime(start)
        end_dt = parse_utc_datetime(end) if end else now_hour - timedelta(hours=1)
        return start_dt, end_dt

    state = s3io.read_state(zone)
    if state and state.get("last_successful_datetime_utc"):
        last_success = parse_utc_datetime(state["last_successful_datetime_utc"])
        start_dt = last_success + timedelta(hours=1)
    else:
        start_dt = now_hour - timedelta(hours=lookback_hours)

    fallback_start = now_hour - timedelta(hours=lookback_hours)
    start_dt = min(start_dt, fallback_start) if state is None else start_dt
    end_dt = now_hour - timedelta(hours=1)

    return start_dt, end_dt


def write_records_grouped_by_day(s3io: S3IO, zone: str, records: list[dict]) -> None:
    df = records_to_dataframe(records)

    if df.empty:
        print("No valid records to write.")
        return

    df["partition_date"] = df["datetime_utc"].dt.date

    for partition_date, part_df in df.groupby("partition_date"):
        part_df = part_df.drop(columns=["partition_date"])
        partition_dt = datetime(
            year=partition_date.year,
            month=partition_date.month,
            day=partition_date.day,
            tzinfo=timezone.utc,
        )

        row_count = s3io.append_raw_partition(zone, partition_dt, part_df)
        key = s3io.raw_partition_key(zone, partition_dt)
        print(f"Wrote partition: s3://{s3io.config.s3_bucket}/{key} rows={row_count}")


def run_collector(mode: str, start: str | None, end: str | None) -> None:
    load_dotenv()

    config = load_config()
    s3io = S3IO(config)
    client = ElectricityMapsClient(config)

    start_dt, end_dt = determine_fetch_window(
        mode=mode,
        start=start,
        end=end,
        s3io=s3io,
        zone=config.zone,
        lookback_hours=config.fetch_lookback_hours,
    )

    timestamps = hourly_range(start_dt, end_dt)

    if config.max_records_per_run is not None:
        timestamps = timestamps[: config.max_records_per_run]

    print(f"Collector mode: {mode}")
    print(f"Zone: {config.zone}")
    print(f"Fetch window: {to_iso_z(start_dt)} -> {to_iso_z(end_dt)}")
    print(f"Timestamps to fetch: {len(timestamps)}")

    if not timestamps:
        print("Nothing to fetch.")
        return

    records = []
    last_successful_dt = None

    for idx, dt in enumerate(timestamps, start=1):
        print(f"[{idx}/{len(timestamps)}] Fetching {to_iso_z(dt)}")

        try:
            data = client.fetch_total_load(dt)
        except Exception as e:
            print(f"Fetch failed at {to_iso_z(dt)}: {repr(e)}")
            continue

        if data is None:
            print(f"No data for {to_iso_z(dt)}")
            time.sleep(config.fetch_delay_seconds)
            continue

        ingested_at = to_iso_z(datetime.now(timezone.utc))
        record = normalize_record(data, zone=config.zone, ingested_at_utc=ingested_at)
        records.append(record)
        last_successful_dt = dt

        time.sleep(config.fetch_delay_seconds)

    write_records_grouped_by_day(s3io, config.zone, records)

    if last_successful_dt is not None:
        s3io.write_state(config.zone, last_successful_dt)
        print(f"Updated state: last_successful_datetime_utc={to_iso_z(last_successful_dt)}")
    else:
        print("No successful fetch. State was not updated.")


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--mode",
        choices=["once", "range", "backfill"],
        default="once",
    )

    parser.add_argument(
        "--start",
        default=None,
        help="UTC datetime, example: 2026-05-01T00:00:00Z",
    )

    parser.add_argument(
        "--end",
        default=None,
        help="UTC datetime, example: 2026-05-21T23:00:00Z",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_collector(mode=args.mode, start=args.start, end=args.end)