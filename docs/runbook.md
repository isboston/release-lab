# Failed release: inspect, recover, verify

This runbook describes the local Helm-owned lab. For an Argo CD-managed service, use the Git revert procedure in [gitops.md](gitops.md).

## First look

All commands below use the repository's local kubeconfig.

```bash
.tools/bin/kubectl --kubeconfig artifacts/lab.kubeconfig -n release-lab get deploy,rs,pods
.tools/bin/kubectl --kubeconfig artifacts/lab.kubeconfig -n release-lab describe deployment probe
.tools/bin/kubectl --kubeconfig artifacts/lab.kubeconfig -n release-lab get events --sort-by=.metadata.creationTimestamp
.tools/bin/helm --kubeconfig artifacts/lab.kubeconfig -n release-lab history probe
```

Look for the new pod's image, `APP_VERSION`, readiness failures, and the number of available replicas. Do not assume every timed-out upgrade is the expected injected failure: image-pull, scheduling, and startup failures need different fixes.

## Readiness regression

The drill sets `READINESS_MODE=fail`. The new process is alive, but readiness returns 503. `maxUnavailable: 0` keeps the previous ready replicas while the new version fails to become ready.

Expected evidence after `python tools/lab.py e2e`:

- `artifacts/readiness-failure/pods.txt`: readiness probe failures for the new version;
- `resources.txt`: old and new ReplicaSets during the blocked rollout;
- `application.log`: 503 responses from the readiness endpoint;
- `artifacts/e2e.json`: a passing result only after functional recovery has been checked.

## Business regression

The drill sets `WORK_MODE=fail`. Readiness still succeeds, so a completed rollout is possible while the product endpoint fails. Inspect the HTTP response and business request metrics instead of relying only on pod status.

The `BusinessRequestsFailing` rule requires a sustained error ratio above 5% and at least 20 requests in its two-minute window. The short recovery drill does not wait for that alert to fire; deterministic Prometheus rule tests exercise the alert separately.

## Manual recovery

Find the last known working revision in Helm history. Replace `REVISION` with its number:

```bash
.tools/bin/helm --kubeconfig artifacts/lab.kubeconfig -n release-lab \
  rollback probe REVISION --wait --timeout 120s
python tools/lab.py smoke
```

The smoke check expects version `good`, verifies the response digest, and sends requests through the Service. A successful `helm rollback` alone is not the completion criterion.

For the initial local release, the recorded good revision belongs to this disposable exercise. Do not transfer these revision numbers to another cluster.

## If a check fails unexpectedly

Keep `artifacts/unexpected-failure` and the corresponding CI run. Inspect events before retrying. A failure caused by a missing image, permission, or cluster must remain a failed check.

The lab has no stateful workload. Rolling back a database migration or recovering persistent data would require an application-specific plan that this exercise does not provide.
