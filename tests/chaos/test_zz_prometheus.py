"""
Scenario S6: Verify Prometheus recorded 5xx metrics after chaos tests.

Note: This test runs last in the suite. It queries Prometheus for the 5xx metric increase
on job="employee" over the last 30 minutes. If executed in isolation without preceding
chaos scenarios (where no 5xx errors occurred), it may fail as expected.
"""

import os
import time
import httpx
import pytest

PROMETHEUS_URL = os.getenv("CHAOS_PROMETHEUS_URL", "http://localhost:9090")


@pytest.mark.chaos
def test_prometheus_shows_5xx_after_chaos():
    # 5xx PromQL query derived from ems-overview.json using 30m window
    query_reqs = 'increase(http_requests_total{status=~"5..", job="employee"}[30m])'
    query_dur = 'increase(http_request_duration_seconds_count{status=~"5..", job="employee"}[30m])'

    # Retry up to 3 x scrape_interval (3 * 5s = 15s)
    max_wait = 15.0
    start_time = time.time()
    found_5xx = False
    metric_val = 0.0

    with httpx.Client(timeout=5.0) as client:
        while time.time() - start_time < max_wait:
            for q in [query_reqs, query_dur]:
                try:
                    resp = client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": q})
                    if resp.status_code == 200:
                        data = resp.json()
                        results = data.get("data", {}).get("result", [])
                        for res in results:
                            metric_job = res.get("metric", {}).get("job")
                            if metric_job == "employee":
                                val_str = res.get("value", [None, "0"])[1]
                                val = float(val_str)
                                if val > 0:
                                    found_5xx = True
                                    metric_val = val
                                    break
                except Exception:
                    pass
                if found_5xx:
                    break
            if found_5xx:
                break
            time.sleep(2.0)

    print(f"\n[S6 Prometheus Metric] Observed 5xx increase for job='employee': {metric_val}")
    assert found_5xx, (
        f"Expected 5xx request increase > 0 for job='employee' over last 30m in Prometheus at {PROMETHEUS_URL}. "
        f"Make sure chaos tests S1/S2 ran before S6."
    )
