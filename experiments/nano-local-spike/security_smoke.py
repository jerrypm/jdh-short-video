"""Checks the running spike server without changing its saved report."""
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ORIGIN = "http://127.0.0.1:8769"
REPORT = Path(__file__).resolve().parents[2] / "docs/qa/nano-local-spike-browser.json"


def request(path="/", method="GET", headers=None, body=None):
    try:
        with urlopen(Request(ORIGIN + path, method=method, headers=headers or {}, data=body), timeout=5) as response:
            return response.status, response.headers, response.read()
    except HTTPError as error:
        return error.code, error.headers, error.read()


status, headers, body = request()
assert status == 200
assert "connect-src 'self'" in headers["Content-Security-Policy"]
assert headers["X-Content-Type-Options"] == "nosniff"
token = re.search(rb'name="spike-token" content="([a-f0-9]+)"', body).group(1).decode()
before = REPORT.read_bytes() if REPORT.exists() else None
checks = [
    ("foreign_host", request(headers={"Host": "attacker.example"})[0], 403),
    ("foreign_origin", request(headers={"Origin": "https://attacker.example"})[0], 403),
    ("directory_traversal", request("/../../README.md")[0], 404),
    ("missing_token", request("/report", "POST", {"Origin": ORIGIN}, b"{}")[0], 403),
    ("missing_origin", request("/report", "POST", {"X-JDH-Spike-Token": token}, b"{}")[0], 403),
    ("malformed_body", request("/report", "POST", {"Origin": ORIGIN, "X-JDH-Spike-Token": token}, b"not-json")[0], 400),
    ("wrong_provider", request("/report", "POST", {"Origin": ORIGIN, "X-JDH-Spike-Token": token}, b'{"provider":"cloud"}')[0], 400),
    ("bridge_without_token", request("/bridge/status")[0], 403),
    ("arbitrary_bridge_operation", request("/bridge/enqueue", "POST", {"X-JDH-Spike-Token": token}, b'{"action":"shell"}')[0], 400),
]
for name, actual, expected in checks:
    assert actual == expected, (name, actual, expected)
after = REPORT.read_bytes() if REPORT.exists() else None
assert before == after, "Rejected requests changed the report."
print(json.dumps({"passed": [row[0] for row in checks], "report_unchanged": True}, indent=2))
