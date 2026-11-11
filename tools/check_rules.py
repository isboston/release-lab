"""Run the real Prometheus rule evaluator against synthetic request series."""

from pathlib import Path
import shutil
import subprocess

import yaml

from lab import ROOT, binary


def main():
    directory = ROOT / "artifacts/promtool"
    directory.mkdir(parents=True, exist_ok=True)
    stack = list(yaml.safe_load_all((ROOT / "monitoring/stack.yaml").read_text()))
    config = next(item for item in stack if item["kind"] == "ConfigMap" and item["metadata"]["name"] == "prometheus-config")
    (directory / "rules.yml").write_text(config["data"]["rules.yml"], encoding="utf-8")
    shutil.copyfile(ROOT / "monitoring/alerts.test.yaml", directory / "alerts.test.yaml")
    for args in [("check", "rules", "rules.yml"), ("test", "rules", "alerts.test.yaml")]:
        subprocess.run([binary("promtool"), *args], cwd=directory, check=True, timeout=30)


if __name__ == "__main__":
    main()
