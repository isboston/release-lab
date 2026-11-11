# Optional GitOps walkthrough

The local recovery drill works without publishing this repository. This walkthrough requires a reachable Git repository, a published probe image, and an Argo CD installation. It has a separate validation status from the Helm exercise.

## 1. Publish the image

After the repository is on GitHub, run the manual **Publish probe image** workflow from the default branch. Copy the `ghcr.io/...@sha256:...` reference from its summary. For the simplest public demo, make the resulting package publicly readable in GHCR; otherwise configure image-pull credentials in the destination namespace separately.

Do not use a guessed digest or `latest`. The generator rejects mutable tags.

## 2. Generate a service

Replace the repository and digest with real values:

```bash
python tools/new_service.py payments \
  --owner platform-team \
  --repo https://github.com/YOUR_ACCOUNT/release-lab.git \
  --image ghcr.io/YOUR_ACCOUNT/release-lab@sha256:YOUR_IMAGE_DIGEST
```

The output is `services/payments/`:

| File | Purpose |
| --- | --- |
| `values.json` | Image identity, owner and version consumed by the shared chart |
| `namespace.json` | Namespace with the restricted Pod Security standard |
| `project.json` | Repository, namespace and resource-kind boundary |
| `application.json` | Argo CD application tracking the chart and values in Git |

Review and commit these files to `main`. The values path must exist on the remote branch before Argo CD can render it. Re-running the generator refuses to overwrite the directory.

## 3. Install Argo CD in the disposable lab

If Argo CD is not already present, the pinned lab version is v3.6.1:

```bash
.tools/bin/kubectl --kubeconfig artifacts/lab.kubeconfig create namespace argocd
.tools/bin/kubectl --kubeconfig artifacts/lab.kubeconfig -n argocd apply \
  --server-side --force-conflicts \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/v3.6.1/manifests/install.yaml
.tools/bin/kubectl --kubeconfig artifacts/lab.kubeconfig -n argocd \
  rollout status deployment/argocd-repo-server --timeout=180s
.tools/bin/kubectl --kubeconfig artifacts/lab.kubeconfig -n argocd \
  rollout status statefulset/argocd-application-controller --timeout=180s
```

This is the upstream non-HA installation, scoped to the disposable local cluster. The Argo CD API is not exposed publicly by this walkthrough.

## 4. Apply the reviewed boundaries and application

```bash
.tools/bin/kubectl --kubeconfig artifacts/lab.kubeconfig apply -f services/payments/namespace.json
.tools/bin/kubectl --kubeconfig artifacts/lab.kubeconfig apply -f services/payments/project.json
.tools/bin/kubectl --kubeconfig artifacts/lab.kubeconfig apply -f services/payments/application.json
.tools/bin/kubectl --kubeconfig artifacts/lab.kubeconfig -n argocd get application payments -o yaml
.tools/bin/kubectl --kubeconfig artifacts/lab.kubeconfig -n payments get pods
```

Wait for the Application to report `Synced` and `Healthy`. Check its events if the repository is private, a package cannot be pulled, or the values file is absent. Private repository credentials belong in Argo CD's credential mechanism, not in these generated files.

## 5. Deliver and recover through Git

Change the image digest in `values.json` through a pull request. Once merged, Argo CD reconciles the desired state. If a bad release is merged, revert the commit in Git and verify synchronization, workload readiness, and a functional request.

Do not use `helm rollback` for this application. Automatic self-healing would reconcile it back to the Git version. Automatic pruning is disabled; removing the service later is an explicit lifecycle action.

The optional GitOps service is in its own namespace. The lab dashboard currently discovers only the `probe` release in `release-lab`; extend discovery and access boundaries deliberately before presenting it as monitoring all generated services.

References: [Argo CD getting started](https://argo-cd.readthedocs.io/en/stable/getting_started/), [automated sync](https://argo-cd.readthedocs.io/en/stable/user-guide/auto_sync/), [project restrictions](https://argo-cd.readthedocs.io/en/stable/user-guide/projects/).
