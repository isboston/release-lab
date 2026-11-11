# Validation record

Recorded on 2026-11-11. Results below describe checks actually executed, not planned coverage.

| Check | Result | Environment |
| --- | --- | --- |
| HTTP behavior, service generator, chart rendering and invalid inputs | Passed: 19 tests | Windows, Python 3.12.14 |
| Helm lint | Passed | Helm 4.3.1 |
| GitHub Actions workflow validation | Passed | actionlint 1.7.12 |
| Prometheus rule syntax | Passed: 2 rules | promtool 3.16.0 |
| Prometheus alert behavior | Passed: 3 scenarios | promtool 3.16.0 |
| Kubernetes recovery drills | Not yet executed | Requires Docker with Linux containers |
| Live Prometheus/Grafana checks | Not yet executed | Requires the lab cluster |
| Optional Argo CD walkthrough | Not yet executed | Requires a reachable Git repository and image |

The development machine has no Docker daemon. The repository contains a hosted CI job for the cluster checks, but configuration is not evidence of a completed run.

Reproduce the local checks with `python tools/verify.py`. Its machine-readable result is written to `artifacts/verification.json` (ignored by Git). The integration job writes `artifacts/e2e.json`, `artifacts/monitoring.json`, and diagnostic logs.

Update this record with the corresponding CI run URL after the first full pass. Do not turn the pending entries into success claims based only on static validation.
