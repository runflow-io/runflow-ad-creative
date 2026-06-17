# Brand kits

This directory ships a single `example.json` schema reference. **User brand kits
live outside the plugin directory** at `~/.config/runflow/brand-kits/<slug>.json`
so that `/plugin update` never overwrites them.

The skill reads from both locations — user-config first, this plugin dir as a
legacy fallback. New kits are always written to the user-config path.

`example.json` is a schema-only template — the skill ignores it when listing
real kits. Copy it to `~/.config/runflow/brand-kits/<your-slug>.json` to start
a new one (or just let the skill's interview flow do that for you on first run).

## Schema

```json
{
  "slug": "<lowercase-kebab>",
  "name": "<Display Name>",
  "logo_url": null,
  "logo_path": "/absolute/path/to/logo.png",
  "primary_color": "#09090B",
  "accent_color": "#FBBF24",
  "typeface": "Outfit",
  "default_tone": "premium",
  "voice_notes": "<short string of voice constraints>"
}
```

### Fields

| Field | Required | Notes |
|---|---|---|
| `slug` | yes | Lowercase kebab-case. Matches the filename (e.g. `runflow.json` → `runflow`). |
| `name` | yes | Human-readable brand name. |
| `logo_url` | one-of | HTTPS URL of an existing logo asset. Preferred for team use — survives across machines. |
| `logo_path` | one-of | Absolute local path. Used when `logo_url` is null. Script uploads it to Runflow on each run. |
| `primary_color` | yes | Hex. Drives the `Primary brand color: …` line in the prompt. |
| `accent_color` | no | Hex. Currently informational; reserved for prompt-template v2. |
| `typeface` | yes | Font family name. Goes into `Use the typography of: …`. |
| `default_tone` | yes | One of `premium / playful / urgent / technical / editorial / friendly`. The skill still always asks per-run. |
| `voice_notes` | no | Free-text voice constraints, shown to the user during the copy step as a soft check. |

Sentinel quality scoring on each variant + thumbs-up/down feedback routing from the
"which goes live" step are always on. They're free for ComfyUI workflow outputs, so
the skill doesn't expose a toggle. If you ever need to silence them per-brand, the
helper functions live in `tools/create_ad.py` and `tools/feedback.py`.

### One of `logo_url` or `logo_path` is required

- Prefer `logo_url` for shared/team brand kits — every teammate gets the same asset.
- Use `logo_path` for personal kits or when the logo PNG lives in this repo (path is stable).
- If both are set, `logo_url` wins.

## Adding a brand

1. Pick a slug (`betterpic`, `maison-zola`, etc.).
2. Drop the logo PNG somewhere stable (this repo's `assets/` dir is a good home for
   team-shared logos).
3. Create `<slug>.json` with the schema above.
4. Commit.

## Updating a brand

Edit the JSON in place. The skill re-reads it on every run, so no restart needed.
If the logo asset URL changed, refresh `logo_url`; if you only have the new file
locally, drop the new PNG and update `logo_path`.

## Inspecting

The skill's `create_ad.py` will print a clear error if the kit is missing or
malformed. To dry-check a kit:

```bash
python3 -c "import json; print(json.load(open('runflow.json')))"
```
