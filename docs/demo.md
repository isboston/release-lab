# Demonstration

Allow time for the first image download and cluster startup. Subsequent runs reuse the local cluster. Commands are run from the repository root.

## Run the two drills

```bash
python tools/lab.py e2e
```

The output identifies each fault and reports its elapsed time. Open `artifacts/e2e.json`, then inspect `artifacts/readiness-failure/resources.txt` to compare the old and new ReplicaSets during the blocked rollout.

The business-failure drill is the useful contrast: the rollout completes because the pod is ready, but a request to `/work` fails. `artifacts/business-failure/application.log` contains those failed requests.

## Inspect the recovered service

```bash
python tools/lab.py smoke
.tools/bin/kubectl --kubeconfig artifacts/lab.kubeconfig -n release-lab get pods
```

The functional check verifies both version `good` and the digest returned for a known input. Pod readiness alone is not the result being checked.

## Inspect monitoring

```bash
python tools/check_monitoring.py
.tools/bin/kubectl --kubeconfig artifacts/lab.kubeconfig -n release-lab \
  port-forward --address 127.0.0.1 svc/grafana 3000:3000
```

Open `http://127.0.0.1:3000/d/release-lab`. The dashboard separates business errors from health-probe traffic and shows readiness per pod. It starts collecting when monitoring is installed; it cannot show earlier drills retroactively. To observe a drill, install monitoring first and run `e2e` again.

## Inspect the code behind the result

- `tools/lab.py`: why an image-pull error must not count as the expected readiness failure; why smoke traffic uses the Service network path.
- `charts/service/templates/deployment.yaml`: how `maxUnavailable: 0` and readiness work together.
- `monitoring/stack.yaml`: per-pod scrape discovery and the minimum-traffic condition on the error alert.
- `docs/gitops.md`: why recovery for an Argo-owned application belongs in Git.

Cleanup: `python tools/lab.py down`.
