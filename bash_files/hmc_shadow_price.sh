#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

kind="${1:-all}"
if [[ $# -gt 0 ]]; then
  shift
fi

backend="${BACKEND:-slurm}"

case "$kind" in
  det)
    steps=(shadow-prices-det derive-prices)
    ;;
  hmc)
    steps=(shadow-prices-hmc derive-prices)
    ;;
  all)
    steps=(shadow-prices-det derive-prices shadow-prices-hmc derive-prices)
    ;;
  *)
    echo "Usage: $0 [det|hmc|all] [extra run.sh options]" >&2
    echo "Example: REPLICATION_SLURM_ACCOUNT=pi-lhansen $0 hmc --dry-run" >&2
    exit 2
    ;;
esac

exec ./run.sh --steps "${steps[@]}" --backend "$backend" "$@"
