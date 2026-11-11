# Five-minute walkthrough

## 1. State the problem

"A successful Kubernetes rollout does not prove that the application works. This lab separates readiness checks from functional checks and verifies recovery after both kinds of failure."

## 2. Show one implementation detail

Open `tools/lab.py` and explain why the readiness drill checks a running failed pod before accepting a timed-out upgrade. An unrelated image-pull error should not produce a green test.

Then show why `smoke` sends traffic through the Service network path rather than relying on `port-forward svc/...`.

## 3. Show evidence

Use your own successful run's `artifacts/e2e.json`, failed pod diagnostics, and recovered response. If the cluster run has not completed, say so and show the available local checks instead. Do not quote timing from someone else's machine as a performance result.

## 4. Explain one tradeoff

Choose one:

- capture diagnostics before rollback versus automatic rollback;
- a disposable local cluster versus an actual cloud environment;
- per-pod scraping versus scraping a load-balanced Service;
- a Git-based generator versus building a developer portal too early.

## 5. Be specific about the next production requirement

Pick the requirement relevant to the employer: IAM and secret delivery, multi-node capacity, persistent recovery, ingress/TLS, admission policy, or ownership and access control. Explain how you would test it before calling the platform production-ready.

## Before using the project in an interview

Run both drills yourself, change an alert threshold and its test, onboard one service with a real digest, and explain the rollback ownership difference between Helm and Argo CD. These changes give you concrete decisions and observations to discuss.
