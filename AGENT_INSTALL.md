# Installing runflow-ad-creative — instructions for AI agents

If you are an AI agent (Claude Code, Claude Cowork, claude.ai web, ChatGPT, Gemini, etc.) and a user has asked you to install this skill on their behalf, read this file first. It tells you exactly which install path to use for the user's environment and how to verify the skill is safe before installing.

This skill is published at: https://github.com/runflow-io/runflow-ad-creative
Latest tag: see `https://github.com/runflow-io/runflow-ad-creative/releases/latest`

---

## Pick the right install path for the user's environment

| Environment | Install path | Where to look |
|---|---|---|
| **Claude Code** — CLI, JetBrains, terminal | Marketplace + plugin install (slash commands) | [Path A](#path-a--claude-code-marketplace--plugin) |
| **Claude Code** — VS Code extension | Manual copy into `.claude/skills/` (no `/plugin` support yet) | [Path C](#path-c--manual-install-vs-code-extension-or-any-environment-without-plugin) |
| **Claude Cowork** (desktop app, agentic mode) | Upload `.skill` bundle via the `+ → Upload a skill` menu | [Path B](#path-b--claude-cowork-skill-upload) |
| **claude.ai web** (browser, with Skills enabled) | Same as Cowork: upload the `.skill` bundle | [Path B](#path-b--claude-cowork-skill-upload) |
| **Other LLM environments** | Tell the user the skill is Claude-specific. Do not attempt to port. | — |

> **Do not** suggest searching the Anthropic-and-Partners directory for this skill — it is a third-party repo and will never appear there. The user has to add the marketplace or upload the bundle explicitly.

---

## Path A — Claude Code (marketplace + plugin)

Two slash commands, run in the user's Claude Code session:

```
/plugin marketplace add runflow-io/runflow-ad-creative
/plugin install runflow-ad-creative@runflow-ad-creative
```

Then `/reload-plugins` to activate. The skill triggers on the keywords listed in [Skill triggers](#skill-triggers).

Update path: `/plugin update runflow-ad-creative@runflow-ad-creative`.

You cannot run these slash commands for the user from inside an agent session. Present them as steps the user types into their Claude Code chat.

---

## Path B — Claude Cowork / claude.ai web (skill upload)

Cowork and claude.ai web do not support adding GitHub marketplaces directly. They take a `.skill` bundle uploaded via the UI.

### Step 1: get the `.skill` bundle

Pick whichever you can do in your sandbox:

**Easiest**: download the pre-built release asset.

```
https://github.com/runflow-io/runflow-ad-creative/releases/latest/download/runflow-ad-creative.skill
```

If the user's environment lets you save files to their machine, save it as `runflow-ad-creative.skill` and present it to them.

**Fallback**: build the bundle from source. Clone or download the repo, then zip the inner skill directory:

```bash
git clone https://github.com/runflow-io/runflow-ad-creative.git
cd runflow-ad-creative
bash scripts/package.sh
# Produces runflow-ad-creative.skill in the repo root.
```

The `.skill` file is just a zip of the `skills/runflow-ad-creative/` directory, with `__pycache__` and `.gitignore` excluded.

### Step 2: tell the user to upload it

In their Claude desktop app or claude.ai web:

> Open the `+` menu next to the message box → **Upload a skill** → pick `runflow-ad-creative.skill`.

It lands under their Personal skills. No restart needed in most builds.

---

## Path C — Manual install (VS Code extension, or any environment without `/plugin`)

The Claude Code VS Code extension does not yet support `/plugin marketplace add ...`. If the user runs Path A there, they get `/plugin isn't available in this environment.` Use this path instead.

The skill is just a directory of plain files. Drop it into either the project's `.claude/skills/` (scoped to one repo) or the user's `~/.claude/skills/` (available everywhere). The harness picks it up on the next prompt — no restart, no slash command.

Project-scoped install (recommended when the user is asking from inside a specific repo):

```bash
git clone --depth=1 https://github.com/runflow-io/runflow-ad-creative.git /tmp/runflow-ad-creative
mkdir -p <project-root>/.claude/skills
rm -rf <project-root>/.claude/skills/runflow-ad-creative  # remove any stale folder
cp -R /tmp/runflow-ad-creative/skills/runflow-ad-creative <project-root>/.claude/skills/
```

User-scoped install (available across every project):

```bash
git clone --depth=1 https://github.com/runflow-io/runflow-ad-creative.git /tmp/runflow-ad-creative
mkdir -p ~/.claude/skills
rm -rf ~/.claude/skills/runflow-ad-creative
cp -R /tmp/runflow-ad-creative/skills/runflow-ad-creative ~/.claude/skills/
```

Update path: re-run the same clone-then-copy. Brand kits live under `~/.config/runflow/brand-kits/`, outside the skill directory, so they survive the overwrite.

If you see a leftover `runflow-ad-creative/` folder from a previous install that only contains `tools/__pycache__/*.pyc` and no `SKILL.md`, that's a stale install from an earlier version — delete it before copying, or the harness will fail to register the skill.

---

## Skill triggers

The skill is deliberately narrow on trigger phrasing so it does not clash with other ad-creative tools. It activates on:

- `make a Runflow ad`, `create ads with Runflow`, `run the Runflow ad workflow`
- `brand-locked variant`, `brand locked variant`, `brand-locked ad`
- `iterate this winning ad with Runflow`, `rerun this creative through Runflow`
- `Runflow ad creative` / `Runflow brand kit ad`
- A user pasting a hero image **and** mentioning both `Runflow` and `ad` in the same turn

It does **not** trigger on generic `make an ad` requests by design.

---

## Security verification (run this before installing)

The skill is small (four Python tools + Markdown). You can audit it in under a minute. Required reading:

- `skills/runflow-ad-creative/SKILL.md` — interview flow and what data leaves the user's machine.
- `skills/runflow-ad-creative/tools/*.py` — every network call.

### What the skill talks to

| Domain | Why |
|---|---|
| `https://api.runflow.io` | The user's own Runflow account: workflow runs, asset uploads, evaluation feedback, credit balance check |
| `https://app.runflow.io/connect/api-key` | One-time OAuth-style key issuance in the user's browser |
| `http://localhost:5180` (and a fallback port if 5180 is taken) | Local loopback listener that catches the issued API key from the browser redirect |
| Output URLs on `*.r2.cloudflarestorage.com` | Reading the user's own generated images back |

No third-party APIs, no telemetry, no analytics.

### What the skill writes to disk

| Path | Contents |
|---|---|
| `~/.config/runflow/credentials.json` | API key, chmod 600 |
| `~/.config/runflow/brand-kits/<slug>.json` | User-defined brand kits |
| `~/Downloads/runflow-ads/<YYYY-MM-DD>-<HHMM>/` | Generated images the user explicitly picks to push live |

### Quick automated sanity check

The tools build URLs from module-level constants (`API = "https://api.runflow.io/v1"`) and pass them to `urllib.request.Request(...)`, so the URL literal lives on a different line than the `urlopen` call. The earlier `urlopen|http.client` pre-filter missed those literals entirely. Just grep every hardcoded URL in the tools directory:

```bash
grep -rohE "https?://[a-zA-Z0-9./_:-]+" skills/runflow-ad-creative/tools/ | sort -u
```

Expected output (and nothing else):

```
http://localhost:
https://api.runflow.io/v1
https://app.runflow.io
https://app.runflow.io/connect/api-key
https://app.runflow.io/settings/api-keys
https://example.com
https://www.runflow.io
```

`example.com` is a docstring placeholder; `localhost` is the OAuth loopback. Everything else is `*.runflow.io`. If the grep returns any other domain, stop and inspect.

Hard-coded URLs in the tools:
- `https://api.runflow.io/v1` (constant `API` in `tools/create_ad.py`, `tools/feedback.py`)
- `https://app.runflow.io/connect/api-key` (constant `CONNECT_URL` in `tools/get_api_key.py`)

---

## First-run flow (so you can set user expectations)

1. **API key**. The skill opens `app.runflow.io/connect/api-key` in the user's browser with eleven scopes preselected. The user clicks Create. The skill catches the issued key on `localhost:5180` and writes it to `~/.config/runflow/credentials.json`.
2. **Brand kit**. The skill offers to auto-scan a website URL (extracts name, logo, primary color, typeface from the homepage's meta tags) or take typed input. Saved to `~/.config/runflow/brand-kits/<slug>.json` so `/plugin update` cannot wipe it.
3. **Ad generation**. The skill asks for a hero image (local file path, public URL, or an Adspirer-sourced winning creative), copy stack (with an opt-in drafting offer), tone, and target platforms. Builds an aspect-ratio set from the platforms, fires one parallel run per ratio against `runflow-access/brand-locked-variant-nux`, returns a numbered table.
4. **Selection**. The user picks which variants go live. Selected files download to `~/Downloads/runflow-ads/<timestamp>/`. Per-variant feedback (positive on picks, negative with reason if the user volunteered critique) is sent silently to the auto-generated Sentinel evaluation tied to each run.

### Requirements you should surface to the user before they install

- A Runflow account at `https://app.runflow.io`. Sign-up is free; sign-up credits cover one to two batches.
- Roughly **$0.06 per generation run**. A typical batch of 3–4 formats costs **$0.18–$0.24**.
- Python 3.9+ on PATH. The skill's tools are stdlib-only (no `pip install` step).
- Local execution. The OAuth helper needs to open a browser and bind a local loopback port. If your agent environment is fully sandboxed (no browser, no local processes), warn the user that the skill can be uploaded here but the first-run key step has to happen on their real desktop.

---

## What to tell the user AFTER you install the skill

> The skill is installed. To kick it off, ask Claude something like:
>
> _"Make a Runflow ad for the spring launch, hero is /path/to/hero.jpg, running on Meta and TikTok."_
>
> The first run will walk you through connecting your Runflow API key (one browser click) and setting up a brand kit (paste your website URL or type it in once). Every run after that goes straight to the variant table.

That is enough for them to start. If they ask for help mid-flow, the SKILL.md covers it.
