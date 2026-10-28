#!/usr/bin/env python3
"""Does a llama-swap model load and work?  smoke.py MODEL [--no-tools] [--vision] [--timeout 1200]

Loads the model through llama-swap (first call waits for the load; other models may be unloaded as configured),
then checks: 1) a short answer, 2) a tool call (OpenAI "tools"), 3) with --vision: names two colours in a built-in
red|blue picture. Prints load time, decode speed when the engine reports it, VRAM per GPU and RAM afterwards.
Exit code 0 = all checks passed.
"""
import base64, json, pathlib, struct, sys, time, urllib.request, zlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import rig


def chat(model, messages, timeout, **kw):
    body = {"model": model, "messages": messages, "max_tokens": kw.pop("max_tokens", 1500), **kw}
    req = urllib.request.Request(rig.LS_URL + "/v1/chat/completions", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    t = time.time()
    try:
        r = json.load(urllib.request.urlopen(req, timeout=timeout))
    except urllib.error.HTTPError as e:
        return None, time.time() - t, f"HTTP {e.code}: {e.read().decode()[:600]}"
    except Exception as e:
        return None, time.time() - t, str(e)
    return r, time.time() - t, None


def png():
    w, h = 128, 64
    rows = b"".join(b"\x00" + b"\xdc\x14\x14" * (w // 2) + b"\x14\x3c\xdc" * (w // 2) for _ in range(h))
    ch = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + ch(b"IDAT", zlib.compress(rows)) + ch(b"IEND", b""))


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    model = rig.resolve_model(a[0])
    timeout = int(a[a.index("--timeout") + 1]) if "--timeout" in a else 1200
    ok = True
    print(f"model {model}; running before: {rig.running()}")
    r, dt, err = chat(model, [{"role": "user", "content": "Reply with one word: ready"}], timeout)
    if err:
        print(f"FAIL load/answer after {dt:.0f} s: {err}\nlogs: curl -s localhost:8080/logs | tail -50")
        sys.exit(1)
    msg = r["choices"][0]["message"]
    tps = (r.get("timings") or {}).get("predicted_per_second")
    print(f"OK   load+answer {dt:.0f} s: {(msg.get('content') or '').strip()[:80]!r}"
          + (f"  decode {tps:.0f} tok/s" if tps else ""))
    if "--no-tools" not in a:
        tools = [{"type": "function", "function": {"name": "get_weather", "description": "Current weather for a city",
                  "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}}}]
        r, dt, err = chat(model, [{"role": "user", "content": "What is the weather in Warsaw right now? Use the tool."}],
                          timeout, tools=tools)
        calls = (r or {}).get("choices", [{}])[0].get("message", {}).get("tool_calls") if r else None
        if calls and calls[0]["function"]["name"] == "get_weather":
            print(f"OK   tool call in {dt:.1f} s: {calls[0]['function']['arguments']}")
        else:
            ok = False
            print(f"FAIL tool call: {err or json.dumps((r or {}).get('choices', [{}])[0].get('message'))[:400]}"
                  "\n     (llama.cpp: needs --jinja and a template with tool support; vLLM: --tool-call-parser)")
    if "--vision" in a:
        img = base64.b64encode(png()).decode()
        r, dt, err = chat(model, [{"role": "user", "content": [
            {"type": "text", "text": "What two colours does this image contain, and which is on the left? One sentence."},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64," + img}}]}], timeout)
        ans = ((r or {}).get("choices", [{}])[0].get("message", {}).get("content") or "").lower() if r else ""
        if "red" in ans and "blue" in ans:
            print(f"OK   vision in {dt:.1f} s: {ans.strip()[:120]!r}")
        else:
            ok = False
            print(f"FAIL vision: {err or ans[:300]!r}  (llama.cpp needs --mmproj)")
    print("VRAM: " + ", ".join(f"GPU{g['gpu']} {g['used_gb']:.1f} GB" for g in rig.vram())
          + f"; RAM available {rig.ram_gb()['available']:.0f} of {rig.RAM_GB:.0f} GB; running: {rig.running()}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
