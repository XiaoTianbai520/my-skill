#!/usr/bin/env python3
"""Run one command with proxy env vars injected, without polluting the global environment.

Windows-safe: does not rely on POSIX `env`, and does not attempt to modify the
parent shell (which is impossible from a child process). Everything is scoped to
the spawned child.

Usage:
    python run_with_proxy.py -- pip install requests
    python run_with_proxy.py --no-proxy-hosts localhost,127.0.0.1,.cn -- npm install
    python run_with_proxy.py --port 7890 -- git clone https://github.com/foo/bar.git

Note: pass the target command AFTER `--` so its own flags are not eaten by argparse.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7890

# Hosts that must never go through the proxy (local + common mainland-CN services
# that are already fast enough direct; routing them through a proxy slows them down).
DEFAULT_NO_PROXY = ",".join(
    [
        "localhost",
        "127.0.0.1",
        "::1",
        "0.0.0.0",
        "*.local",
        "mirrors.aliyun.com",
        "mirrors.tuna.tsinghua.edu.cn",
        "mirrors.cloud.tencent.com",
        "registry.npmmirror.com",
        "pypi.tuna.tsinghua.edu.cn",
        "mirrors.ustc.edu.cn",
    ]
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Run a command with proxy env vars set.")
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--no-proxy-hosts", default=DEFAULT_NO_PROXY)
    ap.add_argument("--scheme", default="http", choices=["http", "socks5", "socks5h"])
    ap.add_argument("--dry-run", action="store_true", help="print the command, do not execute")
    ap.add_argument("command", nargs=argparse.REMAINDER)
    args = ap.parse_args()

    cmd = [c for c in args.command if c != "--"]
    if not cmd:
        ap.error("no command given; usage: run_with_proxy.py -- <command> [args...]")

    proxy_url = f"{args.scheme}://{args.host}:{args.port}"
    env = os.environ.copy()
    env["HTTP_PROXY"] = proxy_url
    env["HTTPS_PROXY"] = proxy_url
    env["http_proxy"] = proxy_url
    env["https_proxy"] = proxy_url
    env["ALL_PROXY"] = proxy_url
    env["all_proxy"] = proxy_url
    env["NO_PROXY"] = args.no_proxy_hosts
    env["no_proxy"] = args.no_proxy_hosts

    print(f"[run_with_proxy] HTTP_PROXY={proxy_url}", file=sys.stderr)
    print(f"[run_with_proxy] $ {' '.join(cmd)}", file=sys.stderr)

    if args.dry_run:
        for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"):
            print(f"{key}={env[key]}")
        return 0

    completed = subprocess.run(cmd, env=env, shell=False)
    return completed.returncode


if __name__ == "__main__":
    sys.exit(main())
