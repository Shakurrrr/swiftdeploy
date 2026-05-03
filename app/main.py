#!/usr/bin/env python3
"""
SwiftDeploy API Service
Supports stable and canary modes with chaos engineering endpoints.
"""

import http.server
import json
import os
import random
import time
import threading
from datetime import datetime, timezone


# ─── Configuration from environment ────────────────────────────────────────────
MODE = os.environ.get("MODE", "stable").lower()
APP_VERSION = os.environ.get("APP_VERSION", "1.0.0")
APP_PORT = int(os.environ.get("APP_PORT", "3000"))
START_TIME = time.monotonic()

# ─── Chaos state (global, thread-safe via lock) ─────────────────────────────────
chaos_lock = threading.Lock()
chaos_state = {
    "mode": None,        # None | "slow" | "error"
    "duration": 0,       # for slow mode
    "rate": 0.0,         # for error mode
}


def get_uptime() -> float:
    return round(time.monotonic() - START_TIME, 2)


def apply_chaos() -> dict | None:
    """
    Apply active chaos. Returns error response dict if request should 500,
    None if request proceeds normally. Handles sleep side-effect.
    """
    with chaos_lock:
        state = dict(chaos_state)

    if state["mode"] == "slow":
        time.sleep(state["duration"])
        return None

    if state["mode"] == "error":
        if random.random() < state["rate"]:
            return {
                "error": "chaos error injection",
                "code": 500,
                "mode": "error",
                "rate": state["rate"],
            }

    return None


class SwiftDeployHandler(http.server.BaseHTTPRequestHandler):
    server_version = "SwiftDeploy/1.0"
    sys_version = ""

    # ── Logging ──────────────────────────────────────────────────────────────
    def log_message(self, fmt, *args):
        # Suppress default noisy logging; structured logs go to stdout
        ts = datetime.now(timezone.utc).isoformat()
        print(f"[{ts}] {fmt % args}", flush=True)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def send_json(self, code: int, payload: dict):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Deployed-By", "swiftdeploy")
        if MODE == "canary":
            self.send_header("X-Mode", "canary")
        self.end_headers()
        self.wfile.write(body)

    def read_json_body(self) -> dict | None:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        try:
            raw = self.rfile.read(length)
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return None

    # ── Route dispatch ────────────────────────────────────────────────────────
    def do_GET(self):
        if self.path == "/":
            self.handle_root()
        elif self.path == "/healthz":
            self.handle_healthz()
        else:
            self.send_json(404, {"error": "not found", "path": self.path})

    def do_POST(self):
        if self.path == "/chaos":
            self.handle_chaos()
        else:
            self.send_json(404, {"error": "not found", "path": self.path})

    # ── Handlers ──────────────────────────────────────────────────────────────
    def handle_root(self):
        # Apply chaos before responding
        chaos_err = apply_chaos()
        if chaos_err:
            self.send_json(500, chaos_err)
            return

        self.send_json(200, {
            "message": f"Welcome to SwiftDeploy API — running in {MODE} mode",
            "mode": MODE,
            "version": APP_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def handle_healthz(self):
        self.send_json(200, {
            "status": "ok",
            "mode": MODE,
            "version": APP_VERSION,
            "uptime_seconds": get_uptime(),
        })

    def handle_chaos(self):
        # Chaos endpoint only available in canary mode
        if MODE != "canary":
            self.send_json(403, {
                "error": "chaos endpoint is only available in canary mode",
                "mode": MODE,
            })
            return

        body = self.read_json_body()
        if body is None:
            self.send_json(400, {"error": "invalid JSON body"})
            return

        chaos_mode = body.get("mode")

        if chaos_mode == "slow":
            duration = body.get("duration", 1)
            if not isinstance(duration, (int, float)) or duration < 0:
                self.send_json(400, {"error": "'duration' must be a non-negative number"})
                return
            with chaos_lock:
                chaos_state["mode"] = "slow"
                chaos_state["duration"] = duration
                chaos_state["rate"] = 0.0
            self.send_json(200, {
                "ok": True,
                "chaos": "slow",
                "duration_seconds": duration,
            })

        elif chaos_mode == "error":
            rate = body.get("rate", 0.5)
            if not isinstance(rate, (int, float)) or not (0.0 <= rate <= 1.0):
                self.send_json(400, {"error": "'rate' must be a float between 0.0 and 1.0"})
                return
            with chaos_lock:
                chaos_state["mode"] = "error"
                chaos_state["duration"] = 0
                chaos_state["rate"] = rate
            self.send_json(200, {
                "ok": True,
                "chaos": "error",
                "rate": rate,
            })

        elif chaos_mode == "recover":
            with chaos_lock:
                chaos_state["mode"] = None
                chaos_state["duration"] = 0
                chaos_state["rate"] = 0.0
            self.send_json(200, {
                "ok": True,
                "chaos": "recovered",
                "message": "Chaos cancelled. Service returning to normal.",
            })

        else:
            self.send_json(400, {
                "error": f"unknown chaos mode: '{chaos_mode}'",
                "valid_modes": ["slow", "error", "recover"],
            })


class ThreadedHTTPServer(http.server.ThreadingHTTPServer):
    """Allow threaded request handling to support concurrent chaos scenarios."""
    daemon_threads = True


def main():
    print(f"[SwiftDeploy] Starting API service", flush=True)
    print(f"[SwiftDeploy] Mode={MODE} | Version={APP_VERSION} | Port={APP_PORT}", flush=True)

    server = ThreadedHTTPServer(("0.0.0.0", APP_PORT), SwiftDeployHandler)
    print(f"[SwiftDeploy] Listening on 0.0.0.0:{APP_PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[SwiftDeploy] Shutting down.", flush=True)
        server.shutdown()


if __name__ == "__main__":
    main()