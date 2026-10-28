#!/usr/bin/env python3
"""Measure a llama-swap model's speed the same way every time, and compare two measurements.

  bench.py run MODEL [--n 1,4] [--label before]     -> ~/.local/state/rig-skills/bench/<model>-<label>-<time>.json
  bench.py compare A.json B.json                     per prompt/concurrency: tok/s per stream, total, TTFT, change %
  bench.py list [MODEL]                              saved measurements

Uses local-llm-perf-bench/server-bench/bench_stream.py (client-side timing, engine-neutral): a "chat" prompt
(~700 tokens of prose) and "code16k" (~14k-token file + rewrite), each twice, at concurrency 1 and 4 by default.
Sampling = the entry's own --temp/--top-p/--top-k (vendor defaults) - speculative decoding looks much better at
temperature 0 than in real chats, so never benchmark greedy. One run takes 2-6 minutes; first run after a load is
a warm-up (rep 0), compare rep 1 values. Run before AND after a change, nothing else using the GPUs.
"""
import json, os, pathlib, re, subprocess, sys, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import rig

OUT = rig.STATE / "bench"


def sampling(m):
    cmd = m["cmd"]
    g = lambda flag, d: (re.search(rf"{flag}\s+([\d.]+)", cmd) or [None, d])[1]
    return g("--temp", "0.7"), g("--top-p", "0.95"), g("--top-k", "20")


def run(model, n, label):
    mid = rig.resolve_model(model)
    t, p, k = sampling(rig.models()[mid])
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"{mid}-{label}-{rig.now()}.json"
    env = dict(os.environ, BENCH_N=n)
    print(f"bench {mid} (temp {t} top_p {p} top_k {k}), concurrency {n} -> {out}", flush=True)
    r = subprocess.run([sys.executable, str(rig.BENCH / "bench_stream.py"), mid, t, p, k, str(out)], env=env)
    if r.returncode == 0:
        rig.journal("bench", f"{mid} {label}: {out}")
        summary(out)


def best(d):
    """rep 1 (after warm-up) where present, else rep 0."""
    res = {}
    for r in d["results"]:
        key = (r["prompt"], r["conc"])
        if key not in res or r["rep"] == 1:
            res[key] = r
    return res


def summary(path):
    d = json.load(open(path))
    for (pr, c), r in sorted(best(d).items()):
        print(f"  {pr:8} x{c:<2} {r['per_stream']:7.1f} tok/s per stream {r['total']:7.1f} total  ttft {r['ttft']:5.2f} s")


def compare(a, b):
    A, B = best(json.load(open(a))), best(json.load(open(b)))
    print(f"A = {a}\nB = {b}")
    for key in sorted(set(A) & set(B)):
        x, y = A[key], B[key]
        ch = (y["per_stream"] / x["per_stream"] - 1) * 100 if x["per_stream"] else 0
        print(f"  {key[0]:8} x{key[1]:<2} {x['per_stream']:7.1f} -> {y['per_stream']:7.1f} tok/s ({ch:+.1f} %), "
              f"ttft {x['ttft']:.2f} -> {y['ttft']:.2f} s")
    print("Differences under ~3 % are noise; repeat both runs if the result decides something.")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == "run":
        n = a[a.index("--n") + 1] if "--n" in a else "1,4"
        label = a[a.index("--label") + 1] if "--label" in a else "run"
        run(a[1], n, label)
    elif a[0] == "compare":
        compare(a[1], a[2])
    elif a[0] == "list":
        for p in sorted(OUT.glob(f"{a[1] if len(a) > 1 else ''}*.json")):
            print(p)
    else:
        sys.exit(__doc__)
