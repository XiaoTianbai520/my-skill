#!/usr/bin/env python3
"""Probe a local HTTP proxy: reachability, latency, and real download throughput.

Stdlib only. Windows-safe (no external deps, no shell tricks).

Usage:
    python proxy_probe.py
    python proxy_probe.py --host 127.0.0.1 --port 7890
    python proxy_probe.py --compare          # also measure direct (no-proxy) speed
    python proxy_probe.py --json             # machine-readable output

Exit codes:
    0  proxy reachable AND an HTTP request through it succeeded
    2  TCP connect to proxy failed (proxy not running / wrong port)
    3  proxy reachable but HTTP through proxy failed (auth? upstream down?)
"""
from __future__ import annotations

import argparse
import json
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7890
# Small but non-trivial payload so throughput is measurable.
DEFAULT_TARGET = "https://registry.npmjs.org/react"
MAX_BYTES = 512 * 1024


def tcp_probe(host: str, port: int, timeout: float) -> dict:
    """Raw TCP connect test -> tells us whether the proxy is listening at all."""
    t0 = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return {"ok": True, "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}
    except OSError as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def fetch(url: str, proxy_url: str | None, timeout: float, max_bytes: int) -> dict:
    """GET `url`, optionally via `proxy_url`; read at most `max_bytes`."""
    # Empty dict == "explicitly no proxy". Passing {"http": ""} instead would make
    # urllib try to tunnel through an empty host and blow up with "no host given".
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else {}

    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler(proxies),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()),
    )
    opener.addheaders = [("User-Agent", "proxy-probe/1.0")]

    req = urllib.request.Request(url, method="GET")
    t0 = time.perf_counter()
    try:
        with opener.open(req, timeout=timeout) as resp:
            first_byte_at = time.perf_counter()
            chunks = []
            read = 0
            while read < max_bytes:
                chunk = resp.read(65536)
                if not chunk:
                    break
                chunks.append(chunk)
                read += len(chunk)
            elapsed = time.perf_counter() - t0
            ttfb_ms = round((first_byte_at - t0) * 1000, 1)
            mb_s = round(read / 1024 / 1024 / elapsed, 2) if elapsed > 0 else 0.0
            return {
                "ok": True,
                "status": resp.status,
                "ttfb_ms": ttfb_ms,
                "bytes": read,
                "elapsed_s": round(elapsed, 2),
                "mb_per_s": mb_s,
            }
    except urllib.error.HTTPError as exc:
        # A 4xx/5xx still proves the proxy tunnel works; upstream may just reject us.
        return {"ok": True, "status": exc.code, "note": f"HTTPError {exc.code} (tunnel OK)"}
    except Exception as exc:  # noqa: BLE001 - report whatever went wrong
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    ap = argparse.ArgumentParser(description="Probe a local HTTP proxy.")
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--timeout", type=float, default=5.0)
    ap.add_argument("--target", default=DEFAULT_TARGET, help="URL used for the throughput test")
    ap.add_argument("--max-bytes", type=int, default=MAX_BYTES)
    ap.add_argument("--compare", action="store_true", help="also measure direct speed without proxy")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = ap.parse_args()

    proxy_url = f"http://{args.host}:{args.port}"
    result: dict = {"proxy_url": proxy_url, "target": args.target}

    tcp = tcp_probe(args.host, args.port, args.timeout)
    result["tcp"] = tcp
    if not tcp["ok"]:
        result["verdict"] = "PROXY_DOWN"
        result["hint"] = (
            f"Nothing is listening on {args.host}:{args.port}. Start the proxy client "
            "(Clash/Mihomo/v2rayN etc.) and confirm its mixed/HTTP port, then re-run. "
            "Fallback: use a mirror source instead (see references/mirrors.md)."
        )
        print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else _fmt(result))
        return 2

    via = fetch(args.target, proxy_url, args.timeout, args.max_bytes)
    result["via_proxy"] = via
    if not via["ok"]:
        result["verdict"] = "PROXY_UP_BUT_BLOCKED"
        result["hint"] = (
            "TCP connect succeeded but the HTTP request through the proxy failed. "
            "Check whether the proxy requires auth, whether LAN-allow is enabled, "
            "and whether the proxy's own upstream node is alive."
        )
        print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else _fmt(result))
        return 3

    if args.compare:
        direct = fetch(args.target, None, args.timeout, args.max_bytes)
        result["direct"] = direct
        if direct.get("ok") and direct.get("mb_per_s") and via.get("mb_per_s"):
            ratio = via["mb_per_s"] / direct["mb_per_s"] if direct["mb_per_s"] else 0
            result["speedup"] = f"{ratio:.1f}x"
            result["recommend"] = "proxy" if ratio >= 1.2 else "direct-or-mirror"

    result["verdict"] = "PROXY_OK"
    print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else _fmt(result))
    return 0


def _fmt(r: dict) -> str:
    lines = [f"Proxy target : {r['proxy_url']}", f"Test URL    : {r['target']}"]
    tcp = r.get("tcp", {})
    lines.append(
        f"TCP connect : {'OK' if tcp.get('ok') else 'FAIL'} "
        + (f"({tcp.get('latency_ms')} ms)" if tcp.get("ok") else f"({tcp.get('error')})")
    )
    for key in ("via_proxy", "direct"):
        d = r.get(key)
        if not d:
            continue
        label = "Via proxy   " if key == "via_proxy" else "Direct      "
        if d.get("ok"):
            if d.get("mb_per_s") is not None:
                lines.append(
                    f"{label}: HTTP {d.get('status')} | TTFB {d.get('ttfb_ms')} ms | "
                    f"{d.get('bytes')} B in {d.get('elapsed_s')} s | {d.get('mb_per_s')} MB/s"
                )
            else:
                lines.append(f"{label}: {d.get('note')}")
        else:
            lines.append(f"{label}: FAIL ({d.get('error')})")
    if r.get("speedup"):
        lines.append(f"Speedup     : {r['speedup']} -> recommend '{r['recommend']}'")
    lines.append(f"Verdict     : {r['verdict']}")
    if r.get("hint"):
        lines.append(f"Hint        : {r['hint']}")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
