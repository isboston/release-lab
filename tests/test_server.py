import hashlib
import io
import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from app.server import State, make_server


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.logs = io.StringIO()
        self.state = State(version="test-123", log=self.logs)
        self.server = make_server(port=0, state=self.state)
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       kwargs={"poll_interval": 0.01}, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def get(self, path):
        try:
            response = urlopen(self.base + path, timeout=2)
        except HTTPError as error:
            response = error
        with response:
            return response.status, response.read().decode(), response.headers

    def test_work_returns_real_digest_and_version(self):
        status, body, headers = self.get("/work?value=deployment")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"version": "test-123",
                         "sha256": hashlib.sha256(b"deployment").hexdigest()})
        self.assertRegex(headers["X-Request-ID"], r"^[a-f0-9]{32}$")

    def test_failed_readiness_does_not_fail_liveness(self):
        self.state.ready = False
        self.assertEqual(self.get("/readyz")[0], 503)
        self.assertEqual(self.get("/healthz")[0], 200)

    def test_business_failure_can_pass_readiness(self):
        self.state.work = "fail"
        self.assertEqual(self.get("/readyz")[0], 200)
        self.assertEqual(self.get("/work")[0], 503)

    def test_metrics_exclude_probe_traffic(self):
        for _ in range(3):
            self.get("/healthz")
            self.get("/readyz")
        self.get("/work")
        self.state.work = "fail"
        self.get("/work")
        metrics = self.get("/metrics")[1]
        self.assertIn('release_lab_requests_total{route="/work",status="200"} 1', metrics)
        self.assertIn('release_lab_requests_total{route="/work",status="503"} 1', metrics)
        self.assertNotIn('route="/healthz"', metrics)
        self.assertIn("release_lab_request_duration_seconds_count 2", metrics)
        self.assertIn('release_lab_request_duration_seconds_bucket{le="+Inf"} 2', metrics)

    def test_unknown_paths_do_not_create_unbounded_labels(self):
        for path in ("/users/alice", "/users/bob", "/random"):
            self.assertEqual(self.get(path)[0], 404)
        metrics = self.get("/metrics")[1]
        self.assertIn('route="not_found",status="404"} 3', metrics)
        self.assertNotIn("alice", metrics)

    def test_large_work_value_is_rejected(self):
        self.assertEqual(self.get("/work?value=" + "x" * 1025)[0], 400)

    def test_bad_configuration_fails_at_startup(self):
        with self.assertRaises(ValueError):
            State(readiness="broken")
        with self.assertRaises(ValueError):
            State(work="maybe")

    def test_probe_logs_are_quiet_and_query_strings_are_not_logged(self):
        self.get("/healthz")
        self.get("/readyz")
        self.get("/work?value=private-input")
        self.get("/metrics")  # also waits for the preceding request to finish recording
        records = [json.loads(line) for line in self.logs.getvalue().splitlines()]
        self.assertEqual([item["route"] for item in records], ["/work"])
        self.assertNotIn("private-input", self.logs.getvalue())


if __name__ == "__main__":
    unittest.main()
