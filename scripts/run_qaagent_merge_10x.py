#!/usr/bin/env python3
import argparse
import csv
import multiprocessing
import queue as queue_module
import sys
import time
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    # Ensure local imports work when running via "python scripts/...".
    sys.path.insert(0, str(REPO_ROOT))

from scripts.utils.get_parser import config_run_agent_parser, build_argv_agent
from scripts.utils.run_cache import build_cache_path, load_run_cache, save_run_cache

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


def run_agent_main(argv: list[str], timeout_seconds: int = 600) -> None:
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
    parser = config_run_agent_parser(parser)
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
    args_signature = {
        "dataset": args.dataset,
        "model": args.model,
        "runs": args.runs,
        "max_tasks": args.max_tasks,
        "max_workers": args.max_workers,
        "dataset_path": args.dataset_path,
        "predefine_name": args.predefine_name,
    }

    generator_prompts = ("default", "original")
    # generator_prompts = [ "original","default"]
    merge_strategies = ("accuracy", "concat", "llm", "llm_multi_steps")
    # merge_strategies = ("accuracy",  "llm_multi_steps")
    # merge_strategies = ["llm"]

    for generator_prompt in generator_prompts:
        for merge_strategy in merge_strategies:
            argv = build_argv_agent(args, generator_prompt)
            argv += ["--merge-strategy", merge_strategy]
            config_tag = f"{generator_prompt}_{merge_strategy}"
            cache_path = build_cache_path(
                output_dir=output_dir,
                script_id="run_qaagent_merge_10x",
                config_tag=config_tag,
                args_signature=args_signature,
            )
            rows_by_run = {
                run_idx: row
                for run_idx, row in load_run_cache(cache_path).items()
                if 1 <= run_idx <= args.runs
            }
            rows: list[dict[str, str | int | float]] = []

            for run_idx in range(1, args.runs + 1):
                cached_row = rows_by_run.get(run_idx)
                if cached_row is not None:
                    rows.append(cached_row)
                    print(
                        f"[{generator_prompt}/{merge_strategy}] Run {run_idx}/{args.runs}: using cached result",
                        flush=True,
                    )
                    print(f"  → Run {run_idx} cached: "
                          f"Accuracy={float(cached_row['accuracy']):.2f}%, "
                          f"Coverage={float(cached_row['first_five_coverage']):.2f}%→{float(cached_row['coverage']):.2f}%, "
                          f"Tokens={int(cached_row['input_tokens'])}+{int(cached_row['output_tokens'])}")
                    continue

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
                row = {
                    "run": run_idx,
                    "log_dir": str(log_dir),
                    **stats,
                }
                rows_by_run[run_idx] = row
                save_run_cache(cache_path, rows_by_run)
                rows.append(row)

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
