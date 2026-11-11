"""Operate only the release-lab kind cluster using a repository-local kubeconfig."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
KUBECONFIG = ARTIFACTS / "lab.kubeconfig"
CLUSTER = "release-lab"
NAMESPACE = "release-lab"
VERSIONS = json.loads((ROOT / "tools/versions.json").read_text())


def binary(name):
    suffix = ".exe" if os.name == "nt" else ""
    local = ROOT / ".tools/bin" / (name + suffix)
    found = str(local) if local.exists() else shutil.which(name)
    if not found:
        raise RuntimeError(f"Missing {name}. Run python tools/bootstrap.py; install Docker separately.")
    return found


def run(name, *args, check=True, timeout=180, input_text=None):
    command = [binary(name)]
    if name in {"kubectl", "helm"}:
        if not KUBECONFIG.exists():
            raise RuntimeError("Missing local kubeconfig. Run python tools/lab.py up first.")
        command += ["--kubeconfig", str(KUBECONFIG)]
        command += ["--context" if name == "kubectl" else "--kube-context", "kind-" + CLUSTER]
    command += list(map(str, args))
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=timeout, input=input_text)
    if check and result.returncode:
        raise RuntimeError(f"{name} {' '.join(map(str, args))}\n{result.stdout}\n{result.stderr}")
    return result


def up():
    run("docker", "info", timeout=20)
    clusters = run("kind", "get", "clusters").stdout.splitlines()
    if CLUSTER in clusters:
        if not KUBECONFIG.exists():
            raise RuntimeError("A release-lab cluster already exists without this checkout's kubeconfig; refusing to adopt it.")
        print("Using existing release-lab cluster.", flush=True)
        return
    ARTIFACTS.mkdir(exist_ok=True)
    print("Creating isolated kind cluster...", flush=True)
    run("kind", "create", "cluster", "--name", CLUSTER, "--config", "kind.yaml",
        "--image", VERSIONS["kind_node"], "--kubeconfig", KUBECONFIG, "--wait", "120s", timeout=480)


def build():
    print("Building and loading release-probe:dev...", flush=True)
    run("docker", "build", "-t", "release-probe:dev", ".", timeout=480)
    run("kind", "load", "docker-image", "release-probe:dev", "--name", CLUSTER, timeout=180)


def deploy(version="good", readiness="ready", work="ok", timeout="120s", check=True):
    return run("helm", "upgrade", "--install", "probe", "charts/service", "-n", NAMESPACE,
               "--create-namespace", "--wait", "--timeout", timeout,
               "--set-string", f"appVersion={version}", "--set-string", f"readinessMode={readiness}",
               "--set-string", f"workMode={work}", check=check, timeout=240)


def request(base, path):
    try:
        response = urlopen(base + path, timeout=3)
    except HTTPError as error:
        response = error
    with response:
        return response.status, response.read().decode()


@contextmanager
def forward(resource="svc/probe", remote_port=8080):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    command = [binary("kubectl"), "--kubeconfig", str(KUBECONFIG), "--context", "kind-" + CLUSTER,
               "-n", NAMESPACE, "port-forward", "--address", "127.0.0.1", resource, f"{port}:{remote_port}"]
    ARTIFACTS.mkdir(exist_ok=True)
    with (ARTIFACTS / "port-forward.log").open("a", encoding="utf-8") as log:
        process = subprocess.Popen(command, stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError("port-forward exited; see artifacts/port-forward.log")
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                        break
                except OSError:
                    time.sleep(0.2)
            else:
                raise RuntimeError("port-forward did not become ready")
            yield f"http://127.0.0.1:{port}"
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def smoke(expected="good"):
    # Exercise the Service network path; port-forward to a Service actually picks a pod
    # and would not prove that Kubernetes is excluding unready endpoints.
    program = """import hashlib, json, sys
from urllib.request import urlopen
for _ in range(10):
    with urlopen('http://probe.release-lab.svc:8080/work?value=release-check', timeout=3) as r:
        body = json.load(r)
    if body.get('version') != sys.argv[1] or body.get('sha256') != hashlib.sha256(b'release-check').hexdigest():
        raise SystemExit('Unexpected response: ' + repr(body))
print('10 functional requests passed through the Kubernetes Service')
"""
    result = run("kubectl", "-n", NAMESPACE, "exec", "deployment/probe", "--", "python", "-c", program, expected)
    print(result.stdout.strip(), flush=True)


def revision():
    history = json.loads(run("helm", "history", "probe", "-n", NAMESPACE, "-o", "json").stdout)
    return max(item["revision"] for item in history if item["status"] == "deployed")


def rollback(target):
    run("helm", "rollback", "probe", target, "-n", NAMESPACE, "--wait", "--timeout", "120s")


def diagnostics(label):
    directory = ARTIFACTS / label
    directory.mkdir(parents=True, exist_ok=True)
    commands = {
        "resources.txt": ("get", "deploy,rs,pod,svc", "-o", "wide"),
        "events.txt": ("get", "events", "--sort-by=.metadata.creationTimestamp"),
        "pods.txt": ("describe", "pods", "-l", "app.kubernetes.io/instance=probe"),
        "application.log": ("logs", "-l", "app.kubernetes.io/instance=probe", "--all-containers", "--prefix", "--tail=80")}
    for filename, command in commands.items():
        try:
            result = run("kubectl", "-n", NAMESPACE, *command, check=False, timeout=25)
            text = result.stdout + result.stderr
        except (RuntimeError, subprocess.TimeoutExpired) as error:
            text = str(error)
        (directory / filename).write_text(text, encoding="utf-8")


def readiness_failure():
    good = revision()
    result = deploy("readiness-bad", readiness="fail", timeout="40s", check=False)
    if result.returncode == 0:
        raise RuntimeError("A release with failed readiness unexpectedly succeeded")
    diagnostics("readiness-failure")
    pods = json.loads(run("kubectl", "-n", NAMESPACE, "get", "pods", "-l",
                          "app.kubernetes.io/instance=probe", "-o", "json").stdout)["items"]
    failed = []
    for pod in pods:
        env = {item["name"]: item.get("value") for item in pod["spec"]["containers"][0]["env"]}
        if env.get("APP_VERSION") == "readiness-bad" and pod["status"].get("phase") == "Running":
            failed.append(pod["metadata"]["name"])
    if not failed:
        raise RuntimeError("Upgrade failed before the injected fault ran; this is not a passing fault test")
    with forward("pod/" + failed[0]) as base:
        if request(base, "/readyz")[0] != 503 or request(base, "/healthz")[0] != 200:
            raise RuntimeError("The injected readiness failure was not observed")
    smoke("good")  # Old Ready pods still serve the service during a blocked rollout.
    rollback(good)
    smoke("good")


def business_failure():
    good = revision()
    deploy("business-bad", work="fail")
    with forward() as base:
        if request(base, "/readyz")[0] != 200 or request(base, "/work")[0] != 503:
            raise RuntimeError("Expected healthy readiness and a failed business request")
    diagnostics("business-failure")
    rollback(good)
    smoke("good")


def e2e():
    up()
    build()
    deploy()
    smoke()
    report = {"recorded_at": datetime.now(timezone.utc).isoformat(), "cluster": CLUSTER, "checks": []}
    for name, operation in [("readiness failure and recovery", readiness_failure),
                            ("business failure and recovery", business_failure)]:
        started = time.monotonic()
        print(f"Running: {name}", flush=True)
        try:
            operation()
        except Exception:
            diagnostics("unexpected-failure")
            report["checks"].append({"name": name, "passed": False})
            (ARTIFACTS / "e2e.json").write_text(json.dumps(report, indent=2) + "\n")
            raise
        report["checks"].append({"name": name, "passed": True,
                                 "elapsed_seconds": round(time.monotonic() - started, 2)})
    (ARTIFACTS / "e2e.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2), flush=True)


def monitoring():
    config = run("kubectl", "-n", NAMESPACE, "create", "configmap", "release-lab-dashboard",
                 "--from-file=dashboard.json=monitoring/dashboard.json", "--dry-run=client", "-o", "json")
    run("kubectl", "-n", NAMESPACE, "apply", "-f", "-", input_text=config.stdout)
    run("kubectl", "-n", NAMESPACE, "apply", "-f", "monitoring/stack.yaml")
    for name in ("prometheus", "grafana"):
        run("kubectl", "-n", NAMESPACE, "rollout", "status", "deployment/" + name, "--timeout=120s")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["up", "build", "deploy", "smoke", "e2e", "monitoring", "down"])
    args = parser.parse_args()
    try:
        if args.command == "down":
            if not KUBECONFIG.exists():
                raise RuntimeError("No kubeconfig owned by this checkout; refusing cluster deletion")
            run("kind", "delete", "cluster", "--name", CLUSTER, "--kubeconfig", KUBECONFIG)
        else:
            globals()[args.command]()
    except (RuntimeError, subprocess.TimeoutExpired, URLError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
