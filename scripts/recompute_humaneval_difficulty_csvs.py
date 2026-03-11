#!/usr/bin/env python3
import argparse
import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    # Ensure local imports work when running via "python scripts/...".
    sys.path.insert(0, str(REPO_ROOT))

from scripts.classify_humaneval import get_difficulty_mapping
from scripts.utils.summary_parser import compute_avg_tokens_per_task


DIFFICULTIES = [
    "Easy / Basic",
    "Medium / Intermediate",
    "Medium-Hard / Complex",
    "Hard / Advanced",
]

OUTPUT_FIELDS = [
    "run",
    "tasks_evaluated",
    "accuracy",
    "first_five_line_coverage",
    "line_coverage",
    "first_five_coverage",
    "coverage",
    "first_five_branch_coverage",
    "branch_coverage",
    "input_tokens",
    "output_tokens",
    "avg_tokens_per_task",
]


def safe_difficulty_name(difficulty: str) -> str:
    return difficulty.replace(" / ", "_").replace(" ", "_").lower()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Recompute HumanEval per-difficulty accuracy and coverage CSVs "
            "from archived run details."
        )
    )
    parser.add_argument(
        "csv_paths",
        nargs="+",
        type=Path,
        help="One or more aggregate result CSV files to recompute.",
    )
    parser.add_argument(
        "--dataset-path",
        type=Path,
        default=Path("llm30/pipeline/datasets/humaneval/problems_original.jsonl"),
        help="HumanEval dataset JSONL used to classify task difficulty.",
    )
    return parser.parse_args(argv)


def as_float(value: str | float | int | None, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value: str | float | int | None, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def parse_details_file(details_path: Path) -> list[dict[str, str | float | int]]:
    entries: list[dict[str, str | float | int]] = []
    current: dict[str, str] = {}

    with details_path.open() as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue

            if line.startswith("Problem ID:"):
                if current:
                    entries.append(normalize_detail_entry(current, details_path))
                current = {"problem_id": line.partition(":")[2].strip()}
                continue

            if ":" not in line:
                continue

            key, _, value = line.partition(":")
            current[key.strip().lower()] = value.strip()

    if current:
        entries.append(normalize_detail_entry(current, details_path))

    return entries


def normalize_detail_entry(
    raw_entry: dict[str, str],
    details_path: Path,
) -> dict[str, str | float | int]:
    problem_id = raw_entry.get("problem_id", "").strip()
    if not problem_id:
        raise ValueError(f"Missing problem id in {details_path}")

    first_five_coverage = as_float(raw_entry.get("first five coverage"))
    coverage = as_float(raw_entry.get("coverage"))

    return {
        "task_id": problem_id,
        "accuracy": as_float(raw_entry.get("accuracy")),
        "first_five_line_coverage": as_float(
            raw_entry.get("first five line coverage"),
            first_five_coverage,
        ),
        "line_coverage": as_float(raw_entry.get("line coverage"), coverage),
        "first_five_coverage": first_five_coverage,
        "coverage": coverage,
        "first_five_branch_coverage": as_float(
            raw_entry.get("first five branch coverage"),
            0.0,
        ),
        "branch_coverage": as_float(raw_entry.get("branch coverage"), 0.0),
        "input_tokens": as_int(raw_entry.get("input tokens")),
        "output_tokens": as_int(raw_entry.get("output tokens")),
    }


def aggregate_entries(
    entries: list[dict[str, str | float | int]],
) -> dict[str, float | int]:
    tasks_evaluated = len(entries)
    if tasks_evaluated == 0:
        return {
            "tasks_evaluated": 0,
            "accuracy": 0.0,
            "first_five_line_coverage": 0.0,
            "line_coverage": 0.0,
            "first_five_coverage": 0.0,
            "coverage": 0.0,
            "first_five_branch_coverage": 0.0,
            "branch_coverage": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
        }

    sums = {
        "accuracy": 0.0,
        "first_five_line_coverage": 0.0,
        "line_coverage": 0.0,
        "first_five_coverage": 0.0,
        "coverage": 0.0,
        "first_five_branch_coverage": 0.0,
        "branch_coverage": 0.0,
        "input_tokens": 0,
        "output_tokens": 0,
    }

    for entry in entries:
        sums["accuracy"] += as_float(entry["accuracy"])
        sums["first_five_line_coverage"] += as_float(entry["first_five_line_coverage"])
        sums["line_coverage"] += as_float(entry["line_coverage"])
        sums["first_five_coverage"] += as_float(entry["first_five_coverage"])
        sums["coverage"] += as_float(entry["coverage"])
        sums["first_five_branch_coverage"] += as_float(entry["first_five_branch_coverage"])
        sums["branch_coverage"] += as_float(entry["branch_coverage"])
        sums["input_tokens"] += as_int(entry["input_tokens"])
        sums["output_tokens"] += as_int(entry["output_tokens"])

    return {
        "tasks_evaluated": tasks_evaluated,
        "accuracy": sums["accuracy"] / tasks_evaluated,
        "first_five_line_coverage": sums["first_five_line_coverage"] / tasks_evaluated,
        "line_coverage": sums["line_coverage"] / tasks_evaluated,
        "first_five_coverage": sums["first_five_coverage"] / tasks_evaluated,
        "coverage": sums["coverage"] / tasks_evaluated,
        "first_five_branch_coverage": sums["first_five_branch_coverage"] / tasks_evaluated,
        "branch_coverage": sums["branch_coverage"] / tasks_evaluated,
        "input_tokens": sums["input_tokens"],
        "output_tokens": sums["output_tokens"],
    }


def resolve_run_dir(csv_path: Path, log_dir_value: str) -> Path:
    log_dir = Path(log_dir_value)
    candidates = [log_dir]

    if log_dir.is_absolute():
        candidates.append(csv_path.parent / log_dir.name)
    else:
        candidates.append((csv_path.parent / log_dir).resolve())
        candidates.append(csv_path.parent / log_dir.name)

    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        f"Could not resolve archived run directory for {log_dir_value!r} from {csv_path}"
    )


def load_run_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        return [
            row
            for row in reader
            if row.get("run", "").strip().lower() != "aggregate"
            and row.get("log_dir", "").strip()
        ]


def validate_overall_metrics(
    csv_path: Path,
    csv_row: dict[str, str],
    overall_stats: dict[str, float | int],
) -> None:
    checks = {
        "accuracy": as_float(csv_row.get("accuracy")),
        "first_five_coverage": as_float(csv_row.get("first_five_coverage")),
        "coverage": as_float(csv_row.get("coverage")),
    }

    for key, expected in checks.items():
        actual = as_float(overall_stats[key])
        if abs(actual - expected) > 1e-6:
            raise ValueError(
                f"{csv_path.name} run {csv_row.get('run')} mismatch for {key}: "
                f"expected {expected}, recomputed {actual}"
            )


def recompute_run_difficulty_stats(
    run_dir: Path,
    difficulty_mapping: dict[str, str],
) -> dict[str, dict[str, float | int]]:
    details_path = run_dir / "details.txt"
    if not details_path.exists():
        raise FileNotFoundError(f"Missing details.txt in {run_dir}")

    all_entries = parse_details_file(details_path)
    grouped_entries = {difficulty: [] for difficulty in DIFFICULTIES}
    missing_tasks: list[str] = []

    for entry in all_entries:
        task_id = str(entry["task_id"])
        difficulty = difficulty_mapping.get(task_id)
        if difficulty is None:
            missing_tasks.append(task_id)
            continue
        grouped_entries[difficulty].append(entry)

    if missing_tasks:
        missing_preview = ", ".join(sorted(missing_tasks)[:10])
        raise KeyError(
            f"Difficulty classification missing for {len(missing_tasks)} task(s) in {run_dir}: "
            f"{missing_preview}"
        )

    return {
        difficulty: aggregate_entries(entries)
        for difficulty, entries in grouped_entries.items()
        if entries
    }


def build_aggregate_row(rows: list[dict[str, float | int]]) -> dict[str, float | int | str]:
    if not rows:
        raise ValueError("Cannot build aggregate row from an empty row set.")

    sum_tasks = sum(as_int(row["tasks_evaluated"]) for row in rows)
    sum_input = sum(as_int(row["input_tokens"]) for row in rows)
    sum_output = sum(as_int(row["output_tokens"]) for row in rows)

    aggregate_row: dict[str, float | int | str] = {
        "run": "aggregate",
        "tasks_evaluated": sum_tasks,
        "input_tokens": sum_input,
        "output_tokens": sum_output,
        "avg_tokens_per_task": compute_avg_tokens_per_task(
            sum_input,
            sum_output,
            sum_tasks,
        ),
    }

    for key in [
        "accuracy",
        "first_five_line_coverage",
        "line_coverage",
        "first_five_coverage",
        "coverage",
        "first_five_branch_coverage",
        "branch_coverage",
    ]:
        aggregate_row[key] = sum(as_float(row[key]) for row in rows) / len(rows)

    return aggregate_row


def write_difficulty_csv(
    input_csv_path: Path,
    difficulty: str,
    rows: list[dict[str, float | int | str]],
) -> Path:
    output_path = input_csv_path.with_name(
        f"{input_csv_path.stem}_{safe_difficulty_name(difficulty)}.csv"
    )
    with output_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return output_path


def recompute_csv(
    csv_path: Path,
    difficulty_mapping: dict[str, str],
) -> list[Path]:
    run_rows = load_run_rows(csv_path)
    difficulty_rows: dict[str, list[dict[str, float | int | str]]] = {
        difficulty: []
        for difficulty in DIFFICULTIES
    }

    for run_row in run_rows:
        run_dir = resolve_run_dir(csv_path, run_row["log_dir"])
        details_entries = parse_details_file(run_dir / "details.txt")
        validate_overall_metrics(
            csv_path,
            run_row,
            aggregate_entries(details_entries),
        )
        run_difficulty_stats = recompute_run_difficulty_stats(run_dir, difficulty_mapping)

        for difficulty, stats in run_difficulty_stats.items():
            difficulty_rows[difficulty].append(
                {
                    "run": run_row["run"],
                    **stats,
                    "avg_tokens_per_task": compute_avg_tokens_per_task(
                        as_int(stats["input_tokens"]),
                        as_int(stats["output_tokens"]),
                        as_int(stats["tasks_evaluated"]),
                    ),
                }
            )

    written_paths: list[Path] = []
    for difficulty in DIFFICULTIES:
        rows = difficulty_rows[difficulty]
        if not rows:
            continue
        rows_to_write = rows + [build_aggregate_row(rows)]
        written_paths.append(write_difficulty_csv(csv_path, difficulty, rows_to_write))

    return written_paths


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    difficulty_mapping = get_difficulty_mapping(str(args.dataset_path))
    if not difficulty_mapping:
        raise FileNotFoundError(
            f"Could not load difficulty mapping from {args.dataset_path}"
        )

    all_written_paths: list[Path] = []
    for csv_path in args.csv_paths:
        written_paths = recompute_csv(csv_path, difficulty_mapping)
        all_written_paths.extend(written_paths)
        print(f"{csv_path}: wrote {len(written_paths)} per-difficulty CSVs")

    print(f"Generated {len(all_written_paths)} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
