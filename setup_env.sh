#!/usr/bin/env sh

# Prepare the replication environment from the repository root.
# Use `source ./setup_env.sh local` or `source ./setup_env.sh server` if you
# want the created .venv and, on the server, loaded modules to remain active in
# the current shell after setup finishes.

if (return 0 2>/dev/null); then
    SETUP_ENV_SOURCED=1
else
    SETUP_ENV_SOURCED=0
fi

say() {
    printf '%s\n' "$*"
}

warn() {
    printf 'Warning: %s\n' "$*" >&2
}

usage() {
    cat <<'EOF'
Usage:
  source ./setup_env.sh local
  source ./setup_env.sh server
  ./setup_env.sh local
  ./setup_env.sh server

Options:
  --skip-cmdstan   Do not install or overwrite CmdStan.
  --overwrite-cmdstan
                   Reinstall CmdStan even if an existing install is found.
  --skip-renv      Do not run renv restore.
  --with-renv      Restore the R environment in server mode. Local mode does
                   this by default.
  --skip-gurobipy  Do not install the gurobipy Python package.
  -h, --help       Show this help message.

Environment variables:
  PYTHON_BIN       Python executable used to create .venv.
EOF
}

run() {
    printf '+'
    for arg in "$@"; do
        printf ' %s' "$arg"
    done
    printf '\n'
    "$@"
}

find_repo_root() {
    script_dir=$(CDPATH= cd "$(dirname "$0")" 2>/dev/null && pwd -P)
    if [ -n "$script_dir" ] && [ -f "$script_dir/pyproject.toml" ] && [ -f "$script_dir/run.sh" ]; then
        printf '%s\n' "$script_dir"
        return 0
    fi
    if [ -f "pyproject.toml" ] && [ -f "run.sh" ]; then
        pwd -P
        return 0
    fi
    return 1
}

select_python() {
    mode="$1"
    if [ -n "${PYTHON_BIN:-}" ]; then
        printf '%s\n' "$PYTHON_BIN"
        return 0
    fi
    if [ "$mode" = "server" ] && [ -x "/software/python-anaconda-2022.05-el8-x86_64/bin/python3" ]; then
        printf '%s\n' "/software/python-anaconda-2022.05-el8-x86_64/bin/python3"
        return 0
    fi
    if command -v python3.9 >/dev/null 2>&1; then
        command -v python3.9
        return 0
    fi
    if command -v python3 >/dev/null 2>&1; then
        command -v python3
        return 0
    fi
    return 1
}

check_python_version() {
    "$1" - <<'PY'
import sys

version = sys.version_info
if not ((3, 9) <= version[:2] < (3, 12)):
    raise SystemExit(
        f"Python >=3.9,<3.12 is required; found {version.major}.{version.minor}.{version.micro}"
    )
print(f"Using Python {version.major}.{version.minor}.{version.micro}")
PY
}

load_server_modules() {
    if ! command -v module >/dev/null 2>&1; then
        if [ -r "/etc/profile.d/modules.sh" ]; then
            . "/etc/profile.d/modules.sh"
        elif [ -r "/usr/share/Modules/init/sh" ]; then
            . "/usr/share/Modules/init/sh"
        fi
    fi
    if ! command -v module >/dev/null 2>&1; then
        warn "The module command is not available in this shell."
        return 1
    fi
    module avail python gurobi gcc >/dev/null 2>&1 || true
    module load python/anaconda-2022.05 gurobi/11.0 gcc/12.2.0
}

install_r_environment() {
    if ! command -v Rscript >/dev/null 2>&1; then
        warn "Rscript is not available. Install R first, then rerun without --skip-renv."
        return 1
    fi
    run Rscript -e 'options(repos = c(CRAN = "https://cloud.r-project.org")); if (!requireNamespace("renv", quietly = TRUE)) install.packages("renv"); renv::restore(prompt = FALSE)'
}

cmdstan_path_for() {
    "$1" - <<'PY'
from cmdstanpy import cmdstan_path

try:
    print(cmdstan_path())
except ValueError:
    raise SystemExit(1)
PY
}

install_cmdstan_environment() {
    venv_python="$1"
    overwrite_cmdstan="$2"

    existing_cmdstan=$(cmdstan_path_for "$venv_python" 2>/dev/null)
    if [ -n "$existing_cmdstan" ] && [ "$overwrite_cmdstan" = "0" ]; then
        say "Using existing CmdStan: $existing_cmdstan"
        return 0
    fi

    if [ "$overwrite_cmdstan" = "1" ]; then
        run "$venv_python" -m cmdstanpy.install_cmdstan --overwrite
    else
        run "$venv_python" -m cmdstanpy.install_cmdstan
    fi
}

check_environment() {
    venv_python="$1"
    run "$venv_python" - <<'PY' || return 1
import cmdstanpy
import geopandas
import hmmlearn
import matplotlib
import numpy
import pandas
import pyomo.environ as pyo
import scipy
import seaborn

print("python packages ok")
try:
    print("cmdstan:", cmdstanpy.cmdstan_path())
except ValueError:
    print("cmdstan: not installed")
print("gurobi available to Pyomo:", pyo.SolverFactory("gurobi").available(False))
PY

    if command -v gurobi_cl >/dev/null 2>&1; then
        run gurobi_cl --version || warn "gurobi_cl exists but did not report a version."
    else
        warn "gurobi_cl is not on PATH. Install Gurobi 11.0.x and configure a license before optimization steps."
    fi
}

setup_env_main() {
    MODE=""
    SKIP_CMDSTAN=0
    SKIP_RENV=0
    WITH_RENV=0
    SKIP_GUROBIPY=0
    OVERWRITE_CMDSTAN=0

    while [ "$#" -gt 0 ]; do
        case "$1" in
            local|server)
                if [ -n "$MODE" ]; then
                    warn "Choose only one mode: local or server."
                    usage
                    return 1
                fi
                MODE="$1"
                ;;
            --skip-cmdstan)
                SKIP_CMDSTAN=1
                ;;
            --overwrite-cmdstan)
                OVERWRITE_CMDSTAN=1
                ;;
            --skip-renv)
                SKIP_RENV=1
                ;;
            --with-renv)
                WITH_RENV=1
                ;;
            --skip-gurobipy)
                SKIP_GUROBIPY=1
                ;;
            -h|--help)
                usage
                return 0
                ;;
            *)
                warn "Unknown argument: $1"
                usage
                return 1
                ;;
        esac
        shift
    done

    if [ -z "$MODE" ]; then
        MODE="local"
    fi
    if [ "$MODE" = "server" ] && [ "$WITH_RENV" = "0" ]; then
        SKIP_RENV=1
    fi

    REPO_ROOT=$(find_repo_root) || {
        warn "Run this script from the repository root, or call it as ./setup_env.sh from the repository root."
        return 1
    }
    cd "$REPO_ROOT" || return 1

    say "Preparing environment in $REPO_ROOT"
    say "Mode: $MODE"

    if [ "$MODE" = "server" ]; then
        load_server_modules || return 1
    fi

    PYBIN=$(select_python "$MODE") || {
        warn "Could not find python3.9 or python3. Set PYTHON_BIN=/path/to/python and rerun."
        return 1
    }
    check_python_version "$PYBIN" || return 1

    VENV_DIR="$REPO_ROOT/.venv"
    if [ ! -x "$VENV_DIR/bin/python" ]; then
        run "$PYBIN" -m venv "$VENV_DIR" || return 1
    else
        say "Using existing virtual environment: $VENV_DIR"
    fi

    VENV_PY="$VENV_DIR/bin/python"
    check_python_version "$VENV_PY" || return 1
    run "$VENV_PY" -m pip install -U pip setuptools wheel || return 1
    run "$VENV_PY" -m pip install -e "${REPO_ROOT}[all]" || return 1

    if [ "$SKIP_GUROBIPY" = "0" ]; then
        run "$VENV_PY" -m pip install "gurobipy==11.0.*" || return 1
    fi

    if [ "$SKIP_CMDSTAN" = "0" ]; then
        install_cmdstan_environment "$VENV_PY" "$OVERWRITE_CMDSTAN" || return 1
    fi

    if [ "$SKIP_RENV" = "0" ]; then
        install_r_environment || return 1
    elif [ "$MODE" = "server" ] && [ "$WITH_RENV" = "0" ]; then
        say "Skipping R renv restore in server mode. Use --with-renv only on servers with a working R installation."
    fi

    check_environment "$VENV_PY" || return 1

    if [ "$SETUP_ENV_SOURCED" = "1" ]; then
        . "$VENV_DIR/bin/activate" || return 1
        say "Setup complete. The .venv environment is active in this shell."
        if [ "$MODE" = "server" ]; then
            say "Server modules are also loaded in this shell."
        fi
    else
        say "Setup complete. Activate it with:"
        say "  source .venv/bin/activate"
        if [ "$MODE" = "server" ]; then
            say "For a new server shell, reload modules first:"
            say "  module load python/anaconda-2022.05 gurobi/11.0 gcc/12.2.0"
            say "  source .venv/bin/activate"
        fi
    fi
}

setup_env_main "$@"
SETUP_ENV_STATUS=$?

if [ "$SETUP_ENV_SOURCED" = "1" ]; then
    return "$SETUP_ENV_STATUS"
fi
exit "$SETUP_ENV_STATUS"
