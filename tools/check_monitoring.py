"""Validate rules, scrape discovery, and the provisioned dashboard in the lab cluster."""

import json
import time
from urllib.parse import urlencode

from lab import ARTIFACTS, NAMESPACE, forward, monitoring, request, run, smoke


def main():
    monitoring()
    print(run("kubectl", "-n", NAMESPACE, "exec", "deployment/prometheus", "--",
              "promtool", "check", "config", "/etc/prometheus/prometheus.yml").stdout)
    with forward("svc/prometheus", 9090) as base:
        deadline = time.monotonic() + 60
        active = []
        while time.monotonic() < deadline:
            status, body = request(base, "/api/v1/targets")
            if status == 200:
                active = json.loads(body)["data"]["activeTargets"]
                if len(active) == 2 and all(item["health"] == "up" for item in active):
                    break
            time.sleep(2)
        else:
            raise RuntimeError(f"Expected two independently scraped healthy pods, got {active}")
        smoke()
        query = "/api/v1/query?" + urlencode({"query": "sum(release_lab_ready)"})
        status, body = request(base, query)
        result = json.loads(body)
        if status != 200 or float(result["data"]["result"][0]["value"][1]) != 2:
            raise RuntimeError("Readiness metric does not match the two deployed replicas")
    with forward("svc/grafana", 3000) as base:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            status, body = request(base, "/api/dashboards/uid/release-lab")
            if status == 200 and json.loads(body)["dashboard"]["uid"] == "release-lab":
                break
            time.sleep(2)
        else:
            raise RuntimeError("Grafana dashboard was not provisioned")
    report = {"mounted_configuration": "valid", "healthy_scrape_targets": len(active), "grafana_dashboard": "release-lab"}
    (ARTIFACTS / "monitoring.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
