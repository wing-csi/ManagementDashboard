#!/usr/bin/env python3
"""Report whether a collector run actually worked, before you trust it.

`collect_github.py` exits 0 even when most repos came back empty: a repo the
token cannot see, or one whose name no longer exists, is recorded as an error
on that repo and the run carries on. That is the right behaviour for a nightly
job, but it means "the collector succeeded" and "the dashboard has data" are
different claims, and only the second one matters.

Run it against a collector output to get the second answer:

    python3 scripts/verify_collection.py /tmp/metrics-test.json

Exit status is 0 when every configured repo produced data, 1 otherwise, so it
can gate a manual run before the result is published anywhere.

Stdlib only, like the rest of the pipeline.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import pathlib
import sys

STALE_DAYS = 2  # the dashboard calls a snapshot stale past 48 hours


def load(path: pathlib.Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        sys.exit(f"no such file: {path}")
    except json.JSONDecodeError as exc:
        sys.exit(f"{path} is not valid JSON: {exc}")


def age_days(generated_at: str | None) -> float | None:
    """Age of the snapshot in days, or None if the timestamp is unusable."""
    if not generated_at:
        return None
    try:
        when = dt.datetime.fromisoformat(generated_at)
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=dt.timezone.utc)
    return (dt.datetime.now(dt.timezone.utc) - when).total_seconds() / 86400


def repo_errors(meta: dict) -> list[str]:
    """Every error string recorded against one repo, whatever the field name.

    Field names have grown over time (issues_error, history_error, ...), so
    this matches on the suffix rather than an allow-list that would silently
    miss a newly added one.
    """
    return [
        str(value)
        for key, value in (meta or {}).items()
        if key.lower().endswith("error") and value
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("metrics", nargs="?", type=pathlib.Path,
                    default=pathlib.Path("docs/data/metrics.json"),
                    help="collector output to inspect (default: docs/data/metrics.json)")
    ap.add_argument("--allow-missing", action="append", default=[], metavar="REPO",
                    help="a repo whose failure should not affect the verdict, e.g. one "
                         "you knowingly have no token for. Repeatable. Still reported, "
                         "so it cannot be forgotten about.")
    args = ap.parse_args()

    data = load(args.metrics)
    repos = data.get("repos") or []
    tasks = data.get("tasks") or []
    meta = data.get("repo_meta") or {}

    print(f"file          : {args.metrics}")
    print(f"generated_at  : {data.get('generated_at')}")
    age = age_days(data.get("generated_at"))
    if age is None:
        print("age           : unreadable timestamp")
    else:
        flag = "  <-- the dashboard will call this stale" if age > STALE_DAYS else ""
        print(f"age           : {age:.1f} days{flag}")
    print(f"repos         : {len(repos)}")
    print(f"tasks         : {len(tasks)}")

    owners = sorted({r.split("/")[0] for r in repos})
    print(f"owners        : {', '.join(owners) if owners else '(none)'}")

    per_repo = collections.Counter(t.get("repo") for t in tasks)

    # A repo with no tasks is not the same as a repo that failed. The collector
    # writes a repo_meta entry for every repo it reached, so a repo with an
    # entry and no tasks was read successfully and simply had no activity in
    # the window — which is a fact about the repo, not a fault. A repo with no
    # entry at all never got collected.
    #
    # Treating quiet repos as failures made the exit code cry wolf on a healthy
    # run, and an exit code nobody trusts is worse than none.
    uncollected = [r for r in repos if r not in meta]
    quiet = [r for r in repos if r in meta and not per_repo.get(r)]
    with_issues = [r for r in repos if (meta.get(r) or {}).get("issues")]
    with_plan = [r for r in repos if (meta.get(r) or {}).get("plan")]
    print(f"with issues   : {len(with_issues)} / {len(repos)}")
    print(f"with a plan   : {len(with_plan)} / {len(repos)}")

    grouped: dict[str, list[str]] = collections.defaultdict(list)
    for repo in repos:
        for message in repo_errors(meta.get(repo)):
            grouped[message].append(repo)
    for message in data.get("errors") or []:
        grouped[str(message)].append("(run-level)")

    if grouped:
        print("\nerrors, grouped by message:")
        for message, affected in sorted(grouped.items(), key=lambda kv: -len(kv[1])):
            print(f"  {len(affected):>3}x  {message}")
            print(f"        {', '.join(affected[:6])}"
                  f"{' …' if len(affected) > 6 else ''}")
    else:
        print("\nerrors        : none")

    if uncollected:
        print(f"\nNOT COLLECTED — no metadata at all ({len(uncollected)}):")
        for repo in uncollected:
            print(f"  {repo}")
        print("  A renamed or moved repo, a token that cannot see it, or a"
              " transient 5xx from GitHub all look like this.")

    if quiet:
        print(f"\ncollected, but no tasks in the window ({len(quiet)}):")
        for repo in quiet:
            print(f"  {repo}")
        print("  These were read successfully — they simply had no activity."
              " Not counted as failures.")

    # An excused repo is still printed above — it just does not decide the
    # verdict. Hiding it would turn "I know about that one" into "I forgot
    # about that one" a fortnight later.
    excused = set(args.allow_missing)
    unknown = excused - set(repos)
    if unknown:
        print(f"\nnote: --allow-missing named {', '.join(sorted(unknown))}, "
              "which is not in this run's repo list — check the spelling.")

    def still_blocking(message: str, affected: list[str]) -> list[str]:
        """Drop the excused repos from one error's affected list.

        A run-level error is not attached to a repo, but it usually names one
        in its text ("Could not resolve to a Repository with the name 'x/y'").
        Excusing x/y and then still failing the verdict on that same error
        would make --allow-missing look broken, so a run-level message that
        names only excused repos is excused with them.
        """
        named = [r for r in affected if r != "(run-level)"]
        rest = [r for r in named if r not in excused]
        if "(run-level)" in affected:
            if not any(r in message for r in excused):
                rest.append("(run-level)")
        return rest

    blocking_errors = {
        message: still_blocking(message, affected)
        for message, affected in grouped.items()
    }
    blocking = any(affected for affected in blocking_errors.values())
    blocking_uncollected = [r for r in uncollected if r not in excused]

    if excused:
        print(f"\nexcused       : {', '.join(sorted(excused))} "
              "(--allow-missing; reported above, not counted)")

    ok = not blocking and not blocking_uncollected
    print("\nverdict       :", "every configured repo was collected"
          if ok else "INCOMPLETE — see above")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
