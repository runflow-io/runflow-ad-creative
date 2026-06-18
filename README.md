# runflow-ad-creative

A Claude Code skill for generating brand-locked ad creatives. Drop a hero image, pick a brand kit, get on-brand ad variants for every platform you're running on.

Powered by Runflow's `brand-locked-variant-nux` ComfyUI workflow on the back end. One install, one prompt, one set of variants per ad surface.

## Install

Pick the path that matches your environment.

### Claude Code (CLI, VS Code, JetBrains, terminal)

Two slash commands. The first registers this repo as a plugin marketplace; the second installs the plugin from it.

```
/plugin marketplace add runflow-io/runflow-ad-creative
/plugin install runflow-ad-creative@runflow-ad-creative
```

Then `/reload-plugins` to activate. Update later with `/plugin update runflow-ad-creative@runflow-ad-creative`.

### Claude Cowork (desktop app, agentic mode) and claude.ai web

These environments do not accept GitHub marketplaces. Upload a `.skill` bundle instead.

1. Download the pre-built bundle: [`runflow-ad-creative.skill`](https://github.com/runflow-io/runflow-ad-creative/releases/latest/download/runflow-ad-creative.skill)
2. In the Claude app, click the `+` button next to the message box → **Upload a skill** → pick the file.

The skill lands under Personal skills. No restart needed.

### Letting an AI agent install it for you

If you ask an LLM (Claude itself, ChatGPT, anything else) to install the skill on your behalf, point it at [`AGENT_INSTALL.md`](AGENT_INSTALL.md). That file has explicit, environment-aware instructions any agent can follow without guessing.

## What you get

- **Brand-kit reuse.** Set up your brand (logo, colors, typeface, default tone, voice notes) once. Auto-scan from a website URL or type it in. Every future ad uses it.
- **Platform-aware format selection.** Tell the skill where the ads will run (Meta, IG, TikTok, YouTube, LinkedIn, Pinterest, X, Google Display) and it picks the right aspect ratios.
- **Parallel generation.** One run per format, fired in parallel. Three formats land in ~90 seconds.
- **Numbered preview table.** You see each variant with a clickable link. Pick the ones to push live by number ("1,3" / "all" / "none").
- **Quality scoring built in.** Every variant is automatically scored on brand fidelity, text rendering, hero preservation, and palette discipline by Runflow's Sentinel engine. Free.
- **Feedback that improves the model.** Your "which goes live" picks (plus any quick critique you drop in) get routed back as taste signal. The model gets better on your brand over time.

## Setup (first run)

1. The skill detects you don't have a Runflow API key. It opens `app.runflow.io/connect/api-key` in your browser with the right scopes pre-selected. Click Create. The key is captured automatically and saved to `~/.config/runflow/credentials.json`.
2. The skill detects you don't have a brand kit. It asks: auto-scan your website, or type it in. Pick one and follow the prompts.
3. You're done. Subsequent runs skip both steps.

## How to invoke

Just ask Claude. The skill triggers on explicit Runflow + ad phrases:

- "Make a Runflow ad for the spring launch, hero is `/Users/me/desktop/hero.jpg`"
- "Create ads with Runflow — same hero, fresh copy"
- "Iterate this winning ad with Runflow" (then paste the URL)
- "Brand-locked variant of this image for Meta + TikTok"

It will NOT trigger on a generic "make me an ad" — by design, so it doesn't fight other ad-creative tools you might have installed.

## What it doesn't do (yet)

- Video. This skill is static images only. Video pipeline is a separate skill.
- Auto-push to ad platforms. Selected variants download to `~/Downloads/runflow-ads/<timestamp>/`. You drop them into Meta Ads Manager, TikTok Ads, etc. yourself.
- Multi-hero batches in one prompt. Re-invoke per hero for now.

## Layout

```
runflow-ad-creative/
├── claude-plugin.json
├── README.md
├── LICENSE
└── skills/
    └── runflow-ad-creative/
        ├── SKILL.md              — interview flow + trigger rules
        ├── brand-kits/
        │   ├── README.md         — brand kit schema reference
        │   └── example.json      — schema-only template, never used as a real kit
        └── tools/
            ├── get_api_key.py    — captures a Runflow API key via local-loopback OAuth
            ├── discover_brand_kit.py — scrapes a homepage for brand fields
            ├── create_ad.py      — uploads hero + logo, fans out N parallel runs, polls
            └── feedback.py       — sends per-variant feedback back to Runflow
```

User data lives outside the plugin so `/plugin update` never touches it:

- `~/.config/runflow/credentials.json` — your API key (chmod 600)
- `~/.config/runflow/brand-kits/<slug>.json` — your brand kits
- `~/Downloads/runflow-ads/<timestamp>/` — generated assets you pushed live

## Requirements

- Python 3.9+ on PATH (stdlib only — no pip install needed).
- A Runflow account. Sign up at https://app.runflow.io if you don't have one. The skill walks you through key creation on first run.
- Credits in your Runflow account. Each run costs ~$0.06. The skill does a pre-flight balance check and warns before firing if you can't cover the batch.

## Contributing

Issues and PRs welcome at https://github.com/runflow-io/runflow-ad-creative. Brand kits are not commits — they're personal config and live in `~/.config/runflow/brand-kits/`.

## License

MIT. See [LICENSE](LICENSE).
