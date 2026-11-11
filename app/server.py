"""A probe service for exercising delivery and recovery, not an application framework."""

import hashlib
import json
import math
import os
import signal
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit


class State:
    buckets = (0.005, 0.025, 0.1, 0.5, 1.0, math.inf)

    def __init__(self, version="local", readiness="ready", work="ok", log=None):
        if readiness not in {"ready", "fail"} or work not in {"ok", "fail"}:
            raise ValueError("readiness must be ready/fail; work must be ok/fail")
        self.version = version
        self.ready = readiness == "ready"
        self.work = work
        self.log = log if log is not None else sys.stdout
        self.lock = threading.Lock()
        self.counts = {}
        self.durations = [0 for _ in self.buckets]
        self.duration_sum = 0.0

    def record(self, route, status, duration, request_id):
        # Do not let probe traffic hide errors in the business request ratio.
        if route in {"/", "/work", "not_found"}:
            with self.lock:
                key = (route, status)
                self.counts[key] = self.counts.get(key, 0) + 1
                self.duration_sum += duration
                for index, bound in enumerate(self.buckets):
                    self.durations[index] += duration <= bound
        if route not in {"/healthz", "/readyz", "/metrics"} or status >= 500:
            with self.lock:
                print(json.dumps({"event": "request", "route": route,
                                  "status": status, "duration_ms": round(duration * 1000, 3),
                                  "request_id": request_id}), file=self.log, flush=True)

    def metrics(self):
        with self.lock:
            lines = ["# HELP release_lab_ready Whether this process accepts traffic.",
                     "# TYPE release_lab_ready gauge",
                     f"release_lab_ready {int(self.ready)}",
                     "# HELP release_lab_requests_total Business requests, excluding probes and scrapes.",
                     "# TYPE release_lab_requests_total counter"]
            # Always expose zero series so a new process can be queried immediately.
            counts = {("/work", 200): 0, ("/work", 503): 0, **self.counts}
            for (route, status), count in sorted(counts.items()):
                lines.append(f'release_lab_requests_total{{route="{route}",status="{status}"}} {count}')
            lines += ["# HELP release_lab_request_duration_seconds Business request duration.",
                      "# TYPE release_lab_request_duration_seconds histogram"]
            for bound, count in zip(self.buckets, self.durations):
                label = "+Inf" if math.isinf(bound) else str(bound)
                lines.append(f'release_lab_request_duration_seconds_bucket{{le="{label}"}} {count}')
            lines += [f"release_lab_request_duration_seconds_sum {self.duration_sum}",
                      f"release_lab_request_duration_seconds_count {self.durations[-1]}"]
            return "\n".join(lines) + "\n"


def make_server(host="127.0.0.1", port=8080, state=None):
    state = state or State()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            started = time.monotonic()
            request_id = uuid.uuid4().hex
            parsed = urlsplit(self.path)
            route = parsed.path
            status = 200
            content_type = "application/json"
            if route == "/healthz":
                payload = {"alive": True}
            elif route == "/readyz":
                status = 200 if state.ready else 503
                payload = {"ready": state.ready}
            elif route == "/":
                payload = {"service": "release-probe", "version": state.version}
            elif route == "/work":
                value = parse_qs(parsed.query).get("value", ["hello"])[0]
                if state.work == "fail":
                    status, payload = 503, {"error": "injected work failure"}
                elif len(value.encode("utf-8")) > 1024:
                    status, payload = 400, {"error": "value exceeds 1024 bytes"}
                else:
                    payload = {"sha256": hashlib.sha256(value.encode()).hexdigest(),
                               "version": state.version}
            elif route == "/metrics":
                payload = state.metrics()
                content_type = "text/plain; version=0.0.4; charset=utf-8"
            else:
                route, status, payload = "not_found", 404, {"error": "not found"}
            body = (payload if isinstance(payload, str) else json.dumps(payload)).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Request-ID", request_id)
            self.end_headers()
            state.record(route, status, time.monotonic() - started, request_id)
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server


def main():
    state = State(os.getenv("APP_VERSION", "local"),
                  os.getenv("READINESS_MODE", "ready"), os.getenv("WORK_MODE", "ok"))
    server = make_server(os.getenv("HOST", "0.0.0.0"), int(os.getenv("PORT", "8080")), state)

    def stop(_signum, _frame):
        state.ready = False
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    print(json.dumps({"event": "started", "port": server.server_port,
                      "version": state.version}), flush=True)
    try:
        server.serve_forever(poll_interval=0.1)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
