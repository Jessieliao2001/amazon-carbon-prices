from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pysrc.services.file_service import get_path


PY = sys.executable
DEFAULT_PARALLEL_STEPS = {
    "baseline",
    "shadow-prices",
    "shadow-prices-det",
    "shadow-prices-hmc",
    "hmc-sampling",
    "mpc-prepare",
    "mpc-sp-grid",
    "mpc-hmc-pre",
    "mpc-hmc-pre-unconstrained",
    "mpc-hmc-pre-constrained",
    "mpc-hmc-figure14",
    "mpc-hmc-figure14-unconstrained",
    "mpc-day0",
    "mpc-day0-unconstrained",
    "mpc-day0-constrained",
    "mpc-converge-paths",
    "mpc-tables",
    "mpc-tables-unconstrained",
    "mpc-tables-constrained",
    "mpc-simulation-tables-unconstrained",
    "mpc-figures-unconstrained",
    "maps",
    "hmc",
    "relative-entropy",
    "hmc-maps",
    "time-consistency",
}
MPC_GROUP_STEPS = {
    "mpc-sp-grid",
    "mpc-hmc-pre",
    "mpc-hmc-pre-unconstrained",
    "mpc-hmc-pre-constrained",
    "mpc-hmc-figure14",
    "mpc-hmc-figure14-unconstrained",
    "mpc-day0",
    "mpc-day0-unconstrained",
    "mpc-day0-constrained",
}
MPC_COMMANDS_PER_GROUP = 1
MPC_MODELS = ("unconstrained", "constrained")
STAGE_ALIASES = {
    "stage-data": ["data", "figure1"],
    "stage-hmm": ["price-estimation", "baseline", "bayesian-r2"],
    "stage-deterministic": [
        "shadow-prices-det",
        "derive-prices-det",
        "deterministic",
        "maps",
    ],
    "stage-time-consistency": ["time-consistency"],
    "stage-hmc": [
        "shadow-prices-hmc",
        "derive-prices-hmc",
        "hmc-sampling",
        "relative-entropy",
        "hmc",
        "hmc-maps",
    ],
    "stage-mpc": [
        "mpc-prepare",
        "mpc-sp-grid",
        "mpc-prices",
        "derive-prices-mpc",
        "mpc-hmc-pre-unconstrained",
        "mpc-probabilities-unconstrained",
        "mpc-day0-unconstrained",
        "mpc-tables-unconstrained",
        "mpc-hmc-figure14-unconstrained",
        "mpc-simulation-tables-unconstrained",
        "mpc-figures-unconstrained",
        "mpc-hmc-pre-constrained",
        "mpc-probabilities-constrained",
        "mpc-day0-constrained",
        "mpc-tables-constrained",
    ],
    "stage-postprocess": [
        "mpc-probabilities",
        "postprocess-final",
        "aux-figures",
    ],
}
FULL_STAGE_SEQUENCE = [
    "stage-data",
    "stage-hmm",
    "stage-deterministic",
    "stage-time-consistency",
    "stage-hmc",
    "stage-mpc",
    "stage-postprocess",
]
POSTPROCESS_STEPS = list(STAGE_ALIASES["stage-postprocess"])


@dataclass(frozen=True)
class ExecutionItem:
    order_index: int
    stage: str
    stage_step_index: int
    step: str


@dataclass(frozen=True)
class LocalLogFiles:
    step_dir: Path
    out: Path
    err: Path


def base_steps() -> dict[str, list[list[str]]]:
    return {
        "data": [["Rscript", "-e", 'source("rsrc/_masterfile_all.R")']],
        "figure1": [[PY, "pysrc/scripts/figure1.py"]],
        "baseline": [
            [PY, "pysrc/sampling/baseline.py", "--sites", "1043"],
            [PY, "pysrc/sampling/baseline.py", "--sites", "78"],
        ],
        "derive-prices": [[PY, "pysrc/replication/derive_carbon_prices.py"]],
        "derive-prices-det": [[PY, "pysrc/replication/derive_carbon_prices.py"]],
        "derive-prices-hmc": [[PY, "pysrc/replication/derive_carbon_prices.py"]],
        "derive-prices-mpc": [[PY, "pysrc/replication/derive_carbon_prices.py"]],
        "deterministic": [[PY, "pysrc/scripts/conduction_det.py"]],
        "time-consistency": [
            [PY, "pysrc/scripts/time_consistency.py", "--bf", "3.75", "--sites", "1043"],
            [PY, "pysrc/scripts/time_consistency.py", "--bf", "5", "--sites", "1043"],
        ],
        "relative-entropy": [
            [
                PY,
                "pysrc/bash/relative_entropy.py",
                "--xi",
                "1",
                "--sites",
                "1043",
                "--skip-density",
            ]
        ],
        "hmc-sampling": hmc_sampling_commands(),
        "hmc-neutral-sampling": [
            [
                PY,
                "pysrc/scripts/hmc_sampling.py",
                "--xi",
                "10000",
                "--price-source",
                "det",
                "--transfers",
                "15",
            ]
        ],
        "hmc": hmc_commands(),
        "mpc-prepare": [
            [PY, "pysrc/mpc/mpc_simulating.py", "--type", "baseline"],
            [PY, "pysrc/mpc/mpc_simulating.py", "--type", "constrained"],
            [PY, "pysrc/mpc/mpc_simulating.py", "--type", "shadow_price"],
        ],
        "mpc-converge-paths": [
            [PY, "pysrc/mpc/mpc_simulating.py", "--type", "converge_uncon"],
            [PY, "pysrc/mpc/mpc_simulating.py", "--type", "converge_con"],
        ],
        "mpc-sp-grid": mpc_sp_grid_commands(),
        "mpc-prices": [[PY, "pysrc/mpc/mpc_compute_sp.py"]],
        "mpc-hmc-pre": mpc_hmc_pre_commands(),
        "mpc-hmc-pre-unconstrained": mpc_hmc_pre_commands("unconstrained"),
        "mpc-hmc-pre-constrained": mpc_hmc_pre_commands("constrained"),
        "mpc-hmc-figure14": mpc_hmc_figure14_commands("unconstrained"),
        "mpc-hmc-figure14-unconstrained": mpc_hmc_figure14_commands("unconstrained"),
        "mpc-tables": mpc_table_commands(),
        "mpc-tables-unconstrained": mpc_table_commands("unconstrained"),
        "mpc-tables-constrained": mpc_table_commands("constrained"),
        "mpc-simulation-tables-unconstrained": mpc_simulation_table_commands("unconstrained"),
        "mpc-figures": mpc_figure_commands("unconstrained"),
        "mpc-figures-unconstrained": mpc_figure_commands("unconstrained"),
        "aux-figures": [
            [PY, "pysrc/replication/build_aux_input_tables.py", "--figures-only"]
        ],
        "mpc-probabilities": mpc_probability_commands(),
        "mpc-probabilities-unconstrained": mpc_probability_commands("unconstrained"),
        "mpc-probabilities-constrained": mpc_probability_commands("constrained"),
        "price-estimation": [[PY, "pysrc/scripts/price_estimation.py"]],
        "bayesian-r2": [[PY, "pysrc/scripts/bayesian_R2.py"]],
        "maps": [
            ["Rscript", "rsrc/analysis/carbon_capture_curves/_masterfile.R"],
            ["Rscript", "rsrc/analysis/calibration_maps_1043_sites.R"],
            ["Rscript", "rsrc/analysis/calibration_maps_78_sites.R"],
            ["Rscript", "rsrc/analysis/map_1043_det.R"],
        ],
        "hmc-maps": [
            ["Rscript", "rsrc/analysis/map_1043_hmc_xi1.R"],
            ["Rscript", "rsrc/analysis/map_1043_hmc_xi05.R"],
            ["Rscript", "rsrc/analysis/map_kl.R"],
        ],
        "postprocess": postprocess_commands(),
        "postprocess-unconstrained": postprocess_commands("unconstrained"),
        "postprocess-constrained": postprocess_commands("constrained"),
        "postprocess-final": postprocess_commands("final"),
    }


SHADOW_PRICE_SPECS = {
    "hmc": [
        ("0.5", range(20, 40), 1043),
        ("1", range(40, 51), 1043),
        ("2", range(50, 61), 1043),
    ],
    "det": [
        ("10000", range(60, 71), 1043),
        ("10000", range(60, 71), 78),
    ],
}


def shadow_price_commands(kind: str = "all") -> list[list[str]]:
    commands: list[list[str]] = []
    if kind == "all":
        specs = SHADOW_PRICE_SPECS["hmc"] + SHADOW_PRICE_SPECS["det"]
    elif kind in SHADOW_PRICE_SPECS:
        specs = SHADOW_PRICE_SPECS[kind]
    else:
        raise ValueError(f"Unknown shadow-price command kind: {kind}")
    for xi, ids, sites in specs:
        for run_id in ids:
            commands.append(
                [
                    PY,
                    "pysrc/bash/shadow_price.py",
                    "--id",
                    str(run_id),
                    "--xi",
                    xi,
                    "--sites",
                    str(sites),
                ]
            )
    return commands


def hmc_commands() -> list[list[str]]:
    return [
        [
            PY,
            "pysrc/scripts/conduction_hmc.py",
            "--xi",
            "1",
            "--tables",
            "ambiguity",
            "transfer-cost",
            "--figures",
            "density",
            "histograms",
            "trajectories",
        ],
        [
            PY,
            "pysrc/scripts/conduction_hmc.py",
            "--xi",
            "2",
            "--tables",
            "ambiguity",
            "--figures",
            "density",
        ],
        [
            PY,
            "pysrc/scripts/conduction_hmc.py",
            "--xi",
            "0.5",
            "--tables",
            "ambiguity",
            "--figures",
            "density",
        ],
    ]


def hmc_sampling_commands() -> list[list[str]]:
    commands: list[list[str]] = []
    transfers = ["0", "10", "15", "20", "25"]
    specs = [
        ("1", ["hmc", "det"]),
        ("2", ["hmc"]),
        ("0.5", ["hmc"]),
    ]
    for xi, price_sources in specs:
        for transfer in transfers:
            for price_source in price_sources:
                commands.append(
                    [
                        PY,
                        "pysrc/scripts/hmc_sampling.py",
                        "--xi",
                        xi,
                        "--price-source",
                        price_source,
                        "--transfers",
                        transfer,
                    ]
                )
    commands.append(
        [
            PY,
            "pysrc/scripts/hmc_sampling.py",
            "--xi",
            "10000",
            "--price-source",
            "det",
            "--transfers",
            "15",
        ]
    )
    return commands


def mpc_models(model: str | None = None) -> tuple[str, ...]:
    if model is None:
        return MPC_MODELS
    if model not in MPC_MODELS:
        raise ValueError(f"Unknown MPC model `{model}`. Expected one of {MPC_MODELS}.")
    return (model,)


def mpc_probability_commands(model: str | None = None) -> list[list[str]]:
    if model is None:
        return [[PY, "pysrc/replication/derive_mpc_transition_probabilities.py"]]
    mpc_models(model)
    return [
        [
            PY,
            "pysrc/replication/derive_mpc_transition_probabilities.py",
            "--model",
            model,
        ]
    ]


def postprocess_commands(model: str | None = None) -> list[list[str]]:
    if model is None or model == "final":
        return [
            [PY, "pysrc/replication/build_paper_numbers.py"],
            [PY, "pysrc/replication/build_aux_input_tables.py"],
        ]

    mpc_models(model)
    return [
        [
            PY,
            "-c",
            (
                "print('postprocess-"
                + model
                + " no longer regenerates MPC tables; use "
                + "mpc-tables-"
                + model
                + " for table generation and postprocess-final for manifests.')"
            ),
        ]
    ]


def mpc_figure_commands(model: str | None = None) -> list[list[str]]:
    # The current MPC trajectory script only reads unconstrained output paths.
    if model not in {None, "unconstrained"}:
        raise ValueError("MPC figure generation is currently available only for unconstrained outputs.")
    return [[PY, "pysrc/scripts/mpc_trajectory.py"]]


def mpc_table_commands(model: str | None = None) -> list[list[str]]:
    commands: list[list[str]] = []
    for model_name in mpc_models(model):
        if model_name == "unconstrained":
            commands.append(
                [
                    PY,
                    "pysrc/mpc/mpc_compute_day0.py",
                    "--model",
                    "unconstrained",
                    "--b",
                    "0",
                    "10",
                    "15",
                    "25",
                    "--xi",
                    "all",
                ]
            )
        else:
            commands.append(
                [
                    PY,
                    "pysrc/mpc/mpc_compute_day0.py",
                    "--model",
                    "constrained",
                    "--b",
                    "all",
                    "--xi",
                    "all",
                ]
            )
    return commands


def mpc_simulation_table_commands(model: str | None = None) -> list[list[str]]:
    if model not in {None, "unconstrained"}:
        raise ValueError("MPC simulation table rows are currently needed only for unconstrained outputs.")
    return [
        [
            PY,
            "pysrc/mpc/mpc_compute.py",
            "--model",
            "unconstrained",
            "--b",
            "0",
            "10",
            "15",
            "25",
            "--xi",
            "inf",
            "--mode",
            "baseline",
        ]
    ]


def mpc_sp_grid_commands() -> list[list[str]]:
    commands: list[list[str]] = []
    pe_values = [
        str((Decimal("5.0") + Decimal("0.1") * index).quantize(Decimal("0.1")))
        for index in range(21)
    ]
    for model in ["unconstrained", "constrained"]:
        for xi in ["0.5", "1", "10000"]:
            for pe_value in pe_values:
                commands.append(
                    [
                        PY,
                        "pysrc/mpc/mpc_hmc_sp.py",
                        "--pe",
                        pe_value,
                        "--xi",
                        xi,
                        "--type",
                        model,
                    ]
                )
    return commands


def mpc_day0_commands(model: str | None = None) -> list[list[str]]:
    return mpc_hmc_commands(
        specs=[
            (model_name, ["10000", "1", "0.5"], range(1, 2), 2)
            for model_name in mpc_models(model)
        ]
    )


def mpc_hmc_pre_commands(model: str | None = None) -> list[list[str]]:
    return mpc_hmc_commands(
        specs=[
            (model_name, ["10000", "1", "0.5"], range(997, 999), 0)
            for model_name in mpc_models(model)
        ]
    )


def mpc_hmc_figure14_commands(model: str | None = None) -> list[list[str]]:
    if model == "constrained":
        raise ValueError("Figure 14 MPC-HMC jobs are defined only for unconstrained outputs.")
    return mpc_hmc_commands(
        specs=[
            ("unconstrained", ["10000", "1", "0.5"], range(1, 51), 0)
        ]
    )


def mpc_hmc_commands(
    *,
    specs: list[tuple[str, list[str], range, int]],
    b_values: list[str] | None = None,
) -> list[list[str]]:
    commands: list[list[str]] = []
    b_values = b_values or ["0", "10", "15", "20", "25"]
    for model, xis, ids, trig in specs:
        for xi in xis:
            for run_id in ids:
                for b_value in b_values:
                    commands.append(
                        [
                            PY,
                            "pysrc/scripts/run_mpc_hmc_job.py",
                            "--id",
                            str(run_id),
                            "--xi",
                            xi,
                            "--b",
                            b_value,
                            "--trig",
                            str(trig),
                            "--type",
                            model,
                        ]
                    )
    return commands


def ordered_steps(selection: list[str]) -> list[str]:
    if selection == ["all"]:
        return [
            step
            for stage in FULL_STAGE_SEQUENCE
            for step in STAGE_ALIASES[stage]
        ]
    if selection == ["postprocess-only"]:
        return list(POSTPROCESS_STEPS)

    expanded: list[str] = []
    for step in selection:
        expanded.extend(STAGE_ALIASES.get(step, [step]))
    return expanded


def stage_items(stage: str, steps: list[str], order_index: int) -> list[ExecutionItem]:
    return [
        ExecutionItem(
            order_index=order_index + index - 1,
            stage=stage,
            stage_step_index=index,
            step=step,
        )
        for index, step in enumerate(steps, start=1)
    ]


def canonical_step_location(
    step: str,
    preferred_stage: str | None = None,
) -> tuple[str, int] | None:
    if preferred_stage in STAGE_ALIASES:
        preferred_steps = STAGE_ALIASES[preferred_stage]
        if step in preferred_steps:
            return preferred_stage, preferred_steps.index(step) + 1

    for stage in FULL_STAGE_SEQUENCE:
        steps = STAGE_ALIASES[stage]
        if step in steps:
            return stage, steps.index(step) + 1
    return None


def execution_plan(selection: list[str]) -> list[ExecutionItem]:
    plan: list[ExecutionItem] = []
    order_index = 1

    if selection == ["all"]:
        for stage in FULL_STAGE_SEQUENCE:
            items = stage_items(stage, STAGE_ALIASES[stage], order_index)
            plan.extend(items)
            order_index += len(items)
        return plan

    elif selection == ["postprocess-only"]:
        return stage_items("stage-postprocess", POSTPROCESS_STEPS, order_index)

    else:
        current_stage: str | None = None
        for value in selection:
            if value in STAGE_ALIASES:
                items = stage_items(value, STAGE_ALIASES[value], order_index)
                plan.extend(items)
                order_index += len(items)
                current_stage = value
            else:
                location = canonical_step_location(value, current_stage)
                if location is None:
                    stage = "custom-steps"
                    stage_step_index = order_index
                else:
                    stage, stage_step_index = location
                    current_stage = stage
                plan.append(
                    ExecutionItem(
                        order_index=order_index,
                        stage=stage,
                        stage_step_index=stage_step_index,
                        step=value,
                    )
                )
                order_index += 1
    return plan


def commands_for_step(step: str) -> list[list[str]]:
    if step == "shadow-prices":
        return shadow_price_commands()
    if step == "shadow-prices-det":
        return shadow_price_commands("det")
    if step == "shadow-prices-hmc":
        return shadow_price_commands("hmc")
    if step == "mpc-day0":
        return mpc_day0_commands()
    if step == "mpc-day0-unconstrained":
        return mpc_day0_commands("unconstrained")
    if step == "mpc-day0-constrained":
        return mpc_day0_commands("constrained")
    steps = base_steps()
    if step not in steps:
        available = (
            sorted(steps)
            + ["shadow-prices", "shadow-prices-det", "shadow-prices-hmc"]
            + sorted(STAGE_ALIASES)
        )
        raise KeyError(f"Unknown step `{step}`. Available steps: {available}")
    return steps[step]


def parallel_steps(values: list[str]) -> set[str]:
    if values == ["auto"]:
        return set(DEFAULT_PARALLEL_STEPS)
    if values == ["none"]:
        return set()
    return set(values)


def safe_name(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value).strip("_")


def local_log_files(
    base_dir: Path,
    *,
    stage: str,
    step_index: int,
    step: str,
    command_index: int,
) -> LocalLogFiles:
    step_dir = base_dir / safe_name(stage) / safe_name(step)
    stem = f"{command_index:04d}"
    return LocalLogFiles(
        step_dir=step_dir,
        out=step_dir / f"{stem}_run.out",
        err=step_dir / f"{stem}_run.err",
    )


def resolve_local_log_base(root: Path, value: Path) -> Path:
    if value.is_absolute():
        return value
    if value.parts and value.parts[0] == "job-outs":
        return root / value
    return root / "job-outs" / value


def display_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def unprefixed_step_dir_name(name: str) -> str | None:
    if len(name) <= 3:
        return None
    if not name[:2].isdigit() or name[2] != "_":
        return None
    return name[3:]


def normalize_numbered_log_step_dirs(log_base: Path, root: Path) -> None:
    if not log_base.exists():
        return
    for stage_dir in sorted(log_base.iterdir()):
        if not stage_dir.is_dir():
            continue
        for step_dir in sorted(stage_dir.iterdir()):
            if not step_dir.is_dir():
                continue
            target_name = unprefixed_step_dir_name(step_dir.name)
            if target_name is None:
                continue
            target = stage_dir / target_name
            if target.exists():
                print(
                    "Skipping old numbered log folder because target exists: "
                    f"{display_path(step_dir, root)} -> {display_path(target, root)}"
                )
                continue
            print(
                "Renaming old numbered log folder: "
                f"{display_path(step_dir, root)} -> {display_path(target, root)}"
            )
            step_dir.rename(target)


def elapsed_text(seconds: int) -> str:
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{days} days {hours:02d} hr {minutes:02d} min {secs:02d} sec"


def run_local(command: list[str], root: Path, log_files: LocalLogFiles | None = None) -> int:
    command_text = shlex.join(command)
    if log_files is None:
        print(f"+ {command_text}")
        return subprocess.run(command, cwd=root).returncode

    log_files.step_dir.mkdir(parents=True, exist_ok=True)

    print(f"+ {command_text}")
    print(f"  logs: {display_path(log_files.out, root)}")

    start = time.time()
    with log_files.out.open("w") as stdout, log_files.err.open("w") as stderr:
        stdout.write(f"Command: {command_text}\n")
        stdout.write(f"Working directory: {root}\n")
        stdout.write(f"Program starts {time.ctime(start)}\n\n")
        stdout.flush()

        result = subprocess.run(command, cwd=root, stdout=stdout, stderr=stderr)

        end = time.time()
        stdout.write(f"\nProgram ends {time.ctime(end)}\n")
        stdout.write(f"Exit code: {result.returncode}\n")
        stdout.write(f"Elapsed time: {elapsed_text(int(end - start))}\n")

    if result.returncode != 0:
        print(f"  failed; stderr: {display_path(log_files.err, root)}")
    return result.returncode


def run_local_step(
    stage: str,
    step: str,
    commands: list[list[str]],
    root: Path,
    *,
    step_index: int,
    jobs: int,
    can_parallelize: bool,
    log_base_dir: Path | None,
) -> list[tuple[str, list[str], int]]:
    failures: list[tuple[str, list[str], int]] = []
    if not can_parallelize or jobs <= 1 or len(commands) <= 1:
        for command_index, command in enumerate(commands, start=1):
            command_log_files = (
                local_log_files(
                    log_base_dir,
                    stage=stage,
                    step_index=step_index,
                    step=step,
                    command_index=command_index,
                )
                if log_base_dir
                else None
            )
            code = run_local(command, root, command_log_files)
            if code != 0:
                failures.append((step, command, code))
                break
        return failures

    workers = min(jobs, len(commands))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                run_local,
                command,
                root,
                local_log_files(
                    log_base_dir,
                    stage=stage,
                    step_index=step_index,
                    step=step,
                    command_index=command_index,
                )
                if log_base_dir
                else None,
            ): command
            for command_index, command in enumerate(commands, start=1)
        }
        for future in as_completed(futures):
            command = futures[future]
            code = future.result()
            if code != 0:
                failures.append((step, command, code))
    return failures


def is_r_command(command: list[str]) -> bool:
    return bool(command) and Path(command[0]).name == "Rscript"


def submit_slurm(
    command: list[str],
    root: Path,
    job_name: str,
    log_files: LocalLogFiles,
    *,
    depends_on: list[str] | None = None,
    dependency_mode: str = "afterok",
) -> tuple[int, str | None]:
    if shutil.which("sbatch") is None:
        raise RuntimeError("`sbatch` is not available. Use `--backend local` on non-server machines.")

    log_files.step_dir.mkdir(parents=True, exist_ok=True)
    command_text = shlex.join(command)

    modules = os.environ.get("REPLICATION_MODULES", "python/anaconda-2022.05 gurobi/11.0 gcc/12.2.0")
    script_lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        f"cd {shlex.quote(str(root))}",
        "if command -v module >/dev/null 2>&1; then "
        f"module load {modules}; "
        "fi",
        "if [ -f .venv/bin/activate ]; then source .venv/bin/activate; fi",
        "export PYTHONUNBUFFERED=1",
        "export PYTHONIOENCODING=UTF-8",
        f"echo {shlex.quote('Command: ' + command_text)}",
        f"echo {shlex.quote('Working directory: ' + str(root))}",
        'echo "Program starts $(date)"',
        "echo",
        "start=$(date +%s)",
        "set +e",
        command_text,
        "code=$?",
        "set -e",
        "end=$(date +%s)",
        "echo",
        'echo "Program ends $(date)"',
        'echo "Exit code: ${code}"',
        'echo "Elapsed time: $((end - start)) seconds"',
        'exit "${code}"',
    ]
    sbatch_command = slurm_batch_command(
        job_name=job_name,
        out=log_files.out,
        err=log_files.err,
        depends_on=depends_on,
        dependency_mode=dependency_mode,
    )
    script_text = "\n".join(script_lines) + "\n"
    print(f"+ {shlex.join(sbatch_command)} < inline-script")
    print(f"  logs: {display_path(log_files.out, root)}")
    result = subprocess.run(
        sbatch_command,
        cwd=root,
        input=script_text,
        capture_output=True,
        text=True,
    )
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print_slurm_stderr_help(result.stderr)
    job_id = None
    if result.returncode == 0 and result.stdout.strip():
        job_id = result.stdout.strip().splitlines()[-1].split(";")[0]
    return result.returncode, job_id


def chunked_commands(
    commands: list[list[str]],
    *,
    size: int,
) -> list[list[tuple[int, list[str]]]]:
    return [
        list(enumerate(commands[start : start + size], start=start + 1))
        for start in range(0, len(commands), size)
    ]


def slurm_group_settings(
    step: str,
    *,
    commands_per_job: int,
    group_min_commands: int,
) -> tuple[int, int]:
    if step in MPC_GROUP_STEPS:
        return MPC_COMMANDS_PER_GROUP, MPC_COMMANDS_PER_GROUP
    return commands_per_job, group_min_commands


def slurm_batch_command(
    *,
    job_name: str,
    out: Path,
    err: Path,
    depends_on: list[str] | None,
    dependency_mode: str,
) -> list[str]:
    slurm_time = os.environ.get("REPLICATION_SLURM_TIME", "1-11:00:00")
    slurm_cpus = os.environ.get("REPLICATION_SLURM_CPUS", "8")
    slurm_mem = os.environ.get("REPLICATION_SLURM_MEM", "32G")
    slurm_account = os.environ.get("REPLICATION_SLURM_ACCOUNT")
    slurm_partition = os.environ.get("REPLICATION_SLURM_PARTITION")

    command = [
        "sbatch",
        "--parsable",
        f"--job-name={job_name}",
        f"--output={out}",
        f"--error={err}",
        f"--time={slurm_time}",
        "--nodes=1",
        f"--cpus-per-task={slurm_cpus}",
        f"--mem={slurm_mem}",
    ]
    if slurm_account:
        command.append(f"--account={slurm_account}")
    if slurm_partition:
        command.append(f"--partition={slurm_partition}")
    if depends_on and dependency_mode != "none":
        command.append(f"--dependency={dependency_mode}:{':'.join(depends_on)}")
    return command


def print_slurm_stderr_help(stderr: str) -> None:
    if not stderr:
        return
    print(stderr.strip(), file=sys.stderr)
    if "Account is not specified" in stderr and not os.environ.get("REPLICATION_SLURM_ACCOUNT"):
        print(
            "Slurm rejected the job because no account was provided. "
            "Rerun with `--slurm-account <account>` or set "
            "`REPLICATION_SLURM_ACCOUNT=<account>`.",
            file=sys.stderr,
        )
    if "QOSMaxSubmitJobPerUserLimit" in stderr:
        print(
            "Slurm rejected the job because the submitted-job limit was reached. "
            "Increase `--slurm-commands-per-job` so fewer sbatch jobs are submitted.",
            file=sys.stderr,
        )


def submit_slurm_group(
    commands: list[tuple[int, list[str]]],
    root: Path,
    job_name: str,
    log_base_dir: Path,
    *,
    stage: str,
    step: str,
    step_index: int,
    group_index: int,
    depends_on: list[str] | None = None,
    dependency_mode: str = "afterok",
) -> tuple[int, str | None]:
    if shutil.which("sbatch") is None:
        raise RuntimeError("`sbatch` is not available. Use `--backend local` on non-server machines.")

    first_command_index = commands[0][0]
    last_command_index = commands[-1][0]
    step_dir = log_base_dir / safe_name(stage) / safe_name(step)
    step_dir.mkdir(parents=True, exist_ok=True)
    group_stem = f"group_{group_index:04d}_{first_command_index:04d}_{last_command_index:04d}"
    group_out = step_dir / f"{group_stem}.out"
    group_err = step_dir / f"{group_stem}.err"

    modules = os.environ.get("REPLICATION_MODULES", "python/anaconda-2022.05 gurobi/11.0 gcc/12.2.0")
    script_lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        f"cd {shlex.quote(str(root))}",
        "if command -v module >/dev/null 2>&1; then "
        f"module load {modules}; "
        "fi",
        "if [ -f .venv/bin/activate ]; then source .venv/bin/activate; fi",
        "export PYTHONUNBUFFERED=1",
        "export PYTHONIOENCODING=UTF-8",
        f"echo {shlex.quote('Grouped Slurm job: ' + job_name)}",
        f"echo {shlex.quote('Working directory: ' + str(root))}",
        f"echo {shlex.quote(f'Commands: {first_command_index:04d}-{last_command_index:04d}')}",
        'echo "Group starts $(date)"',
        "echo",
        "",
        "run_logged_command() {",
        "  local command_text=\"$1\"",
        "  local stdout_path=\"$2\"",
        "  local stderr_path=\"$3\"",
        "  shift 3",
        "  {",
        "    echo \"Command: ${command_text}\"",
        f"    echo \"Working directory: {root}\"",
        "    echo \"Program starts $(date)\"",
        "    echo",
        "  } > \"${stdout_path}\"",
        "  : > \"${stderr_path}\"",
        "  local start",
        "  local end",
        "  local code",
        '  echo "[$(date)] starting: ${command_text}"',
        "  start=$(date +%s)",
        "  set +e",
        "  \"$@\" >> \"${stdout_path}\" 2>> \"${stderr_path}\"",
        "  code=$?",
        "  set -e",
        "  end=$(date +%s)",
        "  {",
        "    echo",
        "    echo \"Program ends $(date)\"",
        "    echo \"Exit code: ${code}\"",
        "    echo \"Elapsed time: $((end - start)) seconds\"",
        "  } >> \"${stdout_path}\"",
        '  echo "[$(date)] finished exit ${code}: ${command_text}"',
        "  if [ \"${code}\" -ne 0 ]; then",
        "    echo \"Command failed with exit code ${code}: ${command_text}\" >&2",
        "    exit \"${code}\"",
        "  fi",
        "}",
        "",
    ]

    for command_index, command in commands:
        command_log_files = local_log_files(
            log_base_dir,
            stage=stage,
            step_index=step_index,
            step=step,
            command_index=command_index,
        )
        command_text = shlex.join(command)
        script_lines.append(
            "run_logged_command "
            f"{shlex.quote(command_text)} "
            f"{shlex.quote(str(command_log_files.out))} "
            f"{shlex.quote(str(command_log_files.err))} "
            f"{command_text}"
        )
    script_lines.extend(
        [
            "",
            "echo",
            'echo "Group ends $(date)"',
        ]
    )
    sbatch_command = slurm_batch_command(
        job_name=job_name,
        out=group_out,
        err=group_err,
        depends_on=depends_on,
        dependency_mode=dependency_mode,
    )
    script_text = "\n".join(script_lines) + "\n"

    print(f"+ {shlex.join(sbatch_command)} < inline-script")
    print(
        "  logs: "
        f"{display_path(group_out, root)} "
        f"(commands {first_command_index:04d}-{last_command_index:04d})"
    )
    result = subprocess.run(
        sbatch_command,
        cwd=root,
        input=script_text,
        capture_output=True,
        text=True,
    )
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print_slurm_stderr_help(result.stderr)
    job_id = None
    if result.returncode == 0 and result.stdout.strip():
        job_id = result.stdout.strip().splitlines()[-1].split(";")[0]
    return result.returncode, job_id


def submit_slurm_step(
    stage: str,
    step: str,
    commands: list[list[str]],
    root: Path,
    log_base_dir: Path,
    *,
    step_index: int,
    depends_on: list[str],
    dependency_mode: str,
    can_parallelize: bool,
    run_r_on_slurm: bool,
    commands_per_job: int,
    group_min_commands: int,
) -> tuple[list[tuple[str, list[str], int]], list[str]]:
    failures: list[tuple[str, list[str], int]] = []
    submitted: list[str] = []
    current_dependency = depends_on

    runnable_commands = [
        command
        for command in commands
        if not (is_r_command(command) and not run_r_on_slurm)
    ]
    if len(runnable_commands) != len(commands):
        for command in commands:
            if is_r_command(command) and not run_r_on_slurm:
                print(
                    "Skipping R command on Slurm; run this step locally instead: "
                    f"[{stage}/{step}] {shlex.join(command)}"
                )

    effective_commands_per_job, effective_group_min_commands = slurm_group_settings(
        step,
        commands_per_job=commands_per_job,
        group_min_commands=group_min_commands,
    )

    if (
        can_parallelize
        and effective_commands_per_job > 1
        and len(runnable_commands) >= effective_group_min_commands
    ):
        for group_index, command_group in enumerate(
            chunked_commands(runnable_commands, size=effective_commands_per_job),
            start=1,
        ):
            job_name = (
                f"{safe_name(stage)}_{step_index:02d}_{safe_name(step)}_"
                f"group_{group_index:04d}"
            )
            try:
                code, job_id = submit_slurm_group(
                    command_group,
                    root,
                    job_name,
                    log_base_dir,
                    stage=stage,
                    step=step,
                    step_index=step_index,
                    group_index=group_index,
                    depends_on=depends_on,
                    dependency_mode=dependency_mode,
                )
            except Exception as exc:
                print(f"Step {step} failed before grouped submission: {exc}")
                code = 1
                job_id = None
            if code != 0:
                failures.append((step, command_group[0][1], code))
            if job_id:
                submitted.append(job_id)
        if not submitted:
            return failures, depends_on
        return failures, submitted

    for index, command in enumerate(runnable_commands, start=1):
        log_files = local_log_files(
            log_base_dir,
            stage=stage,
            step_index=step_index,
            step=step,
            command_index=index,
        )
        job_name = f"{safe_name(stage)}_{step_index:02d}_{safe_name(step)}_{index:04d}"
        try:
            code, job_id = submit_slurm(
                command,
                root,
                job_name,
                log_files,
                depends_on=depends_on if can_parallelize else current_dependency,
                dependency_mode=dependency_mode,
            )
        except Exception as exc:
            print(f"Step {step} failed before submission: {exc}")
            code = 1
            job_id = None
        if code != 0:
            failures.append((step, command, code))
            if not can_parallelize:
                break
        if job_id:
            submitted.append(job_id)
            if not can_parallelize:
                current_dependency = [job_id]

    if not can_parallelize and submitted:
        return failures, [submitted[-1]]
    if not submitted:
        return failures, depends_on
    return failures, submitted


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Main replication driver. Use `--steps all` for the full package, or "
            "`--steps postprocess-only` to validate existing outputs on a laptop."
        )
    )
    parser.add_argument(
        "--steps",
        nargs="+",
        default=["postprocess-only"],
        help=(
            "all, postprocess-only, stage-data, stage-hmm, stage-deterministic, "
            "stage-time-consistency, stage-hmc, stage-mpc, stage-postprocess, "
            "or an explicit list of step names"
        ),
    )
    parser.add_argument("--backend", choices=["local", "slurm"], default="local")
    parser.add_argument(
        "--jobs",
        type=int,
        default=1,
        help="Maximum local commands to run in parallel within parallel-safe steps.",
    )
    parser.add_argument(
        "--parallel-steps",
        nargs="+",
        default=["auto"],
        help="Steps to parallelize within-step. Use `auto` or `none`.",
    )
    parser.add_argument(
        "--slurm-dependency-mode",
        choices=["afterok", "afterany", "none"],
        default="afterok",
        help="Dependency mode between Slurm steps.",
    )
    parser.add_argument(
        "--run-r-on-slurm",
        action="store_true",
        help=(
            "Submit Rscript commands to Slurm. By default, the Slurm backend skips "
            "Rscript commands so R data/plot steps can be run locally."
        ),
    )
    parser.add_argument(
        "--slurm-account",
        help=(
            "Slurm account to pass to sbatch. Equivalent to setting "
            "REPLICATION_SLURM_ACCOUNT."
        ),
    )
    parser.add_argument(
        "--slurm-partition",
        help=(
            "Optional Slurm partition to pass to sbatch. Equivalent to setting "
            "REPLICATION_SLURM_PARTITION."
        ),
    )
    parser.add_argument(
        "--slurm-time",
        help=(
            "Slurm time limit, for example 1-11:00:00. Equivalent to setting "
            "REPLICATION_SLURM_TIME."
        ),
    )
    parser.add_argument(
        "--slurm-cpus",
        help=(
            "CPUs per Slurm task. Equivalent to setting REPLICATION_SLURM_CPUS."
        ),
    )
    parser.add_argument(
        "--slurm-mem",
        help=(
            "Slurm memory request, for example 32G. Equivalent to setting "
            "REPLICATION_SLURM_MEM."
        ),
    )
    parser.add_argument(
        "--slurm-commands-per-job",
        type=int,
        default=int(os.environ.get("REPLICATION_SLURM_COMMANDS_PER_JOB", "10")),
        help=(
            "For parallel-safe Slurm steps, group this many replication commands "
            "inside one sbatch job when the step has at least "
            "--slurm-group-min-commands commands. This keeps large MPC stages "
            "under server job submission limits while leaving small steps unchanged. "
            "The MPC-HMC steps are grouped in fixed batches of 5 transfer commands. "
            "Set to 1 to submit one sbatch job per command. "
            "Default: REPLICATION_SLURM_COMMANDS_PER_JOB or 10."
        ),
    )
    parser.add_argument(
        "--slurm-group-min-commands",
        type=int,
        default=int(os.environ.get("REPLICATION_SLURM_GROUP_MIN_COMMANDS", "100")),
        help=(
            "Only group parallel-safe Slurm steps when the step has at least this "
            "many runnable commands. Default: REPLICATION_SLURM_GROUP_MIN_COMMANDS "
            "or 100."
        ),
    )
    parser.add_argument(
        "--local-log-dir",
        type=Path,
        default=Path("job-outs"),
        help=(
            "Directory for backend numbered *_run.out/*_run.err logs. Defaults to job-outs. "
            "Logs are grouped by selected stage inside this directory. "
            "Relative paths not starting with job-outs are created under job-outs. "
            "Use --no-local-logs to stream directly to the terminal."
        ),
    )
    parser.add_argument(
        "--no-local-logs",
        action="store_true",
        help="Disable local run logs and stream command output directly.",
    )
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--root", type=Path, default=get_path())
    args = parser.parse_args()
    if args.slurm_commands_per_job < 1:
        parser.error("--slurm-commands-per-job must be at least 1")
    if args.slurm_group_min_commands < 2:
        parser.error("--slurm-group-min-commands must be at least 2")

    slurm_env_overrides = {
        "REPLICATION_SLURM_ACCOUNT": args.slurm_account,
        "REPLICATION_SLURM_PARTITION": args.slurm_partition,
        "REPLICATION_SLURM_TIME": args.slurm_time,
        "REPLICATION_SLURM_CPUS": args.slurm_cpus,
        "REPLICATION_SLURM_MEM": args.slurm_mem,
    }
    for name, value in slurm_env_overrides.items():
        if value:
            os.environ[name] = value

    root = args.root.resolve()
    log_base = resolve_local_log_base(root, args.local_log_dir)
    if not args.no_local_logs and not args.dry_run:
        normalize_numbered_log_step_dirs(log_base, root)
    local_log_base = None if args.no_local_logs else log_base
    failures: list[tuple[str, list[str], int]] = []
    selected_parallel_steps = parallel_steps(args.parallel_steps)
    previous_slurm_jobs: list[str] = []

    for item in execution_plan(args.steps):
        step = item.step
        commands = commands_for_step(step)
        can_parallelize = step in selected_parallel_steps
        if args.dry_run:
            runnable_commands: list[list[str]] = []
            for command in commands:
                if (
                    args.backend == "slurm"
                    and is_r_command(command)
                    and not args.run_r_on_slurm
                ):
                    print(f"[{item.stage}/{step} skipped-r-on-slurm] {shlex.join(command)}")
                    continue
                runnable_commands.append(command)
            if (
                args.backend == "slurm"
                and can_parallelize
            ):
                effective_commands_per_job, effective_group_min_commands = slurm_group_settings(
                    step,
                    commands_per_job=args.slurm_commands_per_job,
                    group_min_commands=args.slurm_group_min_commands,
                )
            else:
                effective_commands_per_job, effective_group_min_commands = (
                    args.slurm_commands_per_job,
                    args.slurm_group_min_commands,
                )
            if (
                args.backend == "slurm"
                and can_parallelize
                and effective_commands_per_job > 1
                and len(runnable_commands) >= effective_group_min_commands
            ):
                for group_index, group in enumerate(
                    chunked_commands(
                        runnable_commands,
                        size=effective_commands_per_job,
                    ),
                    start=1,
                ):
                    first_index = group[0][0]
                    last_index = group[-1][0]
                    print(
                        f"[{item.stage}/{step} parallel grouped "
                        f"group={group_index:04d} commands={first_index:04d}-{last_index:04d}] "
                        f"first: {shlex.join(group[0][1])}"
                    )
            else:
                for command in runnable_commands:
                    marker = "parallel" if can_parallelize else "serial"
                    print(f"[{item.stage}/{step} {marker}] {shlex.join(command)}")
            continue

        if args.backend == "slurm":
            step_failures, previous_slurm_jobs = submit_slurm_step(
                item.stage,
                step,
                commands,
                root,
                log_base,
                step_index=item.stage_step_index,
                depends_on=previous_slurm_jobs,
                dependency_mode=args.slurm_dependency_mode,
                can_parallelize=can_parallelize,
                run_r_on_slurm=args.run_r_on_slurm,
                commands_per_job=args.slurm_commands_per_job,
                group_min_commands=args.slurm_group_min_commands,
            )
        else:
            step_failures = run_local_step(
                item.stage,
                step,
                commands,
                root,
                step_index=item.stage_step_index,
                jobs=args.jobs,
                can_parallelize=can_parallelize,
                log_base_dir=local_log_base,
            )

        failures.extend(step_failures)
        if step_failures and not args.continue_on_error:
            return step_failures[0][2]

    if failures:
        print("Completed with failures:")
        for step, command, code in failures:
            print(f"  {step}: exit {code}: {shlex.join(command)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
