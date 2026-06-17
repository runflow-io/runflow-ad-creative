#!/usr/bin/env python3
"""Voice-DNA lint for short ad copy.

Runs an ad-shaped subset of the Runflow Voice DNA rules against the headline +
subhead + CTA *before* generation, so the model never burns credits on copy that
the brand will reject. Prints JSON to stdout. Exit code 0 = clean, 1 = at least
one violation (any severity).

Intentionally narrow — the full Voice DNA lint catches a lot that doesn't apply
to 6-word headlines (paragraph length, contractions philosophy, transitions).
This module focuses on the rules that actually fire on short ad copy:

  - em-dash detection                                (block)
  - banned vocab subset from anti-ai §3A             (block)
  - negative parallelism patterns from §3F           (block)
  - title-case / ALL-CAPS headline                   (warn)
  - dead phrases from §3B                            (warn)
  - opener repetition across headline / subhead      (warn)

Usage:
  python3 lint_copy.py --headline "..." --subhead "..." --cta "..."
"""
import argparse
import json
import re
import sys


# §3A — banned ad-relevant vocab. Match case-insensitively, whole-word.
BANNED_VOCAB = {
    "delve", "leverage", "leveraging", "robust", "seamless", "seamlessly",
    "streamline", "streamlining", "streamlined", "optimize", "optimizing", "optimized",
    "cutting-edge", "bleeding-edge", "state-of-the-art", "next-generation", "next-gen",
    "empower", "empowering", "empowered", "unlock", "unleash",
    "elevate", "elevating", "transform", "transformative",
    "effortless", "effortlessly", "holistic", "synergy", "synergistic",
    "furthermore", "additionally",
    "revolutionary", "revolutionize", "game-changing", "game-changer",
    "unparalleled", "unprecedented",
    "best-in-class", "world-class",
    "harness", "supercharge", "turbocharge",
}

# §3B — dead phrases. Case-insensitive substring match.
DEAD_PHRASES = [
    "in today's", "let's dive in", "let's explore", "let's unpack",
    "at the end of the day", "moving forward",
    "it's important to note", "it's worth noting",
    "in order to",
    "that said",
]

# §3F — negative parallelism. Pattern hints; will have false positives, hence "warn".
NEG_PARALLEL_PATTERNS = [
    r"\bnot just\b",                       # "Not just X..."
    r"\bisn'?t (just )?\w+,?\s+(it'?s|but)\b",   # "This isn't X, it's Y" / "This isn't X but Y"
    r"\bwe don'?t \w+,?\s*we \w+\b",       # "We don't X. We Y"
    r"\bforget \w+,?\s+(try|use|get)\b",   # "Forget X, try Y"
    r"\bstop \w+ing,?\s+start \w+ing\b",   # "Stop X-ing, start Y-ing"
]


def _check_em_dash(field: str, text: str):
    if "—" in text or "–" in text:
        return [{
            "field": field, "rule": "em_dash", "severity": "block",
            "matched": "—" if "—" in text else "–",
            "fix_hint": "Replace with comma, period, colon, or parentheses.",
        }]
    return []


def _check_banned_vocab(field: str, text: str):
    hits = []
    for word in BANNED_VOCAB:
        if re.search(rf"\b{re.escape(word)}\b", text, re.IGNORECASE):
            hits.append({
                "field": field, "rule": "banned_vocab", "severity": "block",
                "matched": word,
                "fix_hint": "Rephrase without the AI-marketing vocab.",
            })
    return hits


def _check_dead_phrase(field: str, text: str):
    hits = []
    lower = text.lower()
    for phrase in DEAD_PHRASES:
        if phrase in lower:
            hits.append({
                "field": field, "rule": "dead_phrase", "severity": "warn",
                "matched": phrase,
                "fix_hint": "Cut the throat-clearing.",
            })
    return hits


def _check_negative_parallelism(field: str, text: str):
    hits = []
    for pat in NEG_PARALLEL_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            hits.append({
                "field": field, "rule": "negative_parallelism", "severity": "block",
                "matched": m.group(0),
                "fix_hint": "Drop the 'not X, but Y' contrast. State the actual claim.",
            })
    return hits


def _check_case(field: str, text: str):
    """Warn on Title Case or ALL CAPS headlines. Sentence case is the Runflow default."""
    words = [w for w in re.findall(r"[A-Za-z]+", text) if len(w) > 0]
    if len(words) < 2:
        return []
    # ALL CAPS
    if all(w.isupper() for w in words):
        return [{
            "field": field, "rule": "all_caps", "severity": "warn",
            "matched": text,
            "fix_hint": "Use sentence case unless the brand kit calls for caps explicitly.",
        }]
    # Title Case heuristic: every word starts with uppercase, and there's no all-lowercase
    # short word (like "to", "the") — those usually stay lowercase in real Title Case.
    capitalized = sum(1 for w in words if w[0].isupper())
    if capitalized == len(words) and len(words) >= 3:
        return [{
            "field": field, "rule": "title_case", "severity": "warn",
            "matched": text,
            "fix_hint": "Sentence case is the Runflow default — only first word capitalized.",
        }]
    return []


def _check_opener_repetition(headline: str, subhead: str):
    """Warn if headline and subhead start with the same word (low variety)."""
    def first_word(s):
        m = re.match(r"\s*([A-Za-z']+)", s)
        return m.group(1).lower() if m else ""
    h, s = first_word(headline), first_word(subhead)
    if h and h == s:
        return [{
            "field": "subhead", "rule": "opener_repetition", "severity": "warn",
            "matched": h,
            "fix_hint": f"Subhead opens with the same word as the headline ('{h}'). Vary it.",
        }]
    return []


def lint(headline: str, subhead: str, cta: str) -> dict:
    violations = []
    for field, text in (("headline", headline), ("subhead", subhead), ("cta", cta)):
        violations += _check_em_dash(field, text)
        violations += _check_banned_vocab(field, text)
        violations += _check_dead_phrase(field, text)
        violations += _check_negative_parallelism(field, text)
        if field in ("headline", "subhead"):
            violations += _check_case(field, text)
    violations += _check_opener_repetition(headline, subhead)
    summary = {"block": 0, "warn": 0}
    for v in violations:
        summary[v["severity"]] = summary.get(v["severity"], 0) + 1
    return {"violations": violations, "summary": summary, "clean": not violations}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--headline", required=True)
    p.add_argument("--subhead", required=True)
    p.add_argument("--cta", required=True)
    args = p.parse_args()

    result = lint(args.headline, args.subhead, args.cta)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["clean"] else 1)


if __name__ == "__main__":
    main()
