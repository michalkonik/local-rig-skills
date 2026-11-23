#!/usr/bin/env python3
"""Split a transcript into overlapping chunks and print a compact index.

  chunk_transcript.py INPUT [--size 12000] [--overlap 600]     INPUT = a .md/.txt file, or "-" for stdin

Cuts just before a [mm:ss] cue when it can, else at a heading, a blank line, or a sentence end.
Writes <work>/c01.md ... and prints one line per chunk: id, size, timestamp range, first words.
Work dir: <input>.chunks/ next to the input (stdin: ~/Documents/notes/stdin-<time>.chunks/).
Prints the summary path (<input>.summary.md) and whether the file has timestamps.
Inputs under --size are not split: read the file directly.
"""
import argparse, datetime, pathlib, re, sys

TS = re.compile(r"\[(\d{1,2}:)?\d{1,2}:\d{2}\]")


def cut_point(text, start, size):
    """Best end for a chunk starting at `start`: before a timestamp, else a heading, blank line, or sentence."""
    end = start + size
    if end >= len(text):
        return len(text)
    window = text[start + size // 2:end]
    for pat in (r".(?=\[\d{1,2}:\d{2}(?::\d{2})?\])", r"\n#{1,6} ", r"\n\s*\n", r"[.!?…][\"')\]]?\s"):
        hits = [m.end() if pat.startswith("[") else m.start() + 1 for m in re.finditer(pat, window)]
        if hits:
            return start + size // 2 + hits[-1]
    return end


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--size", type=int, default=12000)
    ap.add_argument("--overlap", type=int, default=600)
    a = ap.parse_args()
    if a.input == "-":
        text = sys.stdin.read()
        base = pathlib.Path.home() / f"Documents/notes/stdin-{datetime.datetime.now():%Y%m%d-%H%M}"
        base.parent.mkdir(parents=True, exist_ok=True)
        (base.with_suffix(".txt")).write_text(text)
    else:
        src = pathlib.Path(a.input).expanduser()
        text = src.read_text(errors="ignore")
        base = src.with_suffix("")
    summary = f"{base}.summary.md"
    words = len(text.split())
    stamps = TS.findall(text)
    kind = "timestamped transcript" if len(stamps) >= 3 else "not a timestamped transcript"
    print(f"input {len(text)} chars, {words} words, {len(stamps)} timestamps, {kind}; summary -> {summary}")
    if len(text) <= a.size:
        print("short enough: read the whole input directly, no chunks written")
        return
    work = pathlib.Path(f"{base}.chunks")
    work.mkdir(parents=True, exist_ok=True)
    for old in work.glob("c*.md"):
        old.unlink()
    start, n, last_ts = 0, 0, None
    while start < len(text):
        end = cut_point(text, start, a.size)
        chunk = text[start:end]
        n += 1
        stamps = [m.group(0).strip("[]") for m in TS.finditer(chunk)]
        first_ts = stamps[0] if stamps else last_ts
        span = f"[{first_ts}-{stamps[-1]}]" if stamps else ""
        last_ts = stamps[-1] if stamps else last_ts
        cid = f"c{n:02d}"
        (work / f"{cid}.md").write_text(f"<!-- chunk {cid} chars {start}-{end} {span} -->\n{chunk}")
        head = " ".join(TS.sub("", chunk).split()[:10])
        print(f"{cid} {len(chunk):6d} ch {span:16} {head[:70]}")
        if end >= len(text):
            break
        nxt = end - a.overlap
        sp = text.find(" ", nxt)
        start = max(sp + 1 if 0 <= sp < end else nxt, start + 1)
    print(f"{n} chunks in {work}/ (overlap {a.overlap} chars: a point cut at a boundary appears in both)")


if __name__ == "__main__":
    main()
