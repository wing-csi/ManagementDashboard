#!/usr/bin/env python3
"""Copy metrics.json from a clone of the private data repo into docs/data/.

The dashboard always reads docs/data/metrics.json. In this public repo that path is
gitignored — the real data lives in the private repo wing-csi/ManagementDashboard-data,
which CI refreshes nightly. This script bridges the two, so the documented workflow is
identical on Windows, macOS and Linux.

Usage:
    python3 scripts/sync_data.py                     # ../ManagementDashboard-data
    python3 scripts/sync_data.py --from /path/to/ManagementDashboard-data
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_REPO = REPO_ROOT.parent / "ManagementDashboard-data"
DEST = REPO_ROOT / "docs" / "data" / "metrics.json"


def resolve_source(data_repo: Path) -> Path:
    """Locate metrics.json inside a data-repo clone, or explain what is missing."""
    if not data_repo.is_dir():
        raise FileNotFoundError(
            f"No data repo at {data_repo}.\n"
            f"Clone it next to this repo:\n"
            f"  git clone https://github.com/wing-csi/ManagementDashboard-data.git "
            f"{data_repo}\n"
            f"(You need to be a collaborator on that private repo.)"
        )
    src = data_repo / "metrics.json"
    if not src.is_file():
        raise FileNotFoundError(
            f"{data_repo} has no metrics.json yet.\n"
            f"Run 'git pull' there. If it is still missing, the nightly collect "
            f"workflow has not published successfully — check the Actions tab."
        )
    return src


def sync(src: Path, dest: Path) -> int:
    """Copy src over dest, creating parent directories. Returns bytes written."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    return dest.stat().st_size


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--from", dest="data_repo", type=Path, default=DEFAULT_DATA_REPO,
        help="path to a clone of ManagementDashboard-data "
             "(default: ../ManagementDashboard-data)",
    )
    args = parser.parse_args()
    try:
        src = resolve_source(args.data_repo)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    written = sync(src, DEST)
    print(f"synced {written:,} bytes -> {DEST.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
