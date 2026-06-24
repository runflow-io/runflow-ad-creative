#!/usr/bin/env python3
"""compose_explainer.py — assemble an on-brand "how it works" explainer ad.

Part of the runflow-ad-creative skill. Takes the hero (input) image plus the
brand-locked variants produced by create_ad.py and renders a Runflow-branded
multi-panel composite: input photo -> generated variants, each labelled, with
the Runflow mark and a headline whose ACTION phrase is highlighted in amber
(brand rule: highlight the verb/action, rest stays white on dark).

This keeps composite/explainer creatives INSIDE the skill — never hand-built in
raw HTML or a design tool. Output is one PNG per requested outer aspect ratio.

Usage:
  python3 compose_explainer.py \
    --hero input.png \
    --variant "1:1 feed=out-1x1.png" \
    --variant "4:5 feed=out-4x5.png" \
    --headline "One product photo in, [[a full set of ads]] out." \
    --subhead "Brand-locked and resized for every placement, in minutes." \
    --cta "Generate yours" --url "runflow.io" \
    --formats 1:1,4:5 --out ~/Downloads/runflow-ads/explainer

--variant is repeatable; value is "<label>=<path-or-https-url>". Wrap the action
phrase of --headline in [[double brackets]] to highlight it amber.
"""
import argparse, base64, datetime, mimetypes, os, re, shutil, subprocess, sys, tempfile, urllib.request

CANVAS = {"1:1": (1080, 1080), "4:5": (1080, 1350), "9:16": (1080, 1920), "16:9": (1280, 720)}

def find_chrome():
    for p in [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        shutil.which("google-chrome"), shutil.which("chromium"), shutil.which("chrome"),
    ]:
        if p and os.path.exists(p):
            return p
    sys.exit("Chrome/Chromium not found — needed to render the composite.")

def data_uri(src):
    if src.startswith("http"):
        with urllib.request.urlopen(src) as r:
            raw = r.read()
        mime = "image/png"
    else:
        src = os.path.expanduser(src)
        raw = open(src, "rb").read()
        mime = mimetypes.guess_type(src)[0] or "image/png"
    return f"data:{mime};base64," + base64.b64encode(raw).decode()

def headline_html(text):
    # [[action]] -> amber span; the rest stays neutral (white on the dark frame).
    return re.sub(r"\[\[(.+?)\]\]", r'<span class="amber">\1</span>', text)

def build_html(canvas_w, canvas_h, hero_uri, variants, headline, subhead, cta, url):
    panels = "".join(
        f'<div class="panel"><div class="label">{lbl}</div>'
        f'<div class="frame {"por" if "4:5" in lbl or "9:16" in lbl else "sq"}"><img src="{uri}"></div></div>'
        for lbl, uri in variants
    )
    return f"""<!doctype html><html><head><meta charset=utf-8>
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Outfit:wght@400;500;600;700;800&display=swap" rel=stylesheet>
<style>
 *{{box-sizing:border-box;margin:0;padding:0}} html,body{{background:#09090B}}
 .canvas{{width:{canvas_w}px;height:{canvas_h}px;background:#09090B;color:#fff;
   font-family:'Outfit',-apple-system,sans-serif;padding:64px 64px 56px;display:flex;flex-direction:column}}
 .brand{{display:flex;align-items:center;gap:14px}}
 .bar{{width:42px;height:16px;border-radius:999px;background:linear-gradient(90deg,#fff,#F59E0B)}}
 .wm{{font-weight:800;font-size:26px;letter-spacing:-0.02em}} .wm .f{{color:#F59E0B}}
 h1{{font-weight:800;font-size:54px;line-height:1.04;letter-spacing:-0.03em;margin-top:34px}}
 h1 .amber{{color:#F59E0B}}
 .sub{{font-weight:400;font-size:21px;color:#A1A1AA;margin-top:16px;letter-spacing:-0.01em}}
 .panels{{flex:1;display:flex;align-items:center;justify-content:center;gap:26px;margin-top:30px}}
 .arrow{{font-size:46px;color:#F59E0B;font-weight:700}}
 .outs{{display:flex;gap:22px;align-items:flex-start}}
 .panel{{display:flex;flex-direction:column;gap:12px}}
 .label{{font-family:'Space Mono',monospace;font-weight:700;font-size:13px;letter-spacing:0.1em;text-transform:uppercase;color:#A1A1AA}}
 .frame{{border-radius:18px;overflow:hidden;border:1px solid #27272A;background:#000}}
 .frame img{{display:block;width:100%;height:100%;object-fit:cover}}
 .sq{{width:268px;height:268px}} .por{{width:268px;height:335px}}
 .footer{{display:flex;align-items:center;gap:18px;margin-top:30px}}
 .cta{{background:#F59E0B;color:#09090B;font-weight:700;font-size:19px;padding:14px 26px;border-radius:999px}}
 .url{{font-family:'Space Mono',monospace;font-size:15px;color:#A1A1AA;letter-spacing:0.04em}}
</style></head><body>
<div class="canvas">
  <div class="brand"><div class="bar"></div><div class="wm">Run<span class="f">flow</span></div></div>
  <h1>{headline_html(headline)}</h1>
  {f'<div class="sub">{subhead}</div>' if subhead else ''}
  <div class="panels">
    <div class="panel"><div class="label">Your photo</div><div class="frame sq"><img src="{hero_uri}"></div></div>
    <div class="arrow">&rarr;</div>
    <div class="outs">{panels}</div>
  </div>
  <div class="footer"><div class="cta">{cta}</div><div class="url">{url}</div></div>
</div></body></html>"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hero", required=True)
    ap.add_argument("--variant", action="append", required=True, help='"<label>=<path-or-url>", repeatable')
    ap.add_argument("--headline", required=True, help="wrap the action phrase in [[ ]] to highlight amber")
    ap.add_argument("--subhead", default="")
    ap.add_argument("--cta", default="Generate yours")
    ap.add_argument("--url", default="runflow.io")
    ap.add_argument("--formats", default="1:1,4:5", help="outer canvas ratios for the explainer")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    chrome = find_chrome()
    hero_uri = data_uri(args.hero)
    variants = []
    for v in args.variant:
        if "=" not in v:
            sys.exit(f"--variant must be '<label>=<path-or-url>', got {v!r}")
        lbl, src = v.split("=", 1)
        variants.append((lbl.strip(), data_uri(src.strip())))

    out_dir = os.path.expanduser(args.out) or os.path.join(
        os.path.expanduser("~/Downloads/runflow-ads"),
        datetime.date.today().isoformat() + "-explainer")
    os.makedirs(out_dir, exist_ok=True)
    tmp = tempfile.mkdtemp()
    results = []
    for fmt in [f.strip() for f in args.formats.split(",") if f.strip()]:
        if fmt not in CANVAS:
            sys.exit(f"unsupported format {fmt}; allowed: {list(CANVAS)}")
        w, h = CANVAS[fmt]
        html_path = os.path.join(tmp, f"explainer-{fmt.replace(':','x')}.html")
        open(html_path, "w").write(build_html(w, h, hero_uri, variants, args.headline, args.subhead, args.cta, args.url))
        out_png = os.path.join(out_dir, f"explainer-{fmt.replace(':','x')}.png")
        subprocess.run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
            "--force-device-scale-factor=1", f"--window-size={w},{h}",
            f"--screenshot={out_png}", f"file://{html_path}"], capture_output=True)
        if os.path.exists(out_png):
            results.append(out_png)
            print(f"EXPLAINER[{fmt}] -> {out_png}")
        else:
            print(f"EXPLAINER[{fmt}] FAILED")
    print("\nRESULTS:", results)
    print("\nNEXT: present these on the templates-subdomain preview (never hand off loose files as the result).")

if __name__ == "__main__":
    main()
