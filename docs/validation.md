# Validation record

Recorded on 2026-11-11. Results below describe checks actually executed, not planned coverage.

| Check | Result | Environment |
| --- | --- | --- |
| HTTP behavior, service generator, chart rendering and invalid inputs | Passed: 19 tests | Windows, Python 3.12.14 |
| Helm lint | Passed | Helm 4.3.1 |
| GitHub Actions workflow validation | Passed | actionlint 1.7.12 |
| Prometheus rule syntax | Passed: 2 rules | promtool 3.16.0 |
| Prometheus alert behavior | Passed: 3 scenarios | promtool 3.16.0 |
| Kubernetes recovery drills | Passed: readiness and business failures, followed by functional recovery | GitHub-hosted Ubuntu 24.04, kind 0.33.0 / Kubernetes 1.37.0 |
| Live Prometheus/Grafana checks | Passed: two healthy scrape targets and the provisioned dashboard | Same CI cluster |
| Image publication | Passed; anonymous pull verified | GHCR, linux/amd64 |
| Argo CD synchronization and replica drift correction | Passed: synchronized, healthy, functional request verified before and after drift correction | Argo CD 3.6.1 on a separate kind cluster |

The local development machine has no Docker daemon; the cluster checks were executed on a GitHub-hosted Linux runner. [Successful delivery and publishing run](https://github.com/isboston/release-lab/actions/runs/42998944679), tested commit `66b2e28f250c162109689ae46a07a632b34048a5`.

The [delivery checks also passed on the GitOps-enabled revision](https://github.com/isboston/release-lab/actions/runs/42999887537), commit `25080eb5d4d5bc97ba116811bdc9318386012cdf`.

Machine-readable results copied from that run: [recovery](evidence/42998944679/e2e.json), [monitoring](evidence/42998944679/monitoring.json). In this single exercise, measured recovery took 1.33 seconds for the readiness regression and 6.75 seconds for the business regression. These are lab observations, not a benchmark or service-level objective.

Published image: `ghcr.io/isboston/release-lab@sha256:e504ada48ade6e14b5ca21e97e920a3d2de827fe746ef4055874c0c8be7dc8dd`.

[Successful GitOps run](https://github.com/isboston/release-lab/actions/runs/42999897248), synchronized commit `25080eb5d4d5bc97ba116811bdc9318386012cdf`. The [captured result](evidence/42999897248/gitops.json) records a functional service and automatic correction of a manual replica-count change. The observed correction-and-verification interval was 3.92 seconds in this run. This check does not exercise a Git revert or multi-tenant access control.

Reproduce the local checks with `python tools/verify.py`. Its machine-readable result is written to `artifacts/verification.json` (ignored by Git). The integration job writes `artifacts/e2e.json`, `artifacts/monitoring.json`, and diagnostic logs.

The first cluster run exposed a race between rollback completion and Service traffic convergence. Its diagnostics and the resulting change are described in [decisions.md](decisions.md).
