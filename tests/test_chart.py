import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

from tools.lab import ROOT, binary
from tools.new_service import scaffold


class ChartTests(unittest.TestCase):
    def render(self, *arguments, success=True):
        result = subprocess.run([binary("helm"), "template", "probe", "charts/service",
                                 "-n", "release-lab", *arguments], cwd=ROOT,
                                capture_output=True, text=True, timeout=30)
        if not success:
            self.assertNotEqual(result.returncode, 0, result.stdout)
            return result.stderr
        self.assertEqual(result.returncode, 0, result.stderr)
        return {item["kind"]: item for item in yaml.safe_load_all(result.stdout) if item}

    def test_selectors_and_named_ports_form_a_working_service(self):
        objects = self.render()
        deployment, service = objects["Deployment"], objects["Service"]
        labels = deployment["spec"]["template"]["metadata"]["labels"]
        for key, value in service["spec"]["selector"].items():
            self.assertEqual(labels[key], value)
        container = deployment["spec"]["template"]["spec"]["containers"][0]
        ports = {item["name"] for item in container["ports"]}
        self.assertIn(service["spec"]["ports"][0]["targetPort"], ports)
        for probe in ("startupProbe", "readinessProbe", "livenessProbe"):
            self.assertIn(container[probe]["httpGet"]["port"], ports)

    def test_invalid_rollout_inputs_fail_before_apply(self):
        for override in ("replicaCount=0", "replicaCount=100", "readinessMode=unknown",
                         "image.digest=sha256:bad", "image.tag=", "owner=INVALID"):
            with self.subTest(override=override):
                self.render("--set", override, success=False)

    def test_generated_service_values_render_an_immutable_image(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = scaffold(Path(temp), "payments", "payments-team",
                                 "ghcr.io/example/probe@sha256:" + "b" * 64,
                                 "https://github.com/example/release-lab.git")
            objects = self.render("-f", str(directory / "values.json"))
            image = objects["Deployment"]["spec"]["template"]["spec"]["containers"][0]["image"]
            self.assertEqual(image, "ghcr.io/example/probe@sha256:" + "b" * 64)

    def test_one_replica_does_not_get_an_unfulfillable_disruption_budget(self):
        self.assertNotIn("PodDisruptionBudget", self.render("--set", "replicaCount=1"))

    def test_optional_policy_selects_only_this_release(self):
        objects = self.render("--set", "networkPolicy.enabled=true")
        policy = objects["NetworkPolicy"]["spec"]
        deployment = objects["Deployment"]["spec"]
        self.assertEqual(policy["podSelector"]["matchLabels"], deployment["selector"]["matchLabels"])
        self.assertEqual(policy["egress"], [])

    def test_dashboard_and_alerts_parse(self):
        objects = list(yaml.safe_load_all((ROOT / "monitoring/stack.yaml").read_text()))
        configs = {item["metadata"]["name"]: item["data"] for item in objects if item["kind"] == "ConfigMap"}
        for value in configs["prometheus-config"].values():
            self.assertIsInstance(yaml.safe_load(value), dict)
        dashboard = json.loads((ROOT / "monitoring/dashboard.json").read_text())
        uids = {panel["datasource"]["uid"] for panel in dashboard["panels"]}
        datasource = yaml.safe_load(configs["grafana-provisioning"]["datasource.yaml"])
        self.assertEqual(uids, {item["uid"] for item in datasource["datasources"]})


if __name__ == "__main__":
    unittest.main()
