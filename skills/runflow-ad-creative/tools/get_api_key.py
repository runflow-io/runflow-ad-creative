#!/usr/bin/env python3
"""Capture a Runflow API key via the hosted connect flow.

Opens https://app.runflow.io/connect/api-key in the user's default browser with the
scopes this skill needs, then catches the returned key on a local loopback redirect
(default port 5180). Persists the key to ~/.config/runflow/credentials.json with 0600
perms so future skill invocations can read it without re-auth.

Usage:
  python3 get_api_key.py [--port 5180] [--name "Runflow Ad Builder"] [--no-open]
                        [--scopes "runs:create,runs:read,assets:write,..."]

Prints the credentials file path on success. Exits non-zero on any failure.
"""
import argparse
import http.server
import json
import os
import socket
import stat
import sys
import urllib.parse
import webbrowser
from pathlib import Path

CONNECT_URL = "https://app.runflow.io/connect/api-key"
CRED_PATH = Path.home() / ".config" / "runflow" / "credentials.json"
DEFAULT_NAME = "Runflow Ad Builder"
# Scopes the runflow-ad-creative skill needs now + room for adjacent features later.
# The skill never uses destructive scopes (*:delete, comfyui-workflows:create/edit/delete),
# so they are intentionally excluded — the user can re-auth with --scopes if they need them.
#   runs:create               — POST /v1/comfyui-workflows/{owner}/{slug}/runs
#   runs:read                 — GET  /v1/runs/{id} (polling)
#   runs:execute              — redeliver callbacks if polling misses a terminal event
#   assets:create             — POST /v1/asset-uploads + confirmations (hero + logo)
#   assets:read               — list/reuse already-uploaded brand assets
#   assets:edit               — move outputs into per-campaign folders
#   comfyui-workflows:read    — list available workflows / inspect input schemas
#   evaluations:create        — submit variants for Sentinel quality scoring
#   evaluations:read          — fetch the scoring results to rank "which goes live"
#   evaluations:edit          — thumbs up/down on variants the user picked
#   credit_balance:read       — pre-flight check before firing N runs in parallel
DEFAULT_SCOPES = ",".join([
    "runs:create",
    "runs:read",
    "runs:execute",
    "assets:create",
    "assets:read",
    "assets:edit",
    "comfyui-workflows:read",
    "evaluations:create",
    "evaluations:read",
    "evaluations:edit",
    "credit_balance:read",
])


def pick_port(preferred: int) -> int:
    """Bind preferred port if free, else fall back to an OS-assigned one."""
    for candidate in (preferred, 0):
        s = socket.socket()
        try:
            s.bind(("127.0.0.1", candidate))
            port = s.getsockname()[1]
            s.close()
            return port
        except OSError:
            s.close()
            continue
    sys.exit("could not bind a local port")


class _Capture(http.server.BaseHTTPRequestHandler):
    captured: dict = {}

    def log_message(self, *_):
        pass

    def do_GET(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        key = (q.get("api_key") or q.get("key") or q.get("token") or [None])[0]
        if not key:
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h2>No API key in callback</h2>"
                b"<p>The redirect did not include an <code>api_key</code> parameter. "
                b"Try the flow again, or contact Runflow support.</p></body></html>"
            )
            return
        _Capture.captured["api_key"] = key
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(
            b"<html><body style='font-family:-apple-system,sans-serif;padding:40px;background:#09090B;color:#FAFAFA'>"
            b"<h2 style='color:#FBBF24'>Runflow API key captured.</h2>"
            b"<p>You can close this tab and return to your terminal.</p>"
            b"</body></html>"
        )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", type=int, default=5180)
    p.add_argument("--name", default=DEFAULT_NAME)
    p.add_argument("--scopes", default=DEFAULT_SCOPES)
    p.add_argument("--no-open", action="store_true",
                   help="Print the URL but do not auto-open the browser.")
    p.add_argument("--force", action="store_true",
                   help="Overwrite an existing credentials file without prompting.")
    args = p.parse_args()

    if CRED_PATH.exists() and not args.force:
        try:
            current = json.loads(CRED_PATH.read_text())
            if current.get("api_key"):
                print(f"credentials already exist at {CRED_PATH}", file=sys.stderr)
                print("re-run with --force to overwrite, or delete the file.", file=sys.stderr)
                sys.exit(2)
        except Exception:
            pass  # malformed; allow overwrite

    port = pick_port(args.port)
    redirect = f"http://localhost:{port}/"
    qs = urllib.parse.urlencode({
        "api_key_name": args.name,
        "scopes": args.scopes,
        "redirect_to": redirect,
    })
    url = f"{CONNECT_URL}?{qs}"

    print(f"Opening the Runflow connect flow:")
    print(f"  {url}")
    print(f"Listening on {redirect} for the key callback...")
    print()

    if not args.no_open:
        try:
            webbrowser.open(url)
        except Exception as e:
            print(f"could not auto-open browser ({e}); paste the URL above manually", file=sys.stderr)

    srv = http.server.HTTPServer(("127.0.0.1", port), _Capture)
    try:
        while "api_key" not in _Capture.captured:
            srv.handle_request()
    except KeyboardInterrupt:
        sys.exit("interrupted; no key captured")
    finally:
        srv.server_close()

    key = _Capture.captured["api_key"]
    CRED_PATH.parent.mkdir(parents=True, exist_ok=True)
    CRED_PATH.write_text(json.dumps({"api_key": key, "name": args.name}, indent=2))
    os.chmod(CRED_PATH, stat.S_IRUSR | stat.S_IWUSR)
    print(f"key saved to {CRED_PATH}")
    print("the skill will read it automatically next run.")
    print("for current shells, export it with:")
    print(f"  export RUNFLOW_API_KEY=$(python3 -c \"import json; print(json.load(open('{CRED_PATH}'))['api_key'])\")")


if __name__ == "__main__":
    main()
