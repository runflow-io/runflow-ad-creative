#!/usr/bin/env python3
"""Send Sentinel feedback for one or more evaluations.

Inputs a JSON array on stdin or via --json: each item must include `evaluation_id`
and `is_positive` (true/false/null) and may include `reason` (free text).

PATCHes /v1/evaluations/{evaluation_id}/feedback for each. Prints a per-item result.

Usage:
  echo '[{"evaluation_id":"...","is_positive":true,"reason":"clean wordmark"}]' \\
    | python3 feedback.py
  python3 feedback.py --json '[{"evaluation_id":"...","is_positive":false}]'

Auth resolution mirrors create_ad.py: RUNFLOW_API_KEY env, then ~/.config/runflow/credentials.json.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.runflow.io/v1"
CRED_PATH = Path.home() / ".config" / "runflow" / "credentials.json"


def _load_key():
    k = os.environ.get("RUNFLOW_API_KEY")
    if k:
        return k
    if CRED_PATH.exists():
        try:
            data = json.loads(CRED_PATH.read_text())
            if data.get("api_key"):
                return data["api_key"]
        except (OSError, json.JSONDecodeError):
            pass
    sys.exit(f"no key in env or {CRED_PATH}; run get_api_key.py first")


def patch_feedback(evaluation_id: str, is_positive, reason: str = "") -> dict:
    body = {"is_positive": is_positive}
    if reason and is_positive is not None:
        body["reason"] = reason[:2000]
    h = {
        "Authorization": f"Bearer {_load_key()}",
        "Content-Type": "application/json",
    }
    url = f"{API}/evaluations/{evaluation_id}/feedback"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="PATCH", headers=h)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return {"evaluation_id": evaluation_id, "status": resp.status, "ok": True}
    except urllib.error.HTTPError as e:
        return {
            "evaluation_id": evaluation_id,
            "status": e.code,
            "ok": False,
            "error": e.read().decode("utf-8", errors="replace")[:500],
        }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json", help="inline JSON array; stdin used if absent")
    args = p.parse_args()

    raw = args.json if args.json else sys.stdin.read()
    if not raw.strip():
        sys.exit("no feedback payload given (stdin empty, --json missing)")
    try:
        items = json.loads(raw)
    except json.JSONDecodeError as e:
        sys.exit(f"could not parse JSON: {e}")
    if not isinstance(items, list):
        sys.exit("payload must be a JSON array of feedback items")

    out = []
    for it in items:
        eid = it.get("evaluation_id")
        if not eid:
            out.append({"ok": False, "error": "missing evaluation_id", "item": it})
            continue
        if "is_positive" not in it:
            out.append({"evaluation_id": eid, "ok": False, "error": "missing is_positive"})
            continue
        out.append(patch_feedback(eid, it["is_positive"], it.get("reason", "")))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
