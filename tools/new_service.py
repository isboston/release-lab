"""Write reviewable Helm values and Argo CD resources; never apply them to a cluster."""

import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
NAME = re.compile(r"[a-z][a-z0-9-]{0,38}[a-z0-9]\Z")
IMAGE = re.compile(r"([a-z0-9][a-z0-9./:_-]+)@(sha256:[a-f0-9]{64})\Z")
REPO = re.compile(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?\Z")


def scaffold(root, name, owner, image, repository):
    if not NAME.fullmatch(name) or not NAME.fullmatch(owner):
        raise ValueError("name and owner must be 2-40 lowercase DNS-label characters")
    match = IMAGE.fullmatch(image)
    if not match:
        raise ValueError("image must use an immutable sha256 digest, not a tag")
    if not REPO.fullmatch(repository):
        raise ValueError("repository must be an HTTPS GitHub repository URL")
    directory = Path(root).resolve() / "services" / name
    # No overwrite: running the generator again must not erase reviewed configuration.
    directory.mkdir(parents=True, exist_ok=False)
    values = {"owner": owner, "image": {"repository": match[1], "tag": "", "digest": match[2]},
              "appVersion": match[2][7:19]}
    project = {
        "apiVersion": "argoproj.io/v1alpha1", "kind": "AppProject",
        "metadata": {"name": name, "namespace": "argocd"},
        "spec": {"description": f"Delivery boundary for {name}, owned by {owner}",
                 "sourceRepos": [repository],
                 "destinations": [{"server": "https://kubernetes.default.svc", "namespace": name}],
                 "clusterResourceWhitelist": [],
                 "namespaceResourceWhitelist": [
                     {"group": "apps", "kind": "Deployment"},
                     {"group": "", "kind": "Service"},
                     {"group": "", "kind": "ServiceAccount"},
                     {"group": "policy", "kind": "PodDisruptionBudget"},
                     {"group": "networking.k8s.io", "kind": "NetworkPolicy"}]}}
    application = {
        "apiVersion": "argoproj.io/v1alpha1", "kind": "Application",
        "metadata": {"name": name, "namespace": "argocd", "labels": {"owner": owner}},
        "spec": {"project": name,
                 "source": {"repoURL": repository, "targetRevision": "main",
                            "path": "charts/service",
                            "helm": {"valueFiles": [f"../../services/{name}/values.json"]}},
                 "destination": {"server": "https://kubernetes.default.svc", "namespace": name},
                 "syncPolicy": {"automated": {"prune": False, "selfHeal": True},
                                "retry": {"limit": 3, "backoff": {"duration": "5s", "factor": 2, "maxDuration": "1m"}}}}}
    namespace = {"apiVersion": "v1", "kind": "Namespace",
                 "metadata": {"name": name, "labels": {"owner": owner,
                              "pod-security.kubernetes.io/enforce": "restricted"}}}
    for filename, value in [("values.json", values), ("project.json", project),
                            ("application.json", application), ("namespace.json", namespace)]:
        (directory / filename).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    return directory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name")
    parser.add_argument("--owner", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--repo", required=True)
    args = parser.parse_args()
    try:
        directory = scaffold(ROOT, args.name, args.owner, args.image, args.repo)
    except (ValueError, FileExistsError) as error:
        parser.error(str(error))
    print(f"Created {directory.relative_to(ROOT)}. Review and commit before applying.")


if __name__ == "__main__":
    main()
