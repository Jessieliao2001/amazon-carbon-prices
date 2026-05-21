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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pysrc.services.file_service import get_path


PY = sys.executable
DEFAULT_PARALLEL_STEPS = {
    "baseline",
    "shadow-prices",
    "mpc-prepare",
    "mpc-hmc-pre",
    "mpc-hmc-figure14",
    "mpc-day0",
    "mpc-converge-paths",
    "mpc-tables",
    "maps",
    "hmc",
    "hmc-maps",
}
STAGE_ALIASES = {
    "stage-data": ["data"],
    "stage-hmm": ["price-estimation", "baseline", "bayesian-r2"],
    "stage-deterministic": [
        "shadow-prices",
        "derive-prices",
        "deterministic",
        "maps",
    ],
    "stage-hmc": ["hmc", "hmc-maps"],
    "stage-mpc": [
        "mpc-prepare",
        "mpc-prices",
        "derive-prices",
        "mpc-hmc-pre",
        "mpc-probabilities",
        "mpc-day0",
        "mpc-tables",
        "mpc-hmc-figure14",
        "mpc-figures",
        "postprocess",
    ],
}
FULL_STAGE_SEQUENCE = [
    "stage-data",
    "stage-hmm",
    "stage-deterministic",
    "stage-hmc",
    "stage-mpc",
]
POSTPROCESS_STEPS = ["derive-prices", "mpc-probabilities", "postprocess"]


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
    command: Path


def base_steps() -> dict[str, list[list[str]]]:
    return {
        "data": [["Rscript", "-e", 'source("rsrc/_masterfile_all.R")']],
        "baseline": [
            [PY, "pysrc/sampling/baseline.py", "--sites", "1043"],
            [PY, "pysrc/sampling/baseline.py", "--sites", "78"],
        ],
        "derive-prices": [[PY, "pysrc/replication/derive_carbon_prices.py"]],
        "deterministic": [[PY, "pysrc/scripts/conduction_det.py"]],
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
        "mpc-prices": [[PY, "pysrc/mpc/mpc_compute_sp.py"]],
        "mpc-hmc-pre": mpc_hmc_pre_commands(),
        "mpc-hmc-figure14": mpc_hmc_figure14_commands(),
        "mpc-tables": mpc_table_commands(),
        "mpc-figures": [[PY, "pysrc/scripts/mpc_trajectory.py"]],
        "mpc-probabilities": [[PY, "pysrc/replication/derive_mpc_transition_probabilities.py"]],
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
        "postprocess": [
            [PY, "pysrc/mpc/mpc_compute_day0.py", "--model", "unconstrained", "--b", "0", "10", "15", "25", "--xi", "all", "--quiet"],
            [PY, "pysrc/mpc/mpc_compute_day0.py", "--model", "constrained", "--b", "all", "--xi", "all", "--quiet"],
            [PY, "pysrc/replication/build_paper_numbers.py"],
            [PY, "pysrc/replication/build_aux_input_tables.py"],
        ],
    }


def shadow_price_commands() -> list[list[str]]:
    commands: list[list[str]] = []
    specs = [
        ("0.5", range(20, 40), 1043),
        ("1", range(40, 51), 1043),
        ("2", range(50, 61), 1043),
        ("10000", range(60, 71), 1043),
        ("10000", range(60, 71), 78),
    ]
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


def mpc_table_commands() -> list[list[str]]:
    commands: list[list[str]] = []
    specs = [
        ("unconstrained", ["0", "10", "15", "25"]),
        ("constrained", ["0", "10", "15", "20", "25"]),
    ]
    for model, b_values in specs:
        for b_value in b_values:
            for xi in ["inf", "1", "0.5"]:
                commands.append(
                    [
                        PY,
                        "pysrc/mpc/mpc_compute.py",
                        "--model",
                        model,
                        "--b",
                        b_value,
                        "--xi",
                        xi,
                    ]
                )
    return commands


def mpc_day0_commands() -> list[list[str]]:
    return mpc_hmc_commands(
        specs=[
            ("unconstrained", ["10000", "1", "0.5"], range(1, 2), 2),
            ("constrained", ["10000", "1", "0.5"], range(1, 2), 2),
        ]
    )


def mpc_hmc_pre_commands() -> list[list[str]]:
    return mpc_hmc_commands(
        specs=[
            ("unconstrained", ["10000", "1", "0.5"], range(997, 999), 0),
            ("constrained", ["10000", "1", "0.5"], range(997, 999), 0),
        ]
    )


def mpc_hmc_figure14_commands() -> list[list[str]]:
    return mpc_hmc_commands(
        specs=[
            ("unconstrained", ["10000", "1", "0.5"], range(1, 51), 0),
            ("constrained", ["10000", "1", "0.5"], range(1, 51), 0),
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


def execution_plan(selection: list[str]) -> list[ExecutionItem]:
    grouped_steps: list[tuple[str, list[str]]] = []
    if selection == ["all"]:
        grouped_steps = [
            (stage, STAGE_ALIASES[stage])
            for stage in FULL_STAGE_SEQUENCE
        ]
    elif selection == ["postprocess-only"]:
        grouped_steps = [("postprocess-only", POSTPROCESS_STEPS)]
    else:
        custom_steps: list[str] = []
        for value in selection:
            if value in STAGE_ALIASES:
                if custom_steps:
                    grouped_steps.append(("custom-steps", custom_steps))
                    custom_steps = []
                grouped_steps.append((value, STAGE_ALIASES[value]))
            else:
                custom_steps.append(value)
        if custom_steps:
            grouped_steps.append(("custom-steps", custom_steps))

    plan: list[ExecutionItem] = []
    order_index = 1
    for stage, steps in grouped_steps:
        for stage_step_index, step in enumerate(steps, start=1):
            plan.append(
                ExecutionItem(
                    order_index=order_index,
                    stage=stage,
                    stage_step_index=stage_step_index,
                    step=step,
                )
            )
            order_index += 1
    return plan


def commands_for_step(step: str) -> list[list[str]]:
    if step == "shadow-prices":
        return shadow_price_commands()
    if step == "mpc-day0":
        return mpc_day0_commands()
    steps = base_steps()
    if step not in steps:
        available = sorted(steps) + ["shadow-prices"] + sorted(STAGE_ALIASES)
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
    step_dir = (
        base_dir
        / safe_name(stage)
        / f"{step_index:02d}_{safe_name(step)}"
    )
    stem = f"{command_index:04d}"
    return LocalLogFiles(
        step_dir=step_dir,
        out=step_dir / f"{stem}_run.out",
        err=step_dir / f"{stem}_run.err",
        command=step_dir / f"{stem}_command.txt",
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
    log_files.command.write_text(command_text + "\n")

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
    log_files.command.write_text(command_text + "\n")

    modules = os.environ.get("REPLICATION_MODULES", "python/anaconda-2022.05 gurobi/11.0 gcc/12.2.0")
    slurm_time = os.environ.get("REPLICATION_SLURM_TIME", "1-11:00:00")
    slurm_cpus = os.environ.get("REPLICATION_SLURM_CPUS", "8")
    slurm_mem = os.environ.get("REPLICATION_SLURM_MEM", "32G")
    slurm_partition = os.environ.get("REPLICATION_SLURM_PARTITION")
    inner_command = "; ".join(
        [
            "set -euo pipefail",
            f"cd {shlex.quote(str(root))}",
            (
                "if command -v module >/dev/null 2>&1; then "
                f"module load {modules}; "
                "fi"
            ),
            "if [ -f .venv/bin/activate ]; then source .venv/bin/activate; fi",
            command_text,
        ]
    )
    wrapped_command = "bash -lc " + shlex.quote(inner_command)

    sbatch_command = [
        "sbatch",
        "--parsable",
        f"--job-name={job_name}",
        f"--output={log_files.out}",
        f"--error={log_files.err}",
        f"--time={slurm_time}",
        "--nodes=1",
        f"--cpus-per-task={slurm_cpus}",
        f"--mem={slurm_mem}",
    ]
    if slurm_partition:
        sbatch_command.append(f"--partition={slurm_partition}")
    if depends_on and dependency_mode != "none":
        sbatch_command.append(f"--dependency={dependency_mode}:{':'.join(depends_on)}")
    sbatch_command.extend(["--wrap", wrapped_command])
    print(f"+ {shlex.join(sbatch_command)}")
    print(f"  logs: {display_path(log_files.out, root)}")
    result = subprocess.run(sbatch_command, cwd=root, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip(), file=sys.stderr)
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
) -> tuple[list[tuple[str, list[str], int]], list[str]]:
    failures: list[tuple[str, list[str], int]] = []
    submitted: list[str] = []
    current_dependency = depends_on

    for index, command in enumerate(commands, start=1):
        if is_r_command(command) and not run_r_on_slurm:
            print(
                "Skipping R command on Slurm; run this step locally instead: "
                f"[{stage}/{step}] {shlex.join(command)}"
            )
            continue

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
            "stage-hmc, stage-mpc, or an explicit list of step names"
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

    root = args.root.resolve()
    log_base = resolve_local_log_base(root, args.local_log_dir)
    local_log_base = None if args.no_local_logs else log_base
    failures: list[tuple[str, list[str], int]] = []
    selected_parallel_steps = parallel_steps(args.parallel_steps)
    previous_slurm_jobs: list[str] = []

    for item in execution_plan(args.steps):
        step = item.step
        commands = commands_for_step(step)
        can_parallelize = step in selected_parallel_steps
        for index, command in enumerate(commands, start=1):
            if args.dry_run:
                if (
                    args.backend == "slurm"
                    and is_r_command(command)
                    and not args.run_r_on_slurm
                ):
                    print(f"[{item.stage}/{step} skipped-r-on-slurm] {shlex.join(command)}")
                    continue
                marker = "parallel" if can_parallelize else "serial"
                print(f"[{item.stage}/{step} {marker}] {shlex.join(command)}")
        if args.dry_run:
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
