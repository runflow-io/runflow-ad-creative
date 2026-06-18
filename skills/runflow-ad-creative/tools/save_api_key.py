#!/usr/bin/env python3
"""Save a Runflow API key into the canonical credentials file.

Used by the skill's sandboxed and headless auth paths, where the standard
get_api_key.py loopback flow cannot run because there is no browser and no
local port to bind. The user gets the key from
https://app.runflow.io/settings/api-keys and pastes it; this script persists it
to ~/.config/runflow/credentials.json with 0600 permissions.

Usage:
  python3 save_api_key.py --key rfk_abc123...
  python3 save_api_key.py             # reads the key from stdin
  python3 save_api_key.py --print-only --name "Runflow Ad Builder"
                                       # prints the connect/settings URL
                                       # plus the scopes the skill needs,
                                       # writes nothing
"""
import argparse
import json
import os
import stat
import sys
import urllib.parse
from pathlib import Path

CRED_PATH = Path.home() / ".config" / "runflow" / "credentials.json"
SETTINGS_URL = "https://app.runflow.io/settings/api-keys"
CONNECT_URL = "https://app.runflow.io/connect/api-key"
DEFAULT_NAME = "Runflow Ad Builder"
DEFAULT_SCOPES = [
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
]


def print_connect_instructions(name: str) -> None:
    qs = urllib.parse.urlencode({
        "api_key_name": name,
        "scopes": ",".join(DEFAULT_SCOPES),
        "redirect_to": "",  # left empty so the user copies the key from the page
    })
    print("To get a Runflow API key without the automated browser flow:")
    print()
    print("1. Sign in at https://app.runflow.io (free account if you do not have one).")
    print("2. Open the API keys settings:")
    print(f"   {SETTINGS_URL}")
    print(f"   Or use the preselected connect link (paste in your browser):")
    print(f"   {CONNECT_URL}?{qs}")
    print(f"3. Create a key named \"{name}\" with these scopes checked:")
    for s in DEFAULT_SCOPES:
        print(f"   - {s}")
    print("4. Copy the key shown once. It begins with 'rfk_'.")
    print("5. Paste it back to your agent or run:")
    print("   python3 save_api_key.py --key rfk_...")
    print()
    print("If you are in a sandbox that cannot write to your real ~/.config/runflow/,")
    print("save the key on your own desktop with this one-liner:")
    print()
    print("   mkdir -p ~/.config/runflow && \\")
    print("     echo '{\"api_key\":\"PASTE_KEY_HERE\",\"name\":\"Runflow Ad Builder\"}' \\")
    print("     > ~/.config/runflow/credentials.json && \\")
    print("     chmod 600 ~/.config/runflow/credentials.json")


def save(key: str, name: str) -> None:
    key = key.strip()
    if not key:
        sys.exit("no key provided (empty stdin / empty --key)")
    CRED_PATH.parent.mkdir(parents=True, exist_ok=True)
    CRED_PATH.write_text(json.dumps({"api_key": key, "name": name}, indent=2))
    os.chmod(CRED_PATH, stat.S_IRUSR | stat.S_IWUSR)
    print(f"key saved to {CRED_PATH}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--key", help="API key string. Read from stdin if omitted.")
    p.add_argument("--name", default=DEFAULT_NAME,
                   help=f"Friendly label stored alongside the key (default: '{DEFAULT_NAME}')")
    p.add_argument("--print-only", action="store_true",
                   help="Print the connect URL and scopes for the user, write nothing.")
    args = p.parse_args()

    if args.print_only:
        print_connect_instructions(args.name)
        return

    key = args.key or sys.stdin.read()
    save(key, args.name)


if __name__ == "__main__":
    main()
