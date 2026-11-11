"""Deploy the checked-in demo through Argo CD and verify correction of replica drift."""

from datetime import datetime, timezone
import json
import time

from lab import ARTIFACTS, ROOT, VERSIONS, run, up


def wait_for(description, predicate, timeout=180):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(3)
    raise RuntimeError(f"Timed out waiting for {description}")


def application_healthy():
    app = json.loads(run("kubectl", "-n", "argocd", "get", "application", "demo", "-o", "json").stdout)
    status = app.get("status", {})
    return status.get("sync", {}).get("status") == "Synced" and status.get("health", {}).get("status") == "Healthy"


def replicas_restored():
    deploy = json.loads(run("kubectl", "-n", "demo", "get", "deployment/demo", "-o", "json").stdout)
    return deploy["spec"]["replicas"] == 2 and deploy.get("status", {}).get("readyReplicas") == 2


def functional_check():
    expected = json.loads((ROOT / "services/demo/values.json").read_text())["appVersion"]
    program = """import hashlib, json, sys
from urllib.request import urlopen
with urlopen('http://demo.demo.svc:8080/work?value=gitops-check', timeout=5) as response:
    body = json.load(response)
if body.get('version') != sys.argv[1] or body.get('sha256') != hashlib.sha256(b'gitops-check').hexdigest():
    raise SystemExit('Unexpected response: ' + repr(body))
print('GitOps service functional check passed')
"""
    print(run("kubectl", "-n", "demo", "exec", "deployment/demo", "--", "python", "-c", program, expected).stdout)


def main():
    up()
    namespace = run("kubectl", "create", "namespace", "argocd", "--dry-run=client", "-o", "json").stdout
    run("kubectl", "apply", "-f", "-", input_text=namespace)
    source = f"https://raw.githubusercontent.com/argoproj/argo-cd/{VERSIONS['argocd']}/manifests/install.yaml"
    print(f"Installing Argo CD {VERSIONS['argocd']}...", flush=True)
    run("kubectl", "-n", "argocd", "apply", "--server-side", "--force-conflicts", "-f", source, timeout=180)
    for resource in ("deployment/argocd-repo-server", "statefulset/argocd-application-controller"):
        run("kubectl", "-n", "argocd", "rollout", "status", resource, "--timeout=180s", timeout=200)
    for filename in ("namespace.json", "project.json", "application.json"):
        run("kubectl", "apply", "-f", str(ROOT / "services/demo" / filename))
    print("Waiting for the Git-backed application...", flush=True)
    wait_for("application sync and health", application_healthy)
    functional_check()
    print("Injecting replica drift: 2 -> 1...", flush=True)
    run("kubectl", "-n", "demo", "scale", "deployment/demo", "--replicas=1")
    started = time.monotonic()
    wait_for("Argo CD to restore two ready replicas", replicas_restored, timeout=90)
    wait_for("application health after correction", application_healthy)
    functional_check()
    app = json.loads(run("kubectl", "-n", "argocd", "get", "application", "demo", "-o", "json").stdout)
    report = {"recorded_at": datetime.now(timezone.utc).isoformat(), "argocd": VERSIONS["argocd"],
              "synced_revision": app["status"]["sync"]["revision"], "health": "Healthy", "sync": "Synced",
              "functional_check": "passed", "replica_drift_restored": True,
              "drift_recovery_seconds": round(time.monotonic() - started, 2)}
    (ARTIFACTS / "gitops.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        ARTIFACTS.mkdir(exist_ok=True)
        for namespace in ("argocd", "demo"):
            try:
                result = run("kubectl", "-n", namespace, "get", "pods,events", "-o", "wide", check=False, timeout=20)
                (ARTIFACTS / f"gitops-{namespace}.txt").write_text(result.stdout + result.stderr)
            except Exception as error:
                (ARTIFACTS / f"gitops-{namespace}.txt").write_text(str(error))
