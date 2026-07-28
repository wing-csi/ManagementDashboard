#!/usr/bin/env python3
"""One command to refresh and serve the dashboard locally.

Pulls the private data repo, copies metrics.json into docs/data/, starts a static
server and opens a browser. This replaces the three-command sequence in the
README's 本地跑 section.

A pull failure never stops the server: stale data on screen beats no dashboard at
all, which is what matters when you are demoing and the network is uncooperative.

Usage:
    python3 scripts/run_dashboard.py
    python3 scripts/run_dashboard.py --port 8080
    python3 scripts/run_dashboard.py --no-pull --no-browser
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import threading
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sync_data import DEFAULT_DATA_REPO, DEST, resolve_source, sync  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS = REPO_ROOT / "docs"
DEFAULT_PORT = 8000


def pull_data_repo(data_repo: Path) -> str:
    """Run `git pull` in the data repo clone. Returns a human-readable outcome.

    Never raises: the dashboard must still start when the network, the credentials
    or the clone itself are unavailable.
    """
    if not data_repo.is_dir():
        return f"skipped — no clone at {data_repo}"
    try:
        result = subprocess.run(
            ["git", "-C", str(data_repo), "pull", "--ff-only"],
            capture_output=True, text=True, timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as e:
        return f"failed ({e.__class__.__name__}) — using the data already on disk"
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        return f"failed ({detail[-1] if detail else 'unknown error'}) — using the data on disk"
    lines = result.stdout.strip().splitlines()
    return lines[-1] if lines else "ok"


def serve(directory: Path, port: int) -> ThreadingHTTPServer:
    """Start a static server for `directory` on a daemon thread."""
    handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
    httpd = ThreadingHTTPServer(("", port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"port to serve on (default: {DEFAULT_PORT})")
    parser.add_argument("--from", dest="data_repo", type=Path, default=DEFAULT_DATA_REPO,
                        help="path to the ManagementDashboard-data clone")
    parser.add_argument("--no-pull", action="store_true", help="skip git pull")
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser")
    args = parser.parse_args()

    if not args.no_pull:
        print(f"pull    {pull_data_repo(args.data_repo)}")

    try:
        src = resolve_source(args.data_repo)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"sync    {sync(src, DEST):,} bytes -> {DEST.relative_to(REPO_ROOT)}")

    try:
        httpd = serve(DOCS, args.port)
    except OSError as e:
        print(f"error: cannot serve on port {args.port}: {e}\n"
              f"Something else is using it — try --port {args.port + 1}.", file=sys.stderr)
        return 1

    url = f"http://localhost:{args.port}"
    print(f"serve   {url}   (Ctrl+C to stop)")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        print("\nstopped")
        httpd.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
