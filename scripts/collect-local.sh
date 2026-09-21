#!/usr/bin/env bash
#
# Run the collector locally against config.toml and report whether it worked.
#
#   cp .secrets.env.example .secrets.env     # once
#   # put your real tokens in .secrets.env
#   ./scripts/collect-local.sh
#
# Writes to a temp file, never to docs/data/metrics.json: that copy is the only
# local snapshot, and overwriting it with a half-empty run would destroy the
# thing you would want to compare against. Pass --apply once you are happy with
# the result to install it there as well.
#
# Exit status comes from scripts/verify_collection.py: 0 only when every
# configured repo produced data. The collector itself exits 0 even when most
# repos failed, so its status is not the one you want.

set -euo pipefail

cd "$(dirname "$0")/.."

SECRETS=".secrets.env"
OUT="${TMPDIR:-/tmp}/metrics-local.json"
PYTHON="${PYTHON:-python}"
APPLY=0

VERIFY_ARGS=()

while [ $# -gt 0 ]; do
  case "$1" in
    --apply) APPLY=1 ;;
    # Passed straight through: a repo you knowingly have no token for should
    # not make the whole run read as broken.
    --allow-missing)
      [ $# -ge 2 ] || { echo "--allow-missing needs a repo name" >&2; exit 2; }
      VERIFY_ARGS+=(--allow-missing "$2"); shift ;;
    # Print the header comment as the help text, stopping at the first line
    # that is not a comment — a hardcoded line range goes stale the moment
    # the header grows or shrinks.
    -h|--help) awk 'NR>1 && /^#/ {sub(/^# ?/, ""); print; next} NR>1 {exit}' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

# ---- safety: the token file must be ignored by git -------------------------
# Checked every run, not just at setup. A .gitignore edit, a fresh clone, or a
# renamed file could quietly expose it, and the cost of being wrong here is a
# leaked credential in a public commit.
if [ ! -f "$SECRETS" ]; then
  echo "error: $SECRETS not found." >&2
  echo "  cp .secrets.env.example $SECRETS   then put your tokens in it" >&2
  exit 1
fi

if ! git check-ignore -q "$SECRETS"; then
  echo "error: $SECRETS is NOT ignored by git — refusing to run." >&2
  echo "  Add '$SECRETS' to .gitignore before putting a real token in it." >&2
  exit 1
fi

if git ls-files --error-unmatch "$SECRETS" >/dev/null 2>&1; then
  echo "error: $SECRETS is TRACKED by git — a token in it would be committed." >&2
  echo "  git rm --cached $SECRETS    then rotate any token already in it." >&2
  exit 1
fi

# ---- load the tokens -------------------------------------------------------
# `set -a` exports everything the file defines, so the collector sees each
# token_env named in config.toml without this script knowing their names.
set -a
# shellcheck disable=SC1090
. "./$SECRETS"
set +a

placeholder=0
while IFS='=' read -r name _rest; do
  case "$name" in
    ''|'#'*|*[!A-Za-z0-9_]*) continue ;;   # blank, comment, or not a var name
  esac
  value="${!name:-}"
  case "$value" in
    ""|*replace_me*)
      echo "error: $name is still a placeholder in $SECRETS" >&2
      placeholder=1
      ;;
  esac
done < "$SECRETS"
[ "$placeholder" -eq 0 ] || exit 1

# ---- collect ---------------------------------------------------------------
echo "collecting to $OUT ..."
"$PYTHON" scripts/collect_github.py --config config.toml --out "$OUT"

echo
"$PYTHON" scripts/verify_collection.py "$OUT" "${VERIFY_ARGS[@]+"${VERIFY_ARGS[@]}"}" \
  && status=0 || status=$?

if [ "$APPLY" -eq 1 ]; then
  if [ "$status" -ne 0 ]; then
    echo
    echo "not installing: the run was incomplete. Fix the errors above, or" >&2
    echo "re-run without --apply and inspect $OUT yourself." >&2
  else
    cp "$OUT" docs/data/metrics.json
    echo
    echo "installed to docs/data/metrics.json"
  fi
fi

exit "$status"
