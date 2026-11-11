"""Install pinned CLI binaries into .tools/bin after checking upstream SHA-256 sums."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import platform
import stat
import tarfile
from urllib.request import Request, urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = json.loads((ROOT / "tools/versions.json").read_text())


def download(url):
    request = Request(url, headers={"User-Agent": "release-lab-bootstrap"})
    with urlopen(request, timeout=90) as response:
        return response.read()


def install(name, system, arch):
    version = VERSIONS[name]
    suffix = ".exe" if system == "windows" else ""
    binary = name + suffix
    if name == "helm":
        archive = f"helm-v{version}-{system}-{arch}.tar.gz"
        url = f"https://get.helm.sh/{archive}"
        checksum_url = url + ".sha256sum"
    elif name == "kind":
        archive = f"kind-{system}-{arch}"
        url = f"https://github.com/kubernetes-sigs/kind/releases/download/v{version}/{archive}"
        checksum_url = url + ".sha256sum"
    elif name == "kubectl":
        archive = binary
        url = f"https://dl.k8s.io/release/v{version}/bin/{system}/{arch}/{binary}"
        checksum_url = url + ".sha256"
    elif name == "actionlint":
        extension = "zip" if system == "windows" else "tar.gz"
        archive = f"actionlint_{version}_{system}_{arch}.{extension}"
        base = f"https://github.com/rhysd/actionlint/releases/download/v{version}"
        url = f"{base}/{archive}"
        checksum_url = f"{base}/actionlint_{version}_checksums.txt"
    elif name == "promtool":
        extension = "zip" if system == "windows" else "tar.gz"
        archive = f"prometheus-{version}.{system}-{arch}.{extension}"
        base = f"https://github.com/prometheus/prometheus/releases/download/v{version}"
        url = f"{base}/{archive}"
        checksum_url = f"{base}/sha256sums.txt"
    else:
        raise ValueError(f"Unknown tool: {name}")
    checksums = download(checksum_url).decode().splitlines()
    candidates = [line.split()[0] for line in checksums
                  if len(line.split()) == 1 or line.split()[-1].lstrip("*") == archive]
    if len(candidates) != 1:
        raise ValueError(f"Cannot find an unambiguous checksum for {archive}")
    data = download(url)
    if hashlib.sha256(data).hexdigest() != candidates[0]:
        raise ValueError(f"Checksum mismatch for {archive}")
    if archive.endswith(".tar.gz"):
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as package:
            members = [m for m in package.getmembers() if m.isfile() and Path(m.name).name == binary]
            if len(members) != 1:
                raise ValueError(f"Expected exactly one {binary} in archive")
            data = package.extractfile(members[0]).read()
    elif archive.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as package:
            members = [m for m in package.namelist() if Path(m).name == binary]
            if len(members) != 1:
                raise ValueError(f"Expected exactly one {binary} in archive")
            data = package.read(members[0])
    target = ROOT / ".tools/bin" / binary
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"Installed {name} {version} (upstream checksum verified)", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tools", nargs="*", default=["helm", "actionlint", "promtool", "kind", "kubectl"])
    args = parser.parse_args()
    system = platform.system().lower()
    arch = {"x86_64": "amd64", "amd64": "amd64", "arm64": "arm64", "aarch64": "arm64"}.get(platform.machine().lower())
    if system not in {"linux", "darwin", "windows"} or arch is None:
        parser.error("Supported platforms: Linux, macOS, Windows; amd64 or arm64")
    for name in args.tools:
        install(name, system, arch)


if __name__ == "__main__":
    main()
