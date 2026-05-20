from __future__ import annotations

import csv
import re
from pathlib import Path

import pandas as pd

from pysrc.services.file_service import get_path


DEFAULT_PAPER_TEX: Path | None = None
PAPER_FIGURE_INPUTS_FILE = get_path("replication", "paper_figure_inputs.csv")
INCLUDEGRAPHICS_RE = re.compile(
    r"\\includegraphics(?:\[[^\]]*\])?\{(?P<path>[^}]+)\}"
)
FIGURE_ENV_RE = re.compile(r"\\begin\{(figure\*?)\}(.*?)\\end\{\1\}", re.S)
FIGURE_INPUT_COLUMNS = [
    "figure_number",
    "exhibit",
    "paper_include_path",
    "source_basename",
]


def empty_figure_inputs() -> pd.DataFrame:
    return pd.DataFrame(columns=FIGURE_INPUT_COLUMNS)


def strip_latex_comments(text: str) -> str:
    text = re.sub(r"\\begin\{comment\}.*?\\end\{comment\}", "", text, flags=re.S)
    lines: list[str] = []
    for line in text.splitlines():
        if line.lstrip().startswith("%"):
            continue
        out: list[str] = []
        escaped = False
        for char in line:
            if char == "%" and not escaped:
                break
            out.append(char)
            escaped = char == "\\" and not escaped
            if char != "\\":
                escaped = False
        lines.append("".join(out))
    return "\n".join(lines)


def paper_figure_inputs(paper_tex: Path | None) -> pd.DataFrame:
    if paper_tex is None or not paper_tex.exists():
        return empty_figure_inputs()

    clean = strip_latex_comments(paper_tex.read_text(errors="ignore"))
    rows: list[dict[str, object]] = []
    figure_number = 0
    for match in FIGURE_ENV_RE.finditer(clean):
        body = match.group(2)
        includes = [item.group("path") for item in INCLUDEGRAPHICS_RE.finditer(body)]
        if not includes:
            continue
        figure_number += 1
        for include_path in includes:
            rows.append(
                {
                    "figure_number": figure_number,
                    "exhibit": f"Figure {figure_number}",
                    "paper_include_path": include_path,
                    "source_basename": Path(include_path).name,
                }
            )
    return pd.DataFrame(rows, columns=FIGURE_INPUT_COLUMNS)


def read_or_build_paper_figure_inputs(
    paper_tex: Path | None,
    cache_path: Path = PAPER_FIGURE_INPUTS_FILE,
) -> pd.DataFrame:
    if paper_tex is None or not paper_tex.exists():
        if not cache_path.exists():
            raise FileNotFoundError(
                f"Missing {cache_path}. The replication package expects this "
                "repo-internal figure list; pass --paper-tex only when intentionally "
                "refreshing it from a manuscript source."
            )
        return pd.read_csv(cache_path).fillna("")

    inputs = paper_figure_inputs(paper_tex)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    inputs.to_csv(cache_path, index=False, quoting=csv.QUOTE_MINIMAL)
    return inputs


def resolve_generated_figure(root: Path, basename: str) -> Path | None:
    matches: list[Path] = []
    for folder in [root / "output", root / "plots"]:
        if folder.exists():
            matches.extend(
                path
                for path in folder.rglob(basename)
                if path.is_file() and not path.name.startswith("._")
            )
    if not matches:
        return None
    return sorted(matches, key=lambda path: str(path.relative_to(root)))[0]
