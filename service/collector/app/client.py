import time
from typing import Any
from urllib import response

from numpy import record
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import CollectorConfig
from app.time_utils import to_api_datetime


class ElectricityMapsClient:
    def __init__(self, config: CollectorConfig):
        self.config = config
        self.base_url = "https://api.electricitymaps.com/v3/total-load/past"
        self.session = requests.Session()
        self.session.headers.update({"auth-token": config.api_key})

    @retry(
        retry=retry_if_exception_type((requests.Timeout, requests.ConnectionError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=20),
        reraise=True,
    )
    def fetch_total_load(self, dt_utc) -> dict | None:
        params = {
            "zone": self.config.zone,
            "datetime": to_api_datetime(dt_utc),
            "temporalGranularity": "hourly",
        }

        response = self.session.get(
            self.base_url,
            params=params,
            timeout=self.config.request_timeout_seconds,
        )

        if response.status_code == 401:
            raise RuntimeError("Unauthorized API key")

        if response.status_code == 429:
            time.sleep(60)
            return None

        response.raise_for_status()

        data = response.json()

        # DEBUG (rất nên giữ lúc dev)
        print("RAW API RESPONSE:", data)

        value = data.get("value")

        if value is None:
            return None

        return {
            "datetime": data.get("datetime"),
            "zone": data.get("zone"),
            "powerConsumptionTotal": value,
            "powerProductionTotal": None,
            "fossilFreePercentage": None,
            "renewablePercentage": None,
        }