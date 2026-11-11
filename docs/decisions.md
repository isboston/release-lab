# Decisions

## Start with a disposable cluster

kind makes the recovery exercise reproducible without an account, a credit card, or access to an employer's infrastructure. It also fits a hosted CI runner.

The cost is limited realism: a single Docker host cannot demonstrate multi-zone availability, cloud IAM, storage recovery, or production networking. Adding a Terraform directory with an untested cloud deployment would not resolve that gap. A future cloud implementation should be tested against one chosen provider.

## Keep the workload small

The probe service returns a digest of an input string. This provides a business assertion that is stronger than checking an HTTP status. `/healthz` and `/readyz` stay separate from `/work`, so the second drill can demonstrate that a healthy process is not necessarily a working product.

Python's standard-library HTTP server keeps the image and test setup small. It is suitable for this bounded lab workload, not the recommended serving stack for an internet-facing application.

## Capture evidence before rollback

Automatic rollback is useful, but it can remove the failed pods before an operator sees them. The drill deliberately separates upgrade, diagnosis, rollback, and functional verification.

The readiness test also confirms that a new pod is actually running with the injected fault. An image-pull error or a missing cluster must not count as a successful failure drill.

## Check the Service path

`kubectl port-forward svc/probe` selects a pod; it does not exercise ordinary Service routing. The recovery smoke check therefore runs HTTP requests from inside the cluster to the Service DNS name. A port-forward is used only when inspecting a particular failed pod or a dashboard.

Ten requests are a functional sample. They are not a load test, an uninterrupted-availability measurement, or proof that no request was lost during recovery.

## Keep health checks out of the business error ratio

Successful health probes can dominate a quiet service's request count and hide failing business traffic. Only business and unknown-route requests contribute to the request histogram and counter. Unknown paths share a `not_found` label to bound metric cardinality. Query strings are not written to request logs.

Prometheus discovers and scrapes individual pods. Scraping a load-balanced Service address would alternate between independent process counters and produce misleading rates.

## Restrict the generated GitOps configuration

Each generated AppProject allows one repository, one destination namespace, and only the resource kinds used by the chart. Namespace creation remains an explicit operator step. Automatic pruning is off so deleting files does not silently remove a service during the walkthrough.

This bounds what the generated application can deploy. It does not establish a complete multi-tenant security model: Argo CD access control, repository access, cluster administration, and a policy-enforcing CNI still need separate design.

## Keep release ownership unambiguous

Helm owns the local recovery exercise. Argo CD owns services created through the optional GitOps walkthrough. Running a Helm rollback on an Argo-owned application would fight the reconciler; its durable rollback is a Git revert.

## Pin release identities; keep updates reviewable

The generator requires a sha256 image digest. CLI versions and the kind node image are pinned in `tools/versions.json`; downloaded tools are checksum-verified. GitHub Actions are pinned to commit SHAs.

The Python base image and monitoring containers use versioned tags, so their registry contents can change. Dependabot covers the Dockerfile and actions; monitoring/tool upgrades require a reviewed change and another full exercise. Byte-for-byte reproducible builds are not claimed.
