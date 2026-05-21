#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

exec ./run.sh --steps mpc-figures --backend "${BACKEND:-slurm}" "$@"
