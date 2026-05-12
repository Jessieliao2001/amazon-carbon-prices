import re
from pathlib import Path

# ====== 你可以改这里 ======
BASE_DIR = Path("/project/lhansen/HMC_rep26_robust_mac/amazon-carbon-prices/job-outs/mpc")

# xi 和 pe 一一对应
XI_PE_PAIRS = [
    ("0.5", "6.1"),
    ("1", "6.4"),
    ("10000", "6.9"),
    ("0.5", "5.6"),
    ("1", "6.2"),
    ("10000", "6.6"),
]

# 排除检查的 id
EXCLUDED_IDS = {"id_997", "id_998"}

# 如果想打印整个 .err 文件内容，改成 True
PRINT_FULL_ERR = False

# 如果不是打印全文，最多打印前多少行相关内容
MAX_LINES_TO_PRINT = 50
# =========================


def natural_key(s):
    """让 id_2 排在 id_10 前面"""
    return [
        int(text) if text.isdigit() else text.lower()
        for text in re.split(r"(\d+)", str(s))
    ]


def extract_relevant_lines(text):
    """
    提取看起来和参数/报错相关的行。
    如果没提取到，就返回前若干非空行。
    """
    lines = text.splitlines()

    keywords = [
        "param", "parameter", "parameters",
        "xi", "pe", "id",
        "shadow", "price",
        "year done",
        "error", "exception", "traceback",
        "valueerror", "typeerror", "runtimeerror",
        "failed", "abort", "killed", "warning"
    ]

    matched = []
    for line in lines:
        low = line.lower()
        if any(k in low for k in keywords):
            matched.append(line)

    # 去重并保留顺序
    seen = set()
    deduped = []
    for line in matched:
        if line not in seen:
            deduped.append(line)
            seen.add(line)

    if deduped:
        return deduped[:MAX_LINES_TO_PRINT]

    # 如果一个关键词都没匹配到，就返回前若干非空行
    nonempty = [line for line in lines if line.strip()]
    return nonempty[:MAX_LINES_TO_PRINT]


def find_err_files_in_id_dir(id_dir):
    """
    在 id_xxx 文件夹下找所有 .err 文件。
    如果你知道固定文件名，也可以改成:
        return [id_dir / "run.err"] if (id_dir / "run.err").exists() else []
    """
    return sorted(id_dir.rglob("*.err"), key=natural_key)


def main():
    total_checked = 0
    total_nonempty = 0

    for xi, pe in XI_PE_PAIRS:
        pair_dir = BASE_DIR / f"xi_{xi}" / f"pe_{pe}"

        print("\n" + "=" * 100)
        print(f"Checking pair: xi={xi}, pe={pe}")
        print(f"Path: {pair_dir}")

        if not pair_dir.exists():
            print("  -> path does not exist, skipped.")
            continue

        id_dirs = sorted(
            [
                p for p in pair_dir.iterdir()
                if p.is_dir()
                and p.name.startswith("id_")
                and p.name not in EXCLUDED_IDS
            ],
            key=natural_key
        )

        if not id_dirs:
            print("  -> no id_* directories found.")
            continue

        for id_dir in id_dirs:
            err_files = find_err_files_in_id_dir(id_dir)

            if not err_files:
                continue

            for err_file in err_files:
                total_checked += 1

                try:
                    text = err_file.read_text(encoding="utf-8", errors="ignore")
                except Exception as e:
                    print("\n" + "-" * 100)
                    print(f"[READ FAILED] xi={xi}, pe={pe}, id={id_dir.name}, file={err_file}")
                    print(f"Reason: {e}")
                    continue

                # 空文件 or 只有空白字符
                if not text.strip():
                    continue

                total_nonempty += 1

                print("\n" + "-" * 100)
                print(f"[NON-EMPTY ERR] xi={xi}, pe={pe}, id={id_dir.name}")
                print(f"err file: {err_file}")

                if PRINT_FULL_ERR:
                    print("\n[Full .err content]")
                    print(text)
                else:
                    relevant_lines = extract_relevant_lines(text)
                    print("\n[Relevant lines]")
                    for line in relevant_lines:
                        print(line)

    print("\n" + "=" * 100)
    print("Summary")
    print(f"Total .err files checked : {total_checked}")
    print(f"Non-empty .err files     : {total_nonempty}")


if __name__ == "__main__":
    main()