#!/usr/bin/env python3
"""Check a videos-transcriptions summary.md against the headings in that repo's README.

  check_summary.py PATH

Prints OK or ERROR. Headings must stay in lockstep with
~/Desktop/github_repos/videos-transcriptions/README.md (Summary section).
"""
import pathlib, sys

KINDS = {
    "general": ["TL;DR", "Key points", "Actionable takeaways", "Open questions", "Skip/skim map"],
    "investment": ["TL;DR", "Trades", "Key points", "Actionable takeaways", "Open questions", "Skip/skim map"],
    "technical": ["TL;DR", "How it works", "Key points", "Actionable takeaways", "Open questions", "Skip/skim map"],
    "earning": ["TL;DR", "Opportunities", "Setup", "Key points", "Actionable takeaways",
                "Open questions", "Skip/skim map"],
}
FIELDS = ("URL:", "What it is:", "What to do:", "Requirements:", "Money:", "Risk:")


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: check_summary.py SUMMARY.md")
    path = pathlib.Path(sys.argv[1])
    text = path.read_text(errors="ignore")
    kind = next((ln.split(":", 1)[1].strip() for ln in text.splitlines() if ln.startswith("Kind:")), "")
    if kind not in KINDS:
        sys.exit(f"ERROR {path}: Kind must be one of {', '.join(KINDS)}")
    if "Transcript: transcript.md" not in text:
        sys.exit(f"ERROR {path}: missing 'Transcript: transcript.md'")
    heads = [ln[3:].strip() for ln in text.splitlines() if ln.startswith("## ")]
    if heads != KINDS[kind]:
        sys.exit(f"ERROR {path}: headings {heads} != {KINDS[kind]}")
    if kind == "earning":
        body = text.split("## Opportunities", 1)[1].split("\n## ", 1)[0]
        blocks = [b for b in body.split("\n### ") if b.strip()]
        if not blocks:
            sys.exit(f"ERROR {path}: Opportunities has no entries")
        for i, block in enumerate(blocks, 1):
            missing = [f for f in FIELDS if f"- {f}" not in block]
            if missing:
                sys.exit(f"ERROR {path}: opportunity {i} missing {', '.join(missing)}")
    print(f"OK {path} kind {kind}")


if __name__ == "__main__":
    main()
