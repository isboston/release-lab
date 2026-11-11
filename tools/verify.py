"""Run checks that do not need Docker or a Kubernetes cluster."""

import json
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    suffix = ".exe" if os.name == "nt" else ""
    checks = [
        ("unit and chart tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]),
        ("helm lint", [str(ROOT / ".tools/bin" / ("helm" + suffix)), "lint", "charts/service", "--strict"]),
        ("alert rule evaluation", [sys.executable, "tools/check_rules.py"]),
        ("workflow validation", [str(ROOT / ".tools/bin" / ("actionlint" + suffix)), "-shellcheck=", "-pyflakes=", ".github/workflows/ci.yaml", ".github/workflows/publish.yaml", ".github/workflows/gitops.yaml"]),
    ]
    report = {"recorded_at": datetime.now(timezone.utc).isoformat(), "checks": [],
              "scope": "No cluster or container runtime used. Kubernetes recovery is checked by the separate integration job."}
    directory = ROOT / "artifacts"
    directory.mkdir(exist_ok=True)
    passed = True
    for name, command in checks:
        started = time.monotonic()
        result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=120)
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
        report["checks"].append({"name": name, "passed": result.returncode == 0,
                                 "elapsed_seconds": round(time.monotonic() - started, 2)})
        passed = passed and result.returncode == 0
    (directory / "verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
