#!/usr/bin/env python3
"""Send Sentinel feedback for one or more variants.

Inputs a JSON array on stdin or via --json. Each item must include either
`run_id` (preferred, as of 2026-06-18 Sentinel auto-evaluates every workflow run)
or `evaluation_id` (legacy, for direct eval references), plus `is_positive`
(true/false/null) and an optional `reason`.

For each item the script:
  1. Resolves the auto-generated Sentinel evaluation tied to the run via
     GET /v1/runs/{run_id}/evaluations (most-recent eval if multiple).
  2. PATCHes /v1/runs/{run_id}/evaluations/{evaluation_id}/feedback so the
     feedback lands on the same eval surface Sentinel itself populated.

If the eval hasn't landed yet (Sentinel cron runs every ~2 min), it polls
briefly before giving up.

Usage:
  echo '[{"run_id":"019ed...","is_positive":true,"reason":"clean wordmark"}]' \\
    | python3 feedback.py
  python3 feedback.py --json '[{"evaluation_id":"019ed...","is_positive":false}]'
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.runflow.io/v1"
CRED_PATH = Path.home() / ".config" / "runflow" / "credentials.json"
EVAL_LOOKUP_TIMEOUT_S = 120  # Sentinel cron runs every ~2 min per Miguel's update.
EVAL_LOOKUP_INTERVAL_S = 5


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


def _auth_headers():
    return {"Authorization": f"Bearer {_load_key()}"}


def get_evaluations_for_run(run_id: str):
    """Return the list of evaluations tied to a run, newest first."""
    req = urllib.request.Request(
        f"{API}/runs/{run_id}/evaluations",
        headers=_auth_headers(),
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            items = data.get("items", data) if isinstance(data, dict) else data
            return items if isinstance(items, list) else []
    except urllib.error.HTTPError as e:
        return []


def resolve_eval_id(run_id: str, wait: bool = True) -> str:
    """Find the auto-generated Sentinel eval for a run. Polls briefly if it isn't there yet."""
    deadline = time.time() + (EVAL_LOOKUP_TIMEOUT_S if wait else 0)
    while True:
        evals = get_evaluations_for_run(run_id)
        if evals:
            # Newest first — pick the latest completed/pending eval.
            evals_sorted = sorted(evals, key=lambda e: e.get("created_at", ""), reverse=True)
            return evals_sorted[0].get("id", "")
        if time.time() >= deadline:
            return ""
        time.sleep(EVAL_LOOKUP_INTERVAL_S)


def patch_feedback_run_scoped(run_id: str, eval_id: str, is_positive, reason: str = "") -> dict:
    """Preferred endpoint: PATCH /v1/runs/{run_id}/evaluations/{evaluation_id}/feedback."""
    body = {"is_positive": is_positive}
    if reason and is_positive is not None:
        body["reason"] = reason[:2000]
    h = {**_auth_headers(), "Content-Type": "application/json"}
    url = f"{API}/runs/{run_id}/evaluations/{eval_id}/feedback"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="PATCH", headers=h)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return {"run_id": run_id, "evaluation_id": eval_id, "status": resp.status, "ok": True}
    except urllib.error.HTTPError as e:
        return {
            "run_id": run_id, "evaluation_id": eval_id,
            "status": e.code, "ok": False,
            "error": e.read().decode("utf-8", errors="replace")[:500],
        }


def patch_feedback_eval_only(eval_id: str, is_positive, reason: str = "") -> dict:
    """Legacy fallback: PATCH /v1/evaluations/{evaluation_id}/feedback when no run_id is given."""
    body = {"is_positive": is_positive}
    if reason and is_positive is not None:
        body["reason"] = reason[:2000]
    h = {**_auth_headers(), "Content-Type": "application/json"}
    url = f"{API}/evaluations/{eval_id}/feedback"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="PATCH", headers=h)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return {"evaluation_id": eval_id, "status": resp.status, "ok": True}
    except urllib.error.HTTPError as e:
        return {
            "evaluation_id": eval_id, "status": e.code, "ok": False,
            "error": e.read().decode("utf-8", errors="replace")[:500],
        }


def handle_item(item: dict) -> dict:
    if "is_positive" not in item:
        return {"ok": False, "error": "missing is_positive", "item": item}
    reason = item.get("reason", "")
    run_id = item.get("run_id")
    eval_id = item.get("evaluation_id")
    if run_id:
        if not eval_id:
            eval_id = resolve_eval_id(run_id, wait=True)
        if not eval_id:
            return {
                "run_id": run_id, "ok": False,
                "error": (
                    "no Sentinel evaluation found for this run after polling. "
                    "It may not have landed yet (cron is ~2 min) or the run may have "
                    "failed Sentinel's image-output check."
                ),
            }
        return patch_feedback_run_scoped(run_id, eval_id, item["is_positive"], reason)
    if eval_id:
        return patch_feedback_eval_only(eval_id, item["is_positive"], reason)
    return {"ok": False, "error": "item must include run_id or evaluation_id", "item": item}


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

    print(json.dumps([handle_item(it) for it in items], indent=2))


if __name__ == "__main__":
    main()
