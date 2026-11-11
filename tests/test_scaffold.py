import json
from pathlib import Path
import tempfile
import unittest

from tools.new_service import scaffold


class ScaffoldTests(unittest.TestCase):
    image = "ghcr.io/example/probe@sha256:" + "a" * 64
    repository = "https://github.com/example/release-lab.git"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def create(self, name="payments", image=None):
        return scaffold(self.root, name, "payments-team", image or self.image, self.repository)

    def test_scaffold_restricts_namespace_and_uses_digest(self):
        directory = self.create()
        values = json.loads((directory / "values.json").read_text())
        app = json.loads((directory / "application.json").read_text())
        project = json.loads((directory / "project.json").read_text())
        self.assertEqual(values["image"]["digest"], "sha256:" + "a" * 64)
        self.assertEqual(app["spec"]["destination"]["namespace"], "payments")
        self.assertEqual(app["spec"]["project"], "payments")
        self.assertEqual(project["spec"]["sourceRepos"], [self.repository])
        self.assertEqual(project["spec"]["clusterResourceWhitelist"], [])
        self.assertFalse(app["spec"]["syncPolicy"]["automated"]["prune"])

    def test_generator_cannot_overwrite_reviewed_values(self):
        directory = self.create()
        values = directory / "values.json"
        values.write_text("custom reviewed content")
        with self.assertRaises(FileExistsError):
            self.create()
        self.assertEqual(values.read_text(), "custom reviewed content")

    def test_names_cannot_escape_the_service_directory(self):
        for name in ("../outside", "/tmp/app", "UpperCase", "foo/bar", "a" * 64):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.create(name=name)
        self.assertFalse((self.root / "services").exists())

    def test_mutable_tags_are_rejected(self):
        for image in ("nginx:latest", "ghcr.io/example/app:abc123", "app@sha256:abc"):
            with self.subTest(image=image), self.assertRaises(ValueError):
                self.create(image=image)

    def test_arbitrary_repository_schemes_are_rejected(self):
        with self.assertRaises(ValueError):
            scaffold(self.root, "payments", "team", self.image, "file:///etc")


if __name__ == "__main__":
    unittest.main()
