#!/usr/bin/env python3
"""Upload hero + logo, fan out one workflow run per aspect ratio, poll, print results.

Reads RUNFLOW_API_KEY from the environment. Reads brand kit JSON from
`../brand-kits/<slug>.json` relative to this file.

Usage:
  python3 create_ad.py \
    --brand runflow \
    --hero /path/to/model.jpg \
    --headline "Opening contest now" \
    --subhead "$20k to win" \
    --cta "Apply now" \
    --tone "premium" \
    --formats 1:1,9:16,16:9 \
    [--audience "ComfyUI builders"]

Output: one line per run as `RUN[<ratio>] <status> ...` with id or url.
"""
import argparse
import concurrent.futures
import json
import mimetypes
import os
import re
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

API = "https://api.runflow.io/v1"
WORKFLOW = "runflow-access/brand-locked-variant-nux"
ALLOWED_RATIOS = {"1:1", "4:5", "5:4", "3:4", "4:3", "2:3", "3:2", "9:16", "16:9"}
TERMINAL = {"succeeded", "failed", "cancelled", "canceled", "errored"}
SKILL_DIR = Path(__file__).resolve().parent.parent
# User-owned brand kits live in the OS user config dir so `/plugin update` never
# touches them. The plugin only ships `example.json` as a schema reference.
USER_BRAND_KITS_DIR = Path.home() / ".config" / "runflow" / "brand-kits"
LEGACY_BRAND_KITS_DIR = SKILL_DIR / "brand-kits"  # read-only fallback for old installs


CRED_PATH = Path.home() / ".config" / "runflow" / "credentials.json"


def _load_key():
    key = os.environ.get("RUNFLOW_API_KEY")
    if key:
        return key
    if CRED_PATH.exists():
        try:
            data = json.loads(CRED_PATH.read_text())
            if data.get("api_key"):
                return data["api_key"]
        except (OSError, json.JSONDecodeError):
            pass
    sys.exit(
        "RUNFLOW_API_KEY not set and no credentials file at "
        f"{CRED_PATH}. Run get_api_key.py first to authorize."
    )


def _auth():
    return {"Authorization": f"Bearer {_load_key()}"}


def api_req(method, url, body=None, timeout=120):
    h = dict(_auth())
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    r = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            raw = resp.read()
            ct = resp.headers.get("Content-Type", "")
            return json.loads(raw) if raw and ct.startswith("application/json") else raw
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {e.code} on {method} {url}: {body}")


def s3_put(url, payload, mime):
    r = urllib.request.Request(url, data=payload, method="PUT", headers={"Content-Type": mime})
    with urllib.request.urlopen(r, timeout=300) as resp:
        return resp.status


def upload(path: str) -> str:
    p = Path(path)
    if not p.exists():
        sys.exit(f"file not found: {path}")
    mime, _ = mimetypes.guess_type(str(p))
    mime = mime or "application/octet-stream"
    init = api_req("POST", f"{API}/asset-uploads", body={
        "filename": p.name,
        "mime_type": mime,
        "size_bytes": p.stat().st_size,
    })
    s3_put(init["upload_url"], p.read_bytes(), mime)
    confirmed = api_req("POST", f"{API}/asset-uploads/{init['asset_id']}/confirmations", body={})
    return confirmed["url"]


# Conservative per-run cost buffer (USD). Real runs of brand-locked-variant-nux
# bill ~$0.06; using $0.10 gives headroom for workflow-graph changes without
# false negatives in the pre-flight check.
ESTIMATED_COST_PER_RUN_USD = 0.10


def check_credits(num_formats: int) -> dict:
    """Return {ok, balance_usd, estimated_total_usd}. Skips silently if scope missing."""
    try:
        resp = api_req("GET", f"{API}/credit-balances")
    except SystemExit:
        # Scope might be missing (older keys). Skip the check rather than block.
        return {"ok": True, "skipped": True}
    # Response shape: either {items:[{balance_usd:..}]} or a flat balance object.
    balance = None
    if isinstance(resp, dict):
        items = resp.get("items") or []
        if items:
            balance = items[0].get("balance_usd") or items[0].get("balance")
        else:
            balance = resp.get("balance_usd") or resp.get("balance")
    if balance is None:
        return {"ok": True, "skipped": True}
    estimated_total = num_formats * ESTIMATED_COST_PER_RUN_USD
    return {
        "ok": float(balance) >= estimated_total,
        "balance_usd": float(balance),
        "estimated_total_usd": round(estimated_total, 4),
    }


def resolve_brand_kit(slug: str) -> dict:
    # Prefer user-config kits (survive plugin updates). Fall back to the legacy
    # in-plugin location for installs that haven't migrated yet.
    for candidate in (USER_BRAND_KITS_DIR / f"{slug}.json",
                      LEGACY_BRAND_KITS_DIR / f"{slug}.json"):
        if candidate.exists():
            return json.loads(candidate.read_text())
    sys.exit(
        f"brand kit '{slug}' not found. Expected at "
        f"{USER_BRAND_KITS_DIR / f'{slug}.json'}. Run the brand-kit setup flow."
    )


def resolve_image_input(hero: str) -> str:
    """Return a URL the workflow can consume. If hero is a local path, upload first."""
    if re.match(r"^https?://", hero):
        return hero
    return upload(hero)


def build_prompt(headline, subhead, cta, audience, tone, primary_color, typeface, extra=""):
    # NOTE on typography phrasing: do NOT write "Use the typography of: <name>" —
    # gpt_image_2 treats that label/value shape the same as "Headline text: X" and
    # renders the typeface name (e.g. "Couture") as visible copy in the ad. We use
    # "in a typeface visually similar to X" plus an explicit negative guard.
    base = (
        "Produce a brand-locked ad variant from the provided primary design reference. "
        f"Headline text: \"{headline}\". "
        f"Subhead text: \"{subhead}\". "
        f"Call to action: \"{cta}\". "
        f"Audience: {audience}. "
        f"Primary brand color: {primary_color}. "
        f"Render all text in a typeface visually similar to {typeface}; "
        f"do not include the word \"{typeface}\" anywhere in the image. "
        f"Visual tone: {tone}. "
        "Place the provided logo in a prominent corner safe zone. "
        "Preserve the focal subject from the primary design reference. "
        "The only visible text must be the headline, subhead, and call-to-action specified above; "
        "no extra copy, no eyebrows, no taglines. "
        "Avoid warped text or floating overlays."
    )
    if extra:
        base += " " + extra.strip()
    return base


def create_run(hero_url, logo_url, aspect, prompt, client_ref):
    body = {
        "input": {
            "primary_design_ref": hero_url,
            "Aux Reference 1": hero_url,
            "Aux Reference 2": hero_url,
            "logo": logo_url,
            "aspect_ratio": aspect,
            "prompt": prompt,
        },
        "client_ref": f"{client_ref}-{aspect}",
    }
    resp = api_req("POST", f"{API}/comfyui-workflows/{WORKFLOW}/runs", body=body)
    return resp.get("run_id") or resp.get("id")


def poll_until_terminal(run_id, label, max_wait_s=600, interval_s=3):
    deadline = time.time() + max_wait_s
    while time.time() < deadline:
        r = api_req("GET", f"{API}/runs/{run_id}")
        status = r.get("status_code", "")
        if status in TERMINAL:
            return status, r
        time.sleep(interval_s)
    return "timeout", None


def submit_evaluation(image_url: str, prompt: str, aspect: str) -> str:
    """Submit a variant for Sentinel quality scoring. Returns the evaluation_id, or "" on failure."""
    body = {
        "generated_image_url": image_url,
        "task_type": "ad_creative",
        "task_description": (
            "Brand-locked static ad variant produced via the runflow-access/"
            "brand-locked-variant-nux ComfyUI workflow."
        ),
        "generation_prompt": prompt,
        "evaluation_instructions": (
            "Score for: brand wordmark fidelity, headline + subhead text rendering "
            "(no typos / no kerning slips), model or hero preservation, layout balance "
            "for the requested aspect ratio, palette discipline."
        ),
        "input_attributes": {"aspect_ratio": aspect},
    }
    try:
        resp = api_req("POST", f"{API}/evaluations", body=body)
    except SystemExit as e:
        print(f"EVAL[{aspect}] submit_failed {e}", flush=True)
        return ""
    eid = resp.get("id") or resp.get("evaluation_id") or ""
    if eid:
        print(f"EVAL[{aspect}] submitted id={eid}", flush=True)
    return eid


def run_one_format(label, hero_url, logo_url, aspect, prompt, client_ref):
    try:
        rid = create_run(hero_url, logo_url, aspect, prompt, client_ref)
    except SystemExit as e:
        return {"aspect": aspect, "status": "create_failed", "error": str(e)}
    print(f"RUN[{aspect}] queued id={rid}", flush=True)
    status, run = poll_until_terminal(rid, label)
    if status != "succeeded":
        err = ""
        if run:
            err = run.get("error") or run.get("failure_reason") or ""
        print(f"RUN[{aspect}] {status} {err}".strip(), flush=True)
        return {"aspect": aspect, "status": status, "run_id": rid, "error": err}
    out = (run.get("output") or {}).get("outputs", [])
    url = out[0]["url"] if out else ""
    print(f"RUN[{aspect}] succeeded url={url}", flush=True)
    result = {"aspect": aspect, "status": "succeeded", "run_id": rid, "url": url}
    if url:
        # Sentinel scoring is free for ComfyUI workflow outputs — always submit.
        result["evaluation_id"] = submit_evaluation(url, prompt, aspect)
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--brand", required=True, help="brand kit slug (filename in brand-kits/)")
    p.add_argument("--hero", required=True, help="local path or https URL for the hero image")
    p.add_argument("--headline", required=True)
    p.add_argument("--subhead", required=True)
    p.add_argument("--cta", required=True)
    p.add_argument("--tone", required=True)
    p.add_argument("--formats", required=True, help="comma-separated aspect ratios e.g. 1:1,9:16")
    p.add_argument("--audience", default="general", help="optional audience descriptor")
    p.add_argument("--extra", default="",
                   help="optional freeform sentence appended to the prompt (use for "
                        "styling overrides like 'render the headline in pure white').")
    p.add_argument("--client-ref", default="runflow-ad-creative")
    args = p.parse_args()

    formats = [f.strip() for f in args.formats.split(",") if f.strip()]
    invalid = [f for f in formats if f not in ALLOWED_RATIOS]
    if invalid:
        sys.exit(f"unsupported aspect ratio(s): {invalid}. Allowed: {sorted(ALLOWED_RATIOS)}")

    kit = resolve_brand_kit(args.brand)

    # Resolve logo: prefer logo_url; else upload logo_path.
    logo_url = kit.get("logo_url")
    if not logo_url:
        logo_path = kit.get("logo_path")
        if not logo_path:
            sys.exit(f"brand kit {args.brand} has neither logo_url nor logo_path")
        logo_url = upload(logo_path)

    hero_url = resolve_image_input(args.hero)

    prompt = build_prompt(
        headline=args.headline,
        subhead=args.subhead,
        cta=args.cta,
        audience=args.audience,
        tone=args.tone,
        primary_color=kit.get("primary_color", "#09090B"),
        typeface=kit.get("typeface", "Outfit"),
        extra=args.extra,
    )

    # Pre-flight credit check. Block firing if balance won't cover the estimated total.
    credits = check_credits(len(formats))
    if not credits.get("skipped") and not credits.get("ok", True):
        print(
            f"CREDITS_LOW balance_usd={credits.get('balance_usd')} "
            f"estimated_total_usd={credits.get('estimated_total_usd')} "
            f"formats={len(formats)}",
            flush=True,
        )
        print("RESULTS:")
        print(json.dumps({"error": "insufficient_credits", **credits}, indent=2))
        sys.exit(3)
    if credits.get("balance_usd") is not None:
        print(
            f"CREDITS_OK balance_usd={credits['balance_usd']} "
            f"estimated_total_usd={credits['estimated_total_usd']}",
            flush=True,
        )

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(formats), 4)) as ex:
        futures = {
            ex.submit(
                run_one_format,
                f"fmt-{aspect}", hero_url, logo_url, aspect, prompt, args.client_ref,
            ): aspect
            for aspect in formats
        }
        for fut in concurrent.futures.as_completed(futures):
            results.append(fut.result())

    # Sort by the order the user passed
    order = {aspect: i for i, aspect in enumerate(formats)}
    results.sort(key=lambda r: order.get(r["aspect"], 99))

    print()
    print("RESULTS:")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
