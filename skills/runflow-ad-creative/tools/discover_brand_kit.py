#!/usr/bin/env python3
"""Lightweight brand-kit auto-discovery from a website URL.

Fetches the homepage HTML and extracts:
  - name        from <title> (split on common separators)
  - logo_url    from og:image meta, then favicon link
  - primary_color from <meta name="theme-color">
  - typeface    from Google Fonts <link>, then first font-family declaration

Anything not found is returned as null so the skill can ask the user to fill it.

Usage:
  python3 discover_brand_kit.py https://example.com
Prints a JSON object to stdout.
"""
import html as _html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request


UA = "Mozilla/5.0 (compatible; RunflowBrandDiscover/0.1; +https://www.runflow.io)"
TIMEOUT_S = 15


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
        raw = r.read()
        return raw.decode("utf-8", errors="replace")


def _abs(base: str, href: str) -> str:
    return urllib.parse.urljoin(base, href)


def extract_name(html: str):
    # og:site_name is the most reliable signal for the brand name.
    m = re.search(
        r'<meta[^>]+property=["\']og:site_name["\'][^>]*content=["\']([^"\']+)["\']',
        html, re.IGNORECASE,
    )
    if m:
        return _html.unescape(m.group(1).strip()) or None
    # Fall back to <title>, trimmed of boilerplate suffixes.
    m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
    if not m:
        return None
    title = _html.unescape(m.group(1).strip())
    for sep in (" — ", " | ", " - ", " : ", " · "):
        if sep in title:
            title = title.split(sep)[0].strip()
            break
    return title or None


def extract_logo(base: str, html: str):
    # Apple touch icons are usually the cleanest brand logo we can find on the
    # homepage HTML. Favicons next. og:image last — it's frequently a social
    # share card, not the wordmark.
    for pat in (
        r'<link[^>]+rel=["\']apple-touch-icon[^"\']*["\'][^>]+href=["\']([^"\']+)["\']',
        r'<link[^>]+rel=["\']icon["\'][^>]+href=["\']([^"\']+)["\']',
        r'<link[^>]+rel=["\']shortcut icon["\'][^>]+href=["\']([^"\']+)["\']',
        r'<meta[^>]+property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']',
    ):
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            return _abs(base, _html.unescape(m.group(1)))
    return None


def extract_primary_color(html: str):
    m = re.search(
        r'<meta[^>]+name=["\']theme-color["\'][^>]*content=["\']([^"\']+)["\']',
        html, re.IGNORECASE,
    )
    return m.group(1).strip() if m else None


def _resolve_css_var(html: str, var_name: str):
    """If a CSS custom property is declared inline in the page, return its value."""
    pat = rf"--{re.escape(var_name)}\s*:\s*([^;}}\"']+)"
    m = re.search(pat, html, re.IGNORECASE)
    if not m:
        return None
    val = m.group(1).strip().strip("'\"")
    # The value may itself be a font stack; take the first family.
    return val.split(",")[0].strip().strip("'\"") or None


def extract_typeface(html: str):
    # Google Fonts: ?family=Outfit:wght@300...
    m = re.search(r"fonts\.googleapis\.com/css2?\?family=([^&\"']+)", html, re.IGNORECASE)
    if m:
        first = m.group(1).split("|")[0].split(":")[0]
        return urllib.parse.unquote(first).replace("+", " ").strip() or None
    # Fall back: first font-family declaration in inline CSS.
    m = re.search(r"font-family\s*:\s*[\"']?([^,;\"'<>]+)", html, re.IGNORECASE)
    if not m:
        return None
    candidate = m.group(1).strip().strip("'\"")
    # Resolve a CSS custom property if that's what we got (e.g. "var(--font-sans)").
    var_m = re.match(r"var\(\s*--([\w-]+)\s*\)", candidate, re.IGNORECASE)
    if var_m:
        resolved = _resolve_css_var(html, var_m.group(1))
        if resolved:
            return resolved
    return candidate or None


def discover(url: str) -> dict:
    if not re.match(r"^https?://", url):
        url = "https://" + url
    try:
        html = fetch(url)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        return {
            "url": url,
            "error": f"could not fetch {url}: {e}",
            "name": None,
            "logo_url": None,
            "primary_color": None,
            "typeface": None,
        }
    return {
        "url": url,
        "name": extract_name(html),
        "logo_url": extract_logo(url, html),
        "primary_color": extract_primary_color(html),
        "typeface": extract_typeface(html),
    }


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: discover_brand_kit.py <url>")
    result = discover(sys.argv[1])
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
