# Engineering background

Vladimir / [isboston](https://github.com/isboston) — DevOps Engineer at ONLYOFFICE, working on Linux packaging, installation, CI/CD, and deployment automation.

This repository is a personal lab extending that work toward Kubernetes delivery and developer tooling.

## Related public work

These links point to professional contributions, separate from the lab:

- [Docker integration tests](https://github.com/ONLYOFFICE/Docker-DocumentServer/commit/35bee8f23867fe3668d80a425a9d447474d2d435): 35 scenarios, published image selection, digest pinning, conversion checks, HTTPS validation, restart persistence, and diagnostic capture.
- [Reducing duplicate access logs](https://github.com/ONLYOFFICE/DocSpace-buildtools/commit/bfd5e8de722bdd16aa33dc0e093816d5c2b1f3f3): remove duplicate nginx access events and filter successful static requests before ingestion. The commit describes an expected reduction for a sampled page load, not a verified fleet-wide result.
- [Linux font packaging](https://github.com/isboston/msttcore-fonts): DEB/RPM packaging, installation scripts, and release artifacts.

## A short review path

Start with the two drills in the README. Then inspect `readiness_failure`, `business_failure`, and `smoke` in `tools/lab.py`. The useful questions are why the checks differ, what the rollback proves, and which failure conditions must remain test failures.

The generator and AppProject describe a narrow service onboarding path. The decisions document records its current boundaries. The validation record distinguishes executed checks from code awaiting a cluster run.

There is no claimed customer adoption, production uptime, cost reduction, or production cluster scale for this personal project.
