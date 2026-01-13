#!/usr/bin/env python3
import argparse
import csv
import multiprocessing
import queue as queue_module
import sys
import time
from datetime import datetime
from pathlib import Path


def sanitize_name(value: str) -> str:
    return value.replace("/", "_").replace(":", "_").replace(" ", "_")


def list_log_dirs(logs_root: Path) -> set[Path]:
    if not logs_root.exists():
        return set()
    prefixes = ("multi_agent-", "QAagent-", "QAagent_merge-")
    return {
        path.resolve()
        for path in logs_root.iterdir()
        if path.is_dir() and path.name.startswith(prefixes)
    }


def parse_summary(summary_path: Path) -> dict[str, float | int]:
    values: dict[str, str] = {}
    with summary_path.open() as handle:
        for line in handle:
            line = line.strip()
            if not line or ":" not in line:
                continue
            key, _, value = line.partition(":")
            values[key.strip().lower()] = value.strip()

    return {
        "accuracy": float(values["accuracy"]),
        "first_five_coverage": float(values["first five coverage"]),
        "coverage": float(values["coverage"]),
        "input_tokens": int(values["input tokens"]),
        "output_tokens": int(values["output tokens"]),
    }


def build_argv(
        args: argparse.Namespace, generator_prompt: str, merge_strategy: str
) -> list[str]:
    return [
        "--dataset",
        args.dataset,
        "--model",
        args.model,
        "--max-tasks",
        str(args.max_tasks),
        "--max-workers",
        str(args.max_workers),
        "--generator-prompt",
        generator_prompt,
        "--merge-strategy",
        merge_strategy,
    ]


def _run_agent_main(argv: list[str], output_queue: multiprocessing.Queue) -> None:
    import traceback
    from llm30.pipeline.QAagent import QAagent_merge

    class QueueWriter:
        def __init__(self, queue: multiprocessing.Queue) -> None:
            self.queue = queue

        def write(self, data: str) -> None:
            if data:
                self.queue.put(data)

        def flush(self) -> None:
            return None

    sys.stdout = QueueWriter(output_queue)
    sys.stderr = QueueWriter(output_queue)

    try:
        exit_code = QAagent_merge.main(argv)
        if exit_code is None:
            exit_code = 0
    except SystemExit as exc:
        exit_code = exc.code if isinstance(exc.code, int) else 1
    except Exception:
        output_queue.put(traceback.format_exc())
        exit_code = 1

    raise SystemExit(exit_code)


def run_agent_main(argv: list[str], timeout_seconds: int = 500) -> None:
    attempt = 0
    while True:
        attempt += 1
        print(f"Starting attempt {attempt}...", flush=True)
        output_queue: multiprocessing.Queue = multiprocessing.Queue()
        process = multiprocessing.Process(
            target=_run_agent_main,
            args=(argv, output_queue),
        )
        process.start()

        last_output = time.monotonic()

        while True:
            try:
                chunk = output_queue.get(timeout=1)
            except queue_module.Empty:
                chunk = None

            if chunk:
                last_output = time.monotonic()
                print(chunk, end="", flush=True)

            if not process.is_alive():
                process.join()
                while True:
                    try:
                        chunk = output_queue.get_nowait()
                    except queue_module.Empty:
                        break
                    if chunk:
                        print(chunk, end="", flush=True)
                exit_code = process.exitcode or 0
                if exit_code == 0:
                    return
                raise RuntimeError(f"QAagent merge exited with code {exit_code}")

            if time.monotonic() - last_output > timeout_seconds:
                print(
                    f"No output for {timeout_seconds} seconds. Restarting run.",
                    flush=True,
                )
                process.terminate()
                process.join(timeout=10)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=5)
                break


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Run QAagent merge sequentially and aggregate summary stats into CSVs."
    )
    parser.add_argument("--runs", type=int, default=10, help="Number of sequential runs.")
    parser.add_argument("--dataset", default="humaneval", help="Dataset to use.")
    parser.add_argument("--model", default="nvidia/nemotron-3-nano-30b-a3b", help="Model name.")
    parser.add_argument("--max-tasks", type=int, default=20, help="Maximum tasks per run.")
    parser.add_argument("--max-workers", type=int, default=5, help="Workers per run.")
    parser.add_argument("--output-dir", default="logs", help="Directory for the CSV output.")
    parser.add_argument(
        "--predefine-name",
        default=None,
        help="Base name for output CSVs (suffixes _<prompt>_<strategy>.csv are added).",
    )
    args = parser.parse_args(argv)

    if args.runs <= 0:
        raise ValueError("runs must be positive.")

    logs_root = Path("logs")
    logs_root.mkdir(parents=True, exist_ok=True)

    if args.predefine_name:
        base_name = sanitize_name(args.predefine_name)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dataset_name = sanitize_name(args.dataset)
        model_name = sanitize_name(args.model)
        base_name = f"{timestamp}_qaagen_merge_{dataset_name}_{model_name}"

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    generator_prompts = ("default", "original")
    merge_strategies = ("accuracy", "concat")
    # merge_strategies = ("concat", "concat-enhanced", "llm", "accuracy")
    # merge_strategies = ["accuracy"]

    for generator_prompt in generator_prompts:
        for merge_strategy in merge_strategies:
            argv = build_argv(args, generator_prompt, merge_strategy)
            rows: list[dict[str, str | int | float]] = []

            for run_idx in range(1, args.runs + 1):
                before_logs = list_log_dirs(logs_root)
                print(
                    f"[{generator_prompt}/{merge_strategy}] Run {run_idx}/{args.runs}: "
                    f"QAagent_merge.main {' '.join(argv)}",
                    flush=True,
                )
                run_agent_main(argv)

                after_logs = list_log_dirs(logs_root)
                new_logs = sorted(after_logs - before_logs, key=lambda path: path.stat().st_mtime)
                if new_logs:
                    log_dir = new_logs[-1]
                else:
                    all_logs = sorted(after_logs, key=lambda path: path.stat().st_mtime)
                    if not all_logs:
                        raise RuntimeError("No QAagent log directories found after run.")
                    log_dir = all_logs[-1]

                summary_path = log_dir / "summary.txt"
                if not summary_path.exists():
                    raise FileNotFoundError(f"Missing summary file: {summary_path}")

                stats = parse_summary(summary_path)
                rows.append(
                    {
                        "run": run_idx,
                        "log_dir": str(log_dir),
                        **stats,
                    }
                )

                # Print summary after each run
                print(f"  → Run {run_idx} complete: "
                      f"Accuracy={stats['accuracy']:.2f}%, "
                      f"Coverage={stats['first_five_coverage']:.2f}%→{stats['coverage']:.2f}%, "
                      f"Tokens={stats['input_tokens']}+{stats['output_tokens']}")

            avg_accuracy = sum(row["accuracy"] for row in rows) / len(rows)
            avg_first_five = sum(row["first_five_coverage"] for row in rows) / len(rows)
            avg_coverage = sum(row["coverage"] for row in rows) / len(rows)
            sum_input_tokens = sum(row["input_tokens"] for row in rows)
            sum_output_tokens = sum(row["output_tokens"] for row in rows)

            rows.append(
                {
                    "run": "aggregate",
                    "log_dir": "",
                    "accuracy": avg_accuracy,
                    "first_five_coverage": avg_first_five,
                    "coverage": avg_coverage,
                    "input_tokens": sum_input_tokens,
                    "output_tokens": sum_output_tokens,
                }
            )

            output_path = output_dir / f"{base_name}_{generator_prompt}_{merge_strategy}.csv"

            fieldnames = [
                "run",
                "log_dir",
                "accuracy",
                "first_five_coverage",
                "coverage",
                "input_tokens",
                "output_tokens",
            ]
            with output_path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)

            # Print summary for this configuration
            print(f"\n{'=' * 60}")
            print(f"[{generator_prompt}/{merge_strategy}] Configuration Complete - Summary of {args.runs} runs:")
            print(f"{'=' * 60}")
            print(f"Average Accuracy:          {avg_accuracy:.2f}%")
            print(f"Average First-Five Cov:    {avg_first_five:.2f}%")
            print(f"Average Total Coverage:    {avg_coverage:.2f}%")
            print(f"Total Input Tokens:        {sum_input_tokens:,}")
            print(f"Total Output Tokens:       {sum_output_tokens:,}")
            print(f"CSV saved to: {output_path}")
            print(f"{'=' * 60}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
