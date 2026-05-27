#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

usage() {
    echo "Usage: bash_files/mpc_hmc.sh <local|slurm> <all|pre|formal|figure14|day0|pre-unconstrained|pre-constrained|figure14-unconstrained|day0-unconstrained|day0-constrained> [run.sh options]"
    echo
    echo "Stages:"
    echo "  pre       Transition-probability jobs: trig=0, ids 997-998."
    echo "  figure14  Formal MPC path jobs: trig=0, ids 1-50, unconstrained only."
    echo "  day0      Day-0 present-value decomposition jobs: trig=2, id 1."
    echo "  formal    figure14 + day0, unconstrained first and constrained second."
    echo "  all       pre + formal, unconstrained first and constrained second."
    echo "  *-unconstrained and *-constrained run only that MPC model."
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ] || [ "${1:-}" = "help" ]; then
    usage
    exit 0
fi

BACKEND="${1:-}"
STAGE="${2:-}"
if [ -z "$BACKEND" ] || [ -z "$STAGE" ]; then
    usage
    exit 2
fi
shift 2

if [ "$BACKEND" != "local" ] && [ "$BACKEND" != "slurm" ]; then
    usage
    exit 2
fi

case "$STAGE" in
    pre)
        STEPS=(mpc-hmc-pre)
        ;;
    pre-unconstrained)
        STEPS=(mpc-hmc-pre-unconstrained)
        ;;
    pre-constrained)
        STEPS=(mpc-hmc-pre-constrained)
        ;;
    figure14)
        STEPS=(mpc-hmc-figure14-unconstrained)
        ;;
    figure14-unconstrained)
        STEPS=(mpc-hmc-figure14-unconstrained)
        ;;
    day0)
        STEPS=(mpc-day0)
        ;;
    day0-unconstrained)
        STEPS=(mpc-day0-unconstrained)
        ;;
    day0-constrained)
        STEPS=(mpc-day0-constrained)
        ;;
    formal)
        STEPS=(
            mpc-hmc-figure14-unconstrained
            mpc-day0-unconstrained
            mpc-day0-constrained
        )
        ;;
    all)
        STEPS=(
            mpc-hmc-pre-unconstrained
            mpc-hmc-figure14-unconstrained
            mpc-day0-unconstrained
            mpc-hmc-pre-constrained
            mpc-day0-constrained
        )
        ;;
    *)
        usage
        exit 2
        ;;
esac

exec ./run.sh --steps "${STEPS[@]}" --backend "$BACKEND" "$@"
