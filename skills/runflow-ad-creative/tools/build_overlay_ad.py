#!/usr/bin/env python3
"""build_overlay_ad.py — deterministic, brand-perfect ad build for person/UGC heroes.

Part of the runflow-ad-creative skill. Chains two steps so the brand layer is
pixel-exact instead of baked (and fragile) by the image model:

  1. background-removal — runs the hero through Runflow's `runflow/background-removal`
     model to get a clean transparent cutout (fixes busy/uncut backgrounds).
  2. overlay compose — places the cutout on the Runflow brand background and renders
     the copy as REAL text: Outfit font, the action phrase highlighted in amber
     (brand rule), headline pinned to the top, logo + CTA. One PNG per aspect ratio.

Use this for person / UGC / talking-to-camera heroes where the model's baked text
(wrong font, no highlight) and dirty background are the problem. The brand-locked
ComfyUI workflow (create_ad.py) stays the path when you want the model to compose a
scene; this path is for clean, deterministic brand overlays.

Usage:
  python3 build_overlay_ad.py \
    --hero hero.jpg \
    --headline "Wait, it also [[learns your brand]]?" \
    --subhead "Generate ads and train a mini brand model" \
    --cta "See how" --formats 1:1,4:5 --out ~/Downloads/runflow-ads/overlay

Wrap the headline's action phrase in [[ ]] to highlight it amber. RUNFLOW_API_KEY
must be set (same as create_ad.py).
"""
import argparse, base64, datetime, json, os, re, shutil, subprocess, sys, time, urllib.request

BASE="https://api.runflow.io"
CANVAS={"1:1":(1080,1080),"4:5":(1080,1350),"9:16":(1080,1920),"16:9":(1280,720)}

def key():
    k=os.environ.get("RUNFLOW_API_KEY")
    if not k:
        p=os.path.expanduser("~/.config/runflow/credentials.json")
        if os.path.exists(p): k=json.load(open(p)).get("api_key")
    if not k: sys.exit("RUNFLOW_API_KEY not set")
    return k

def api(method, path, body=None, k=None):
    data=json.dumps(body).encode() if body is not None else None
    r=urllib.request.Request(BASE+path, data=data, method=method,
        headers={"Authorization":f"Bearer {k}","Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(r) as resp: return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")

def remove_bg(local_path, k):
    """Upload the hero and run background-removal. Returns the transparent cutout bytes."""
    size=os.path.getsize(local_path); mime="image/jpeg" if local_path.lower().endswith((".jpg",".jpeg")) else "image/png"
    st,up=api("POST","/v1/asset-uploads",{"filename":os.path.basename(local_path),"mime_type":mime,"size_bytes":size},k)
    if st>=300: sys.exit(f"presign failed: {up}")
    urllib.request.urlopen(urllib.request.Request(up["upload_url"], data=open(local_path,"rb").read(),
        method="PUT", headers={"Content-Type":mime}))
    api("POST",f"/v1/asset-uploads/{up['asset_id']}/confirmations",{},k)
    st,asset=api("GET",f"/v1/assets/{up['asset_id']}",None,k)
    st,run=api("POST","/v1/models/runflow/background-removal/runs",{"input":{"image_url":asset["url"]}},k)
    if st>=300: sys.exit(f"background-removal failed: {run}")
    rid=run["id"]
    for _ in range(90):
        st,r=api("GET",f"/v1/runs/{rid}?add_signature=true",None,k)
        if r.get("status_code") in ("succeeded","partial_succeeded","failed","cancelled"): break
        time.sleep(2)
    urls=(r.get("output") or {}).get("image_urls") or []
    if not urls: sys.exit(f"background-removal returned no image (status {r.get('status_code')})")
    return urllib.request.urlopen(urls[0]).read()

def find_chrome():
    for p in ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              "/Applications/Chromium.app/Contents/MacOS/Chromium",
              shutil.which("google-chrome"), shutil.which("chromium")]:
        if p and os.path.exists(p): return p
    sys.exit("Chrome/Chromium not found")

def headline_html(t):
    return re.sub(r"\[\[(.+?)\]\]", r'<span class="amber">\1</span>', t)

def html(w, h, cutout_uri, headline, subhead, cta, url):
    return f"""<!doctype html><html><head><meta charset=utf-8>
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Outfit:wght@400;500;600;700;800&display=swap" rel=stylesheet>
<style>
 *{{box-sizing:border-box;margin:0;padding:0}} html,body{{background:#09090B}}
 .c{{position:relative;width:{w}px;height:{h}px;background:radial-gradient(120% 80% at 50% 0%, #1A1A1F 0%, #09090B 60%);
   color:#fff;font-family:'Outfit',-apple-system,sans-serif;overflow:hidden}}
 .hero{{position:absolute;left:50%;bottom:0;transform:translateX(-50%);height:76%;z-index:1}}
 .hero img{{height:100%;width:auto;object-fit:contain;object-position:bottom}}
 .brand{{position:absolute;top:40px;left:50%;transform:translateX(-50%);display:flex;align-items:center;gap:12px;z-index:3}}
 .bar{{width:38px;height:14px;border-radius:999px;background:linear-gradient(90deg,#fff,#F59E0B)}}
 .wm{{font-weight:800;font-size:22px;letter-spacing:-0.02em}} .wm .f{{color:#F59E0B}}
 .copy{{position:absolute;top:96px;left:0;right:0;padding:0 64px;text-align:center;z-index:3}}
 h1{{font-weight:800;font-size:52px;line-height:1.05;letter-spacing:-0.03em;text-wrap:balance}}
 h1 .amber{{color:#F59E0B}}
 .sub{{font-weight:500;font-size:23px;color:#D4D4D8;margin-top:14px;letter-spacing:-0.01em}}
 .cta{{position:absolute;bottom:56px;left:50%;transform:translateX(-50%);z-index:4;
   background:#F59E0B;color:#09090B;font-weight:700;font-size:21px;padding:16px 34px;border-radius:999px;
   box-shadow:0 8px 30px rgba(0,0,0,0.4)}}
</style></head><body>
<div class="c">
  <div class="hero"><img src="{cutout_uri}"></div>
  <div class="brand"><div class="bar"></div><div class="wm">Run<span class="f">flow</span></div></div>
  <div class="copy"><h1>{headline_html(headline)}</h1>{f'<div class="sub">{subhead}</div>' if subhead else ''}</div>
  <div class="cta">{cta}</div>
</div></body></html>"""

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--hero",default="",help="raw hero photo; background-removed automatically (or pass --cutout)")
    ap.add_argument("--headline",required=True,help="wrap the action phrase in [[ ]] for amber")
    ap.add_argument("--subhead",default="")
    ap.add_argument("--cta",default="See how")
    ap.add_argument("--url",default="runflow.io")
    ap.add_argument("--formats",default="1:1,4:5")
    ap.add_argument("--out",default="")
    ap.add_argument("--cutout",default="",help="reuse an already-cut webp/png instead of re-running bg-removal")
    args=ap.parse_args()

    if not args.cutout and not args.hero:
        sys.exit("pass --hero (to background-remove) or --cutout (already cut)")
    if args.cutout:
        cutout=open(os.path.expanduser(args.cutout),"rb").read()
        mime="image/webp" if args.cutout.lower().endswith(".webp") else "image/png"
    else:
        print("[bg] removing background…",flush=True)
        cutout=remove_bg(os.path.expanduser(args.hero), key()); mime="image/webp"
    cutout_uri=f"data:{mime};base64,"+base64.b64encode(cutout).decode()

    chrome=find_chrome()
    out_dir=os.path.expanduser(args.out) or os.path.join(os.path.expanduser("~/Downloads/runflow-ads"),
        datetime.date.today().isoformat()+"-overlay")
    os.makedirs(out_dir,exist_ok=True)
    import tempfile; tmp=tempfile.mkdtemp()
    for fmt in [f.strip() for f in args.formats.split(",") if f.strip()]:
        if fmt not in CANVAS: sys.exit(f"bad format {fmt}")
        w,hh=CANVAS[fmt]
        hp=os.path.join(tmp,f"ad-{fmt.replace(':','x')}.html")
        open(hp,"w").write(html(w,hh,cutout_uri,args.headline,args.subhead,args.cta,args.url))
        outp=os.path.join(out_dir,f"ad-{fmt.replace(':','x')}.png")
        subprocess.run([chrome,"--headless=new","--disable-gpu","--hide-scrollbars",
            "--force-device-scale-factor=1",f"--window-size={w},{hh}",f"--screenshot={outp}",f"file://{hp}"],
            capture_output=True)
        print(f"AD[{fmt}] -> {outp}" if os.path.exists(outp) else f"AD[{fmt}] FAILED",flush=True)

if __name__=="__main__":
    main()
