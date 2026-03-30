import requests
from datetime import datetime, timedelta

PROMETHEUS_URL = "http://localhost:9090"


class PrometheusClient:
    def query_range(self, metric: str, hours: int = 1) -> list:
        end = datetime.now()
        start = end - timedelta(hours=hours)
        params = {
            "query": metric,
            "start": start.isoformat() + "Z",
            "end": end.isoformat() + "Z",
            "step": "15s",
        }
        try:
            resp = requests.get(
                f"{PROMETHEUS_URL}/api/v1/query_range", params=params, timeout=5
            )
            resp.raise_for_status()
            return resp.json().get("data", {}).get("result", [])
        except requests.RequestException:
            return []
