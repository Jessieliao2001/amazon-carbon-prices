from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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


def base_steps() -> dict[str, list[list[str]]]:
    return {
        "data": [["Rscript", "-e", 'source("rsrc/_masterfile_all.R")']],
        "baseline": [
            [PY, "pysrc/sampling/baseline.py", "--sites", "1043"],
            [PY, "pysrc/sampling/baseline.py", "--sites", "78"],
        ],
        "derive-prices": [[PY, "scripts/derive_carbon_prices.py"]],
        "deterministic": [[PY, "scripts/conduction_det.py"]],
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
        "mpc-figures": [[PY, "scripts/mpc_trajectory.py"]],
        "mpc-probabilities": [[PY, "scripts/derive_mpc_transition_probabilities.py"]],
        "price-estimation": [[PY, "scripts/price_estimation.py"]],
        "bayesian-r2": [[PY, "scripts/bayesian_R2.py"]],
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
            [PY, "scripts/build_paper_numbers.py"],
            [PY, "scripts/build_aux_input_tables.py"],
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
            "scripts/conduction_hmc.py",
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
            "scripts/conduction_hmc.py",
            "--xi",
            "2",
            "--tables",
            "ambiguity",
            "--figures",
            "density",
        ],
        [
            PY,
            "scripts/conduction_hmc.py",
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
                            "scripts/run_mpc_hmc_job.py",
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
            "data",
            "price-estimation",
            "baseline",
            "bayesian-r2",
            "shadow-prices",
            "derive-prices",
            "deterministic",
            "mpc-prepare",
            "mpc-prices",
            "derive-prices",
            "mpc-day0",
            "mpc-probabilities",
            "mpc-converge-paths",
            "mpc-tables",
            "mpc-figures",
            "maps",
            "hmc",
            "hmc-maps",
            "postprocess",
        ]
    if selection == ["postprocess-only"]:
        return ["derive-prices", "mpc-probabilities", "postprocess"]

    expanded: list[str] = []
    for step in selection:
        expanded.extend(STAGE_ALIASES.get(step, [step]))
    return expanded


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


def run_local(command: list[str], root: Path) -> int:
    print(f"+ {shlex.join(command)}")
    return subprocess.run(command, cwd=root).returncode


def run_local_step(
    step: str,
    commands: list[list[str]],
    root: Path,
    *,
    jobs: int,
    can_parallelize: bool,
) -> list[tuple[str, list[str], int]]:
    failures: list[tuple[str, list[str], int]] = []
    if not can_parallelize or jobs <= 1 or len(commands) <= 1:
        for command in commands:
            code = run_local(command, root)
            if code != 0:
                failures.append((step, command, code))
                break
        return failures

    workers = min(jobs, len(commands))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(run_local, command, root): command for command in commands
        }
        for future in as_completed(futures):
            command = futures[future]
            code = future.result()
            if code != 0:
                failures.append((step, command, code))
    return failures


def submit_slurm(
    command: list[str],
    root: Path,
    job_name: str,
    slurm_dir: Path,
    *,
    depends_on: list[str] | None = None,
    dependency_mode: str = "afterok",
) -> tuple[int, str | None]:
    if shutil.which("sbatch") is None:
        raise RuntimeError("`sbatch` is not available. Use `--backend local` on non-server machines.")

    slurm_dir.mkdir(parents=True, exist_ok=True)
    script_path = slurm_dir / f"{job_name}.sh"
    modules = os.environ.get("REPLICATION_MODULES", "python/anaconda-2022.05 gurobi/11.0 gcc/12.2.0")
    slurm_time = os.environ.get("REPLICATION_SLURM_TIME", "1-11:00:00")
    slurm_cpus = os.environ.get("REPLICATION_SLURM_CPUS", "8")
    slurm_mem = os.environ.get("REPLICATION_SLURM_MEM", "32G")
    slurm_partition = os.environ.get("REPLICATION_SLURM_PARTITION")
    script = [
        "#!/bin/bash",
        f"#SBATCH --job-name={job_name}",
        f"#SBATCH --output={slurm_dir / (job_name + '.out')}",
        f"#SBATCH --error={slurm_dir / (job_name + '.err')}",
        f"#SBATCH --time={slurm_time}",
        "#SBATCH --nodes=1",
        f"#SBATCH --cpus-per-task={slurm_cpus}",
        f"#SBATCH --mem={slurm_mem}",
        f"cd {shlex.quote(str(root))}",
        "command -v module >/dev/null 2>&1 && module load " + modules,
        "[ -f .venv/bin/activate ] && source .venv/bin/activate",
        shlex.join(command),
    ]
    if slurm_partition:
        script.insert(4, f"#SBATCH --partition={slurm_partition}")
    script_path.write_text("\n".join(script) + "\n")

    sbatch_command = ["sbatch", "--parsable"]
    if depends_on and dependency_mode != "none":
        sbatch_command.append(f"--dependency={dependency_mode}:{':'.join(depends_on)}")
    sbatch_command.append(str(script_path))
    print(f"+ {shlex.join(sbatch_command)}")
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
    step: str,
    commands: list[list[str]],
    root: Path,
    slurm_dir: Path,
    *,
    step_index: int,
    depends_on: list[str],
    dependency_mode: str,
    can_parallelize: bool,
) -> tuple[list[tuple[str, list[str], int]], list[str]]:
    failures: list[tuple[str, list[str], int]] = []
    submitted: list[str] = []
    current_dependency = depends_on

    for index, command in enumerate(commands, start=1):
        job_name = f"{step_index:02d}_{step.replace('-', '_')}_{index}"
        try:
            code, job_id = submit_slurm(
                command,
                root,
                job_name,
                slurm_dir,
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
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--root", type=Path, default=get_path())
    args = parser.parse_args()

    root = args.root.resolve()
    slurm_dir = root / "replication" / "slurm"
    failures: list[tuple[str, list[str], int]] = []
    selected_parallel_steps = parallel_steps(args.parallel_steps)
    previous_slurm_jobs: list[str] = []

    for step_index, step in enumerate(ordered_steps(args.steps), start=1):
        commands = commands_for_step(step)
        can_parallelize = step in selected_parallel_steps
        for index, command in enumerate(commands, start=1):
            if args.dry_run:
                marker = "parallel" if can_parallelize else "serial"
                print(f"[{step} {marker}] {shlex.join(command)}")
        if args.dry_run:
            continue

        if args.backend == "slurm":
            step_failures, previous_slurm_jobs = submit_slurm_step(
                step,
                commands,
                root,
                slurm_dir,
                step_index=step_index,
                depends_on=previous_slurm_jobs,
                dependency_mode=args.slurm_dependency_mode,
                can_parallelize=can_parallelize,
            )
        else:
            step_failures = run_local_step(
                step,
                commands,
                root,
                jobs=args.jobs,
                can_parallelize=can_parallelize,
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
