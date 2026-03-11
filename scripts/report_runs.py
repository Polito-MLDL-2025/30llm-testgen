#!/usr/bin/env python3
import argparse
import ast
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.classify_humaneval import get_difficulty_mapping


DIFFICULTIES = [
    "Easy / Basic",
    "Medium / Intermediate",
    "Medium-Hard / Complex",
    "Hard / Advanced",
]
DEFAULT_DATASET_PATH = REPO_ROOT / "llm30" / "pipeline" / "datasets" / "humaneval" / "problems_original.jsonl"
CSV_NAME_AGENT_ALIASES = (
    ("qaagent_competitive", "qaagent_competitive"),
    ("qaagen_competitive", "qaagent_competitive"),
    ("qaagent_merge", "qaagent_merge"),
    ("qaagen_merge", "qaagent_merge"),
    ("merge", "qaagent_merge"),
    ("singleagent", "singleagent"),
    ("qaagent", "qaagent"),
    ("qaagen", "qaagent"),
)
CSV_NAME_PROMPT_SUFFIXES = (
    "default_llm_multi_steps",
    "original_llm_multi_steps",
    "default_accuracy",
    "original_accuracy",
    "default_selector",
    "original_selector",
    "default_scorer",
    "original_scorer",
    "default_concat",
    "original_concat",
    "llm_multi_steps",
    "zero_shot",
    "accuracy",
    "selector",
    "original",
    "default",
    "concat",
    "scorer",
    "llm",
)
CSV_NAME_DIFFICULTY_SUFFIXES = (
    "medium-hard_complex",
    "medium_intermediate",
    "hard_advanced",
    "easy_basic",
)
DIFFICULTY_SUFFIX_BY_NAME = {
    "Easy / Basic": "easy_basic",
    "Medium / Intermediate": "medium_intermediate",
    "Medium-Hard / Complex": "medium-hard_complex",
    "Hard / Advanced": "hard_advanced",
}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Count generated testcases for pipeline CSV reports in a directory by "
            "reading the run folders referenced in each CSV's log_dir column."
        )
    )
    parser.add_argument(
        "--csv-dir",
        help="Directory containing pipeline CSV files to analyze.",
    )
    parser.add_argument(
        "--log-dir",
        default=None,
        help="Optional directory that contains the run folders referenced by log_dir.",
    )
    parser.add_argument(
        "--dataset-path",
        default=str(DEFAULT_DATASET_PATH),
        help="HumanEval dataset JSONL used to map tasks to difficulty buckets.",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="Optional path to write a JSON summary report.",
    )
    parser.add_argument(
        "--output-md",
        default=None,
        help="Optional path to write a Markdown summary report.",
    )
    return parser.parse_args(argv)


def count_testcases_in_file(path: Path) -> int:
    text = path.read_text(encoding="utf-8", errors="ignore")

    plain_asserts = 0
    try:
        tree = ast.parse(text)
        plain_asserts = sum(isinstance(node, ast.Assert) for node in ast.walk(tree))
    except SyntaxError:
        plain_asserts = len(re.findall(r"(?m)^\s*assert\b", text))

    unittest_asserts = len(re.findall(r"\bself\.assert[A-Za-z_]*\s*\(", text))
    return plain_asserts + unittest_asserts


def parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def strip_known_suffix(value: str, suffixes: tuple[str, ...]) -> tuple[str, str | None]:
    for suffix in suffixes:
        needle = f"_{suffix}"
        if value.endswith(needle):
            return value[: -len(needle)], suffix
    return value, None


def extract_csv_name_metadata(csv_path: Path) -> dict[str, str]:
    stem = csv_path.stem
    stem_without_difficulty, difficulty_scope = strip_known_suffix(
        stem,
        CSV_NAME_DIFFICULTY_SUFFIXES,
    )
    stem_without_prompt, prompt_suffix = strip_known_suffix(
        stem_without_difficulty,
        CSV_NAME_PROMPT_SUFFIXES,
    )

    agent_type = "unknown"
    for alias, normalized_agent in CSV_NAME_AGENT_ALIASES:
        if re.search(rf"(?:^|_){re.escape(alias)}(?:_|$)", stem_without_prompt):
            agent_type = normalized_agent
            break

    generator_prompt = ""
    strategy_type = ""
    prompt_type = ""

    if prompt_suffix == "zero_shot":
        generator_prompt = "zero_shot"
        prompt_type = "zero_shot"
    elif prompt_suffix in {"accuracy", "selector", "scorer", "concat", "llm", "llm_multi_steps"}:
        strategy_type = prompt_suffix
        prompt_match = re.search(r"_(default|original)$", stem_without_prompt)
        if prompt_match:
            generator_prompt = prompt_match.group(1)
            prompt_type = generator_prompt
        elif prompt_suffix in {"default", "original"}:
            generator_prompt = prompt_suffix
            prompt_type = prompt_suffix
    elif prompt_suffix in {"default", "original"}:
        generator_prompt = prompt_suffix
        prompt_type = prompt_suffix
    elif prompt_suffix:
        prefix, separator, suffix = prompt_suffix.partition("_")
        if prefix in {"default", "original"} and separator and suffix:
            generator_prompt = prefix
            prompt_type = prefix
            strategy_type = suffix
        else:
            strategy_type = prompt_suffix
            prompt_type = prompt_suffix

    return {
        "agent_type": agent_type,
        "prompt_type": prompt_type,
        "generator_prompt": generator_prompt,
        "strategy_type": strategy_type,
        "difficulty_scope": difficulty_scope or "",
    }


def resolve_run_dir(log_dir_value: str, logs_root: Path) -> Path:
    log_dir_value = log_dir_value.strip()
    run_name = Path(log_dir_value).name
    basename_candidate = logs_root / run_name

    if run_name and basename_candidate.exists():
        return basename_candidate.resolve()

    nearby_matches: list[str] = []
    if run_name:
        prefix = run_name.rsplit("-", 1)[0]
        nearby_matches = sorted(
            path.name
            for path in logs_root.glob(f"{prefix}-*")
            if path.is_dir()
        )[:5]

    detail = f"Expected local run folder '{basename_candidate}'."
    if nearby_matches:
        detail += f" Nearby matches under --log-dir: {', '.join(nearby_matches)}"

    raise FileNotFoundError(
        f"Could not resolve run folder from log_dir='{log_dir_value}'. {detail}"
    )


def csv_has_log_dir_column(csv_path: Path) -> bool:
    try:
        with csv_path.open(encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, None)
    except OSError:
        return False
    return bool(header) and "log_dir" in header


def discover_csv_files(csv_dir: Path) -> list[Path]:
    if not csv_dir.exists():
        raise FileNotFoundError(f"CSV directory not found: {csv_dir}")
    if not csv_dir.is_dir():
        raise NotADirectoryError(f"CSV directory is not a directory: {csv_dir}")

    csv_files = sorted(
        path for path in csv_dir.glob("*.csv")
        if path.is_file() and csv_has_log_dir_column(path)
    )
    if not csv_files:
        raise ValueError(f"No CSV files with a log_dir column found in {csv_dir}")
    return csv_files


def load_csv_rows(csv_path: Path) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, str] | None]:
    with csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    run_rows = [
        row
        for row in rows
        if (row.get("run") or "").strip().lower() != "aggregate"
    ]
    aggregate_row = next(
        (
            row
            for row in rows
            if (row.get("run") or "").strip().lower() == "aggregate"
        ),
        None,
    )
    return rows, run_rows, aggregate_row


def summarize_metric_stats(csv_path: Path) -> dict[str, float | None]:
    _, run_rows, aggregate_row = load_csv_rows(csv_path)

    def resolve_metric(field_names: tuple[str, ...]) -> float | None:
        if aggregate_row is not None:
            for field_name in field_names:
                value = parse_float(aggregate_row.get(field_name))
                if value is not None:
                    return value

        values: list[float] = []
        for row in run_rows:
            for field_name in field_names:
                value = parse_float(row.get(field_name))
                if value is not None:
                    values.append(value)
                    break
        if not values:
            return None
        return sum(values) / len(values)

    return {
        "accuracy": resolve_metric(("accuracy",)),
        "line_coverage": resolve_metric(("line_coverage", "coverage")),
        "branch_coverage": resolve_metric(("branch_coverage",)),
        "coverage_score": resolve_metric(("coverage",)),
    }


def empty_metric_stats() -> dict[str, float | None]:
    return {
        "accuracy": None,
        "line_coverage": None,
        "branch_coverage": None,
        "coverage_score": None,
    }


def summarize_difficulty_token_stats(csv_path: Path) -> dict[str, float | int | None]:
    token_stats = summarize_token_stats(csv_path)
    return {
        "total_input_tokens": token_stats["total_input_tokens"],
        "total_output_tokens": token_stats["total_output_tokens"],
        "total_tokens": token_stats["total_tokens"],
        "avg_input_tokens_per_task": token_stats["avg_input_tokens_per_task"],
        "avg_output_tokens_per_task": token_stats["avg_output_tokens_per_task"],
        "avg_total_tokens_per_task": token_stats["avg_total_tokens_per_task"],
    }


def empty_difficulty_token_stats() -> dict[str, float | int | None]:
    return {
        "total_input_tokens": None,
        "total_output_tokens": None,
        "total_tokens": None,
        "avg_input_tokens_per_task": None,
        "avg_output_tokens_per_task": None,
        "avg_total_tokens_per_task": None,
    }


def init_difficulty_summary() -> dict[str, object]:
    return {
        "tasks": None,
        "total_testcases": None,
        "avg_testcases": None,
        "metric_stats": empty_metric_stats(),
        "token_stats": empty_difficulty_token_stats(),
    }


def load_difficulty_metrics(csv_path: Path) -> dict[str, dict[str, object]]:
    by_difficulty: dict[str, dict[str, object]] = {}

    for difficulty, suffix in DIFFICULTY_SUFFIX_BY_NAME.items():
        difficulty_csv_path = csv_path.with_name(f"{csv_path.stem}_{suffix}.csv")
        if not difficulty_csv_path.exists():
            continue

        _, _, aggregate_row = load_csv_rows(difficulty_csv_path)
        metric_stats = summarize_metric_stats(difficulty_csv_path)
        token_stats = summarize_difficulty_token_stats(difficulty_csv_path)
        difficulty_summary = init_difficulty_summary()
        difficulty_summary["tasks"] = parse_int(aggregate_row.get("tasks_evaluated")) if aggregate_row else None
        difficulty_summary["metric_stats"] = metric_stats
        difficulty_summary["token_stats"] = token_stats
        by_difficulty[difficulty] = difficulty_summary

    return by_difficulty


def summarize_token_stats(csv_path: Path, fallback_task_instances: int = 0) -> dict[str, float | int | None]:
    _, run_rows, aggregate_row = load_csv_rows(csv_path)

    total_input_tokens = 0
    total_output_tokens = 0
    total_tasks_evaluated = 0
    has_tasks_evaluated = False
    runs_with_token_stats = 0

    for row in run_rows:
        input_tokens = parse_int(row.get("input_tokens"))
        output_tokens = parse_int(row.get("output_tokens"))
        if input_tokens is None and output_tokens is None:
            continue

        total_input_tokens += input_tokens or 0
        total_output_tokens += output_tokens or 0
        runs_with_token_stats += 1

        tasks_evaluated = parse_int(row.get("tasks_evaluated"))
        if tasks_evaluated is not None and tasks_evaluated > 0:
            total_tasks_evaluated += tasks_evaluated
            has_tasks_evaluated = True

    if not has_tasks_evaluated and aggregate_row is not None:
        aggregate_tasks_evaluated = parse_int(aggregate_row.get("tasks_evaluated"))
        if aggregate_tasks_evaluated is not None and aggregate_tasks_evaluated > 0:
            total_tasks_evaluated = aggregate_tasks_evaluated
            has_tasks_evaluated = True

    total_tokens = total_input_tokens + total_output_tokens
    csv_task_instances = total_tasks_evaluated if has_tasks_evaluated and total_tasks_evaluated > 0 else None
    token_task_instances = total_tasks_evaluated if has_tasks_evaluated and total_tasks_evaluated > 0 else fallback_task_instances
    if token_task_instances <= 0:
        token_task_instances = None

    return {
        "run_row_count": len(run_rows),
        "runs_with_token_stats": runs_with_token_stats,
        "csv_task_instances": csv_task_instances,
        "token_task_instances": token_task_instances,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_tokens": total_tokens,
        "avg_input_tokens_per_run": (total_input_tokens / runs_with_token_stats) if runs_with_token_stats else 0.0,
        "avg_output_tokens_per_run": (total_output_tokens / runs_with_token_stats) if runs_with_token_stats else 0.0,
        "avg_total_tokens_per_run": (total_tokens / runs_with_token_stats) if runs_with_token_stats else 0.0,
        "avg_input_tokens_per_task": (total_input_tokens / token_task_instances) if token_task_instances else None,
        "avg_output_tokens_per_task": (total_output_tokens / token_task_instances) if token_task_instances else None,
        "avg_total_tokens_per_task": (total_tokens / token_task_instances) if token_task_instances else None,
    }


def read_run_dirs(csv_path: Path, logs_root: Path) -> list[Path]:
    with csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "log_dir" not in reader.fieldnames:
            raise ValueError(f"{csv_path} does not contain a log_dir column.")

        run_dirs: list[Path] = []
        seen: set[Path] = set()
        for row in reader:
            log_dir_value = (row.get("log_dir") or "").strip()
            if not log_dir_value:
                continue
            run_dir = resolve_run_dir(log_dir_value, logs_root)
            if run_dir in seen:
                continue
            seen.add(run_dir)
            run_dirs.append(run_dir)
        return run_dirs


def parse_direct_task_id(name: str) -> str | None:
    prefix, separator, suffix = name.partition("_")
    if not separator or not suffix:
        return None
    return f"{prefix}/{suffix}"


def collect_problem_dir_counts(problem_dir: Path) -> dict[str, int]:
    dataset_prefix = problem_dir.name.removeprefix("problem_")
    task_counts: dict[str, int] = {}

    for task_dir in sorted(problem_dir.iterdir()):
        if not task_dir.is_dir():
            continue
        for filename in ("generated_tests.txt", "generated_tests.py"):
            testcase_file = task_dir / filename
            if testcase_file.exists():
                task_id = f"{dataset_prefix}/{task_dir.name}"
                task_counts[task_id] = count_testcases_in_file(testcase_file)
                break
    return task_counts


def collect_direct_dir_counts(run_dir: Path) -> dict[str, int]:
    task_counts: dict[str, int] = {}

    for task_dir in sorted(run_dir.iterdir()):
        if not task_dir.is_dir():
            continue
        task_id = parse_direct_task_id(task_dir.name)
        if not task_id:
            continue
        for filename in ("generated_tests.py", "generated_tests.txt"):
            testcase_file = task_dir / filename
            if testcase_file.exists():
                task_counts[task_id] = count_testcases_in_file(testcase_file)
                break
    return task_counts


def analyze_run_dir(run_dir: Path) -> dict[str, int]:
    task_counts: dict[str, int] = {}

    problem_dirs = sorted(
        path for path in run_dir.iterdir()
        if path.is_dir() and path.name.startswith("problem_")
    )
    for problem_dir in problem_dirs:
        task_counts.update(collect_problem_dir_counts(problem_dir))

    if not task_counts:
        task_counts.update(collect_direct_dir_counts(run_dir))

    if not task_counts:
        raise ValueError(f"No generated test files found in {run_dir}")
    return task_counts


def init_bucket_stats() -> dict[str, dict[str, float | int]]:
    stats = {
        difficulty: {"tasks": 0, "total_testcases": 0}
        for difficulty in DIFFICULTIES
    }
    stats["Unknown"] = {"tasks": 0, "total_testcases": 0}
    return stats


def summarize_counts(
    csv_path: Path,
    run_dirs: list[Path] | None,
    difficulty_mapping: dict[str, str] | None,
) -> dict[str, object]:
    csv_metadata = extract_csv_name_metadata(csv_path)
    testcase_stats_skipped = run_dirs is None
    run_dir_names = [run_dir.name for run_dir in run_dirs] if run_dirs is not None else []
    run_count: int | None = None
    task_instances: int | None = None
    total_testcases: int | None = None
    avg_testcases: float | None = None
    by_difficulty: dict[str, dict[str, object]] = load_difficulty_metrics(csv_path)

    if run_dirs is not None and difficulty_mapping is not None:
        difficulty_stats = init_bucket_stats()
        task_instances = 0
        total_testcases = 0
        run_count = len(run_dirs)

        for run_dir in run_dirs:
            task_counts = analyze_run_dir(run_dir)
            task_instances += len(task_counts)
            total_testcases += sum(task_counts.values())

            for task_id, testcase_count in task_counts.items():
                difficulty = difficulty_mapping.get(task_id, "Unknown")
                difficulty_bucket = difficulty_stats.setdefault(
                    difficulty,
                    {"tasks": 0, "total_testcases": 0},
                )
                difficulty_bucket["tasks"] += 1
                difficulty_bucket["total_testcases"] += testcase_count

        for difficulty, stats in difficulty_stats.items():
            tasks = int(stats["tasks"])
            if tasks == 0:
                continue
            total = int(stats["total_testcases"])
            difficulty_summary = by_difficulty.setdefault(difficulty, init_difficulty_summary())
            difficulty_summary["tasks"] = tasks
            difficulty_summary["total_testcases"] = total
            difficulty_summary["avg_testcases"] = total / tasks

        avg_testcases = (total_testcases / task_instances) if task_instances else None

    token_stats = summarize_token_stats(csv_path, task_instances or 0)
    metric_stats = summarize_metric_stats(csv_path)
    if run_count is None:
        run_count = int(token_stats["run_row_count"])
    if task_instances is None:
        csv_task_instances = token_stats.get("csv_task_instances")
        task_instances = int(csv_task_instances) if csv_task_instances is not None else None

    return {
        "pipeline": csv_path.stem,
        **csv_metadata,
        "testcase_stats_skipped": testcase_stats_skipped,
        "csv_path": str(csv_path),
        "run_count": run_count,
        "run_dirs": run_dir_names,
        "task_instances": task_instances,
        "total_testcases": total_testcases,
        "avg_testcases": avg_testcases,
        "metric_stats": metric_stats,
        "token_stats": token_stats,
        "by_difficulty": by_difficulty,
    }


def write_summary_json(
    output_path: Path,
    summaries: list[dict[str, object]],
    *,
    csv_dir: Path,
    logs_root: Path | None,
    dataset_path: str,
) -> None:
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "csv_dir": str(csv_dir),
        "log_dir": str(logs_root) if logs_root is not None else None,
        "dataset_path": dataset_path,
        "pipeline_count": len(summaries),
        "pipelines": summaries,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")


def format_markdown_number(value: float | int | None) -> str:
    if value is None:
        return "-"
    if isinstance(value, int):
        return str(value)
    return f"{float(value):.2f}"


def write_summary_markdown(
    output_path: Path,
    summaries: list[dict[str, object]],
    *,
    csv_dir: Path,
    logs_root: Path | None,
    dataset_path: str,
) -> None:
    lines = [
        "# Testcase Count Report",
        "",
        f"- Generated at: {datetime.now(timezone.utc).isoformat()}",
        f"- CSV dir: `{csv_dir}`",
        f"- Log dir: `{logs_root}`" if logs_root is not None else "- Log dir: skipped",
        f"- Dataset path: `{dataset_path}`",
        f"- Pipelines analyzed: {len(summaries)}",
        "",
        "## Overview",
        "",
        "| Pipeline | Agent | Prompt | Strategy | Runs | Tasks | Total Testcases | Avg Testcases/Task | Accuracy | Line Coverage | Branch Coverage | Coverage Score | Avg Tokens/Run | Avg Tokens/Task |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    for summary in summaries:
        metric_stats = summary["metric_stats"]
        token_stats = summary["token_stats"]
        lines.append(
            "| "
            f"{summary['pipeline']} | "
            f"{summary['agent_type']} | "
            f"{summary['prompt_type'] or '-'} | "
            f"{summary['strategy_type'] or '-'} | "
            f"{format_markdown_number(summary['run_count'])} | "
            f"{format_markdown_number(summary['task_instances'])} | "
            f"{format_markdown_number(summary['total_testcases'])} | "
            f"{format_markdown_number(summary['avg_testcases'])} | "
            f"{format_markdown_number(metric_stats['accuracy'])} | "
            f"{format_markdown_number(metric_stats['line_coverage'])} | "
            f"{format_markdown_number(metric_stats['branch_coverage'])} | "
            f"{format_markdown_number(metric_stats['coverage_score'])} | "
            f"{format_markdown_number(float(token_stats['avg_total_tokens_per_run']))} | "
            f"{format_markdown_number(token_stats['avg_total_tokens_per_task'])} |"
        )

    for summary in summaries:
        metric_stats = summary["metric_stats"]
        token_stats = summary["token_stats"]
        lines.extend(
            [
                "",
                f"## {summary['pipeline']}",
                "",
                f"- CSV: `{summary['csv_path']}`",
                f"- Agent type: `{summary['agent_type']}`",
                f"- Prompt type: `{summary['prompt_type'] or '-'}`",
                f"- Generator prompt: `{summary['generator_prompt'] or '-'}`",
                f"- Strategy type: `{summary['strategy_type'] or '-'}`",
                f"- Difficulty scope: `{summary['difficulty_scope'] or '-'}`",
                f"- Runs: {format_markdown_number(summary['run_count'])}",
                f"- Task instances: {format_markdown_number(summary['task_instances'])}",
                (
                    "- Testcase statistics: skipped because `--log-dir` was not provided"
                    if summary["testcase_stats_skipped"]
                    else "- Testcase statistics: computed from run directories"
                ),
                f"- Total testcases: {format_markdown_number(summary['total_testcases'])}",
                f"- Avg testcases/task: {format_markdown_number(summary['avg_testcases'])}",
                (
                    "- Avg metrics:"
                    f" accuracy={format_markdown_number(metric_stats['accuracy'])},"
                    f" line_coverage={format_markdown_number(metric_stats['line_coverage'])},"
                    f" branch_coverage={format_markdown_number(metric_stats['branch_coverage'])},"
                    f" coverage_score={format_markdown_number(metric_stats['coverage_score'])}"
                ),
                (
                    "- Avg tokens:"
                    f" input/run={format_markdown_number(float(token_stats['avg_input_tokens_per_run']))},"
                    f" output/run={format_markdown_number(float(token_stats['avg_output_tokens_per_run']))},"
                    f" total/run={format_markdown_number(float(token_stats['avg_total_tokens_per_run']))},"
                    f" total/task={format_markdown_number(token_stats['avg_total_tokens_per_task'])}"
                ),
                (
                    "- Token totals:"
                    f" input={format_markdown_number(token_stats['total_input_tokens'])},"
                    f" output={format_markdown_number(token_stats['total_output_tokens'])},"
                    f" total={format_markdown_number(token_stats['total_tokens'])},"
                    f" token_tasks={format_markdown_number(token_stats['token_task_instances'])}"
                ),
                "",
                "### By Difficulty",
                "",
            ]
        )

        by_difficulty = summary["by_difficulty"]
        if not by_difficulty:
            lines.append("Skipped because testcase counting was not performed.")
        else:
            lines.extend(
                [
                    "| Difficulty | Tasks | Total Testcases | Avg Testcases/Task | Accuracy | Line Coverage | Branch Coverage | Coverage Score | Avg Tokens/Task |",
                    "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
                ]
            )
            for difficulty in DIFFICULTIES + ["Unknown"]:
                stats = by_difficulty.get(difficulty)
                if not stats:
                    continue
                metric_stats = stats.get("metric_stats", {})
                difficulty_token_stats = stats.get("token_stats", {})
                lines.append(
                    "| "
                    f"{difficulty} | "
                    f"{format_markdown_number(stats.get('tasks'))} | "
                    f"{format_markdown_number(stats.get('total_testcases'))} | "
                    f"{format_markdown_number(stats.get('avg_testcases'))} | "
                    f"{format_markdown_number(metric_stats.get('accuracy'))} | "
                    f"{format_markdown_number(metric_stats.get('line_coverage'))} | "
                    f"{format_markdown_number(metric_stats.get('branch_coverage'))} | "
                    f"{format_markdown_number(metric_stats.get('coverage_score'))} | "
                    f"{format_markdown_number(difficulty_token_stats.get('avg_total_tokens_per_task'))} |"
                )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_summary(summary: dict[str, object]) -> None:
    print(summary["pipeline"])
    print(
        "  Metadata: "
        f"agent_type={summary['agent_type']}, "
        f"prompt_type={summary['prompt_type'] or '-'}, "
        f"generator_prompt={summary['generator_prompt'] or '-'}, "
        f"strategy_type={summary['strategy_type'] or '-'}"
    )
    if summary["difficulty_scope"]:
        print(f"  Difficulty scope: {summary['difficulty_scope']}")
    print(f"  CSV: {summary['csv_path']}")
    print(f"  Runs: {format_markdown_number(summary['run_count'])}")
    if summary["run_dirs"]:
        print(f"  Run folders: {', '.join(summary['run_dirs'])}")
    else:
        print("  Run folders: skipped")
    if summary["testcase_stats_skipped"]:
        print("  Warning: testcase statistics skipped because --log-dir was not provided.")
    print(f"  Task instances: {format_markdown_number(summary['task_instances'])}")
    print(f"  Total testcases: {format_markdown_number(summary['total_testcases'])}")
    print(f"  Avg testcases/task: {format_markdown_number(summary['avg_testcases'])}")
    metric_stats = summary["metric_stats"]
    print(
        "  Avg metrics: "
        f"accuracy={format_markdown_number(metric_stats['accuracy'])}, "
        f"line_coverage={format_markdown_number(metric_stats['line_coverage'])}, "
        f"branch_coverage={format_markdown_number(metric_stats['branch_coverage'])}, "
        f"coverage_score={format_markdown_number(metric_stats['coverage_score'])}"
    )
    token_stats = summary["token_stats"]
    print(
        "  Avg tokens: "
        f"input/run={float(token_stats['avg_input_tokens_per_run']):.2f}, "
        f"output/run={float(token_stats['avg_output_tokens_per_run']):.2f}, "
        f"total/run={float(token_stats['avg_total_tokens_per_run']):.2f}, "
        f"total/task={format_markdown_number(token_stats['avg_total_tokens_per_task'])}"
    )
    if not summary["by_difficulty"]:
        print("  By difficulty: skipped")
        print()
        return

    print("  By difficulty:")

    by_difficulty = summary["by_difficulty"]
    for difficulty in DIFFICULTIES + ["Unknown"]:
        stats = by_difficulty.get(difficulty)
        if not stats:
            continue
        metric_stats = stats.get("metric_stats", {})
        difficulty_token_stats = stats.get("token_stats", {})
        print(
            f"    {difficulty}: "
            f"tasks={format_markdown_number(stats.get('tasks'))}, "
            f"total_testcases={format_markdown_number(stats.get('total_testcases'))}, "
            f"avg_testcases={format_markdown_number(stats.get('avg_testcases'))}, "
            f"accuracy={format_markdown_number(metric_stats.get('accuracy'))}, "
            f"line_coverage={format_markdown_number(metric_stats.get('line_coverage'))}, "
            f"branch_coverage={format_markdown_number(metric_stats.get('branch_coverage'))}, "
            f"coverage_score={format_markdown_number(metric_stats.get('coverage_score'))}, "
            f"avg_tokens_per_task={format_markdown_number(difficulty_token_stats.get('avg_total_tokens_per_task'))}"
        )
    print()


def main(argv=None) -> int:
    args = parse_args(argv)
    logs_root = Path(args.log_dir).resolve() if args.log_dir else None
    csv_dir = Path(args.csv_dir).resolve()
    csv_files = discover_csv_files(csv_dir)
    difficulty_mapping = get_difficulty_mapping(args.dataset_path) if logs_root is not None else None

    if logs_root is None:
        print("Warning: --log-dir not provided; skipping testcase counting from run directories.")

    summaries: list[dict[str, object]] = []
    for csv_path in csv_files:
        run_dirs = read_run_dirs(csv_path, logs_root) if logs_root is not None else None
        summaries.append(summarize_counts(csv_path, run_dirs, difficulty_mapping))

    for summary in summaries:
        print_summary(summary)

    if args.output_json:
        output_path = Path(args.output_json).resolve()
        write_summary_json(
            output_path,
            summaries,
            csv_dir=csv_dir,
            logs_root=logs_root,
            dataset_path=args.dataset_path,
        )
        print(f"Wrote summary JSON to {output_path}")

    if args.output_md:
        output_path = Path(args.output_md).resolve()
        write_summary_markdown(
            output_path,
            summaries,
            csv_dir=csv_dir,
            logs_root=logs_root,
            dataset_path=args.dataset_path,
        )
        print(f"Wrote summary Markdown to {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
