#!/usr/bin/env python3
"""
Run all experiment scripts sequentially.

This script orchestrates running all the 10x experiment scripts in sequence:
1. run_qaagent_10x.py
2. run_qaagent_competitive_10x.py
3. run_qaagent_merge_10x.py
4. run_singleagent_10x.py

Each script runs multiple configurations with multiple runs per configuration.
"""
import argparse
import csv
import importlib.util
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    # Ensure local imports work when running via "python scripts/...".
    sys.path.insert(0, str(REPO_ROOT))

from scripts.utils.get_parser import config_run_agent_parser
from scripts.utils.process_cleanup import kill_descendant_processes_sigkill


def print_banner(title: str, char: str = "=") -> None:
    """Print a formatted banner."""
    print(f"\n{char * 80}")
    print(f"{title:^80}")
    print(f"{char * 80}\n")


def list_csv_files(output_dir: Path) -> set[Path]:
    if not output_dir.exists():
        return set()
    return {path.resolve() for path in output_dir.glob("*.csv") if path.is_file()}


def safe_float(value: str | None) -> float | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def print_token_avg_per_result(csv_path: Path) -> None:
    with csv_path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    if not rows:
        return

    printed_any = False
    for row in rows:
        input_tokens = safe_float(row.get("input_tokens"))
        output_tokens = safe_float(row.get("output_tokens"))
        tasks_evaluated = safe_float(row.get("tasks_evaluated"))
        avg_tokens_per_task = safe_float(row.get("avg_tokens_per_task"))
        run_label = row.get("run", "?")

        if input_tokens is None or output_tokens is None:
            continue

        if avg_tokens_per_task is None:
            if tasks_evaluated is None or tasks_evaluated <= 0:
                continue
            avg_tokens_per_task = (input_tokens + output_tokens) / tasks_evaluated

        print(f"    {csv_path.name} | run={run_label}: AvgTok/Task={avg_tokens_per_task:.2f}")
        printed_any = True

    if printed_any:
        print()


def run_script(
        script_name: str,
        args: argparse.Namespace,
        script_number: int,
        total_scripts: int
) -> bool:
    """
    Run a single experiment script.
    
    Returns:
        bool: True if successful, False otherwise
    """
    script_path = Path("scripts") / script_name

    if not script_path.exists():
        print(f"❌ Script not found: {script_path}")
        return False

    # Build argv for script main
    argv = [
        "--runs", str(args.runs),
        "--dataset", args.dataset,
        "--model", args.model,
        "--max-tasks", str(args.max_tasks),
        "--max-workers", str(args.max_workers),
        "--output-dir", args.output_dir,
    ]
    if args.dataset_path:
        argv.extend(["--dataset-path", str(args.dataset_path)])
    if args.qaagent_model:
        argv.extend(["--qaagent-model", args.qaagent_model])
    if args.qaagent_plan_model:
        argv.extend(["--qaagent-plan-model", args.qaagent_plan_model])
    if args.qaagent_test_model:
        argv.extend(["--qaagent-test-model", args.qaagent_test_model])
    if args.qaagent_judge_model:
        argv.extend(["--qaagent-judge-model", args.qaagent_judge_model])
    if args.qaagent_merge_model:
        argv.extend(["--qaagent-merge-model", args.qaagent_merge_model])

    if args.predefine_name:
        # Add timestamp prefix to distinguish between different run_all executions
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        predefined = f"{timestamp}_{args.predefine_name}_{script_name.replace('.py', '')}"
        argv.extend(["--predefine-name", predefined])

    print_banner(f"[{script_number}/{total_scripts}] Running: {script_name}", "=")
    print(f"Args: {' '.join(argv)}")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    start_time = datetime.now()
    output_dir = Path(args.output_dir)
    csv_before = list_csv_files(output_dir)

    try:
        module_name = f"_run_{script_path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, script_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to load module from {script_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        exit_code = module.main(argv)
        if exit_code:
            raise RuntimeError(f"{script_name} exited with code {exit_code}")

        duration = datetime.now() - start_time
        print_banner(f"✅ {script_name} completed successfully!", "-")
        print(f"Duration: {duration}")
        print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        csv_after = list_csv_files(output_dir)
        new_csv_files = sorted(csv_after - csv_before)
        if new_csv_files:
            print("  AvgTok/Task per result:")
            for csv_file in new_csv_files:
                try:
                    print_token_avg_per_result(csv_file)
                except Exception as e:
                    print(f"    Failed to parse {csv_file.name}: {e}")
        return True

    except Exception as e:
        duration = datetime.now() - start_time
        print_banner(f"❌ {script_name} failed with error!", "-")
        print(f"Error: {e}")
        print(f"Duration: {duration}")
        print(f"Failed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        return False

    except KeyboardInterrupt:
        duration = datetime.now() - start_time

        print_banner(f"⚠️  {script_name} interrupted by user!", "-")
        print(f"Duration: {duration}")
        print(f"Interrupted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        raise


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run all experiment scripts sequentially.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Scripts executed in order:
  1. run_qaagent_10x.py             - Standard QA Agent (default + original prompts)
  2. run_qaagent_competitive_10x.py - Competitive QA Agent (default + original prompts)
  3. run_qaagent_merge_10x.py       - QA Agent with merge strategies (2 prompts × 3 strategies)
  4. run_singleagent_10x.py         - Single Agent (default + original prompts)

Example usage:
  # Run with default settings
  python scripts/run_all.py
  
  # HumanEval curated subset (20 selected problems, 10 runs)
  python scripts/run_all.py --dataset humaneval --dataset-path llm30/pipeline/datasets/humaneval/problems_selected.jsonl --runs 10 --max-tasks 20 --max-workers 4

  # HumanEval full dataset (164 problems, single run)
  python scripts/run_all.py --dataset humaneval --dataset-path llm30/pipeline/datasets/humaneval/problems_original.jsonl --runs 1 --max-tasks 164 --max-workers 4

  # Custom configuration
  python scripts/run_all.py --runs 5 --max-tasks 10 --max-workers 4
  
  # With predefined output name
  python scripts/run_all.py --runs 3 --predefine-name experiment_batch_1
  
  # Different model
  python scripts/run_all.py --model gpt-4o --max-tasks 50
        """
    )
    parser = config_run_agent_parser(parser)

    parser.add_argument(
        "--skip",
        nargs="+",
        choices=["qaagent", "competitive", "merge", "singleagent"],
        default=[],
        help="Skip specific scripts (e.g., --skip merge singleagent)"
    )

    args = parser.parse_args()

    # Define all scripts to run
    all_scripts = [
        ("singleagent", "run_singleagent_10x.py"),
        ("qaagent", "run_qaagent_10x.py"),
        ("competitive", "run_qaagent_competitive_10x.py"),
        ("merge", "run_qaagent_merge_10x.py"),

    ]

    # Filter out skipped scripts
    scripts_to_run = [
        (name, script) for name, script in all_scripts
        if name not in args.skip
    ]

    if not scripts_to_run:
        print("❌ All scripts are skipped. Nothing to run!")
        return 1

    # Print configuration
    print_banner("RUN ALL EXPERIMENTS - CONFIGURATION", "=")
    print(f"Timestamp:     {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Runs per config: {args.runs}")
    print(f"Dataset:       {args.dataset}")
    print(f"Model:         {args.model}")
    if args.qaagent_model:
        print(f"QAAGENT_MODEL: {args.qaagent_model}")
    if args.qaagent_plan_model:
        print(f"QAAGENT_PLAN_MODEL: {args.qaagent_plan_model}")
    if args.qaagent_test_model:
        print(f"QAAGENT_TEST_MODEL: {args.qaagent_test_model}")
    if args.qaagent_judge_model:
        print(f"QAAGENT_JUDGE_MODEL: {args.qaagent_judge_model}")
    if args.qaagent_merge_model:
        print(f"QAAGENT_MERGE_MODEL: {args.qaagent_merge_model}")
    print(f"Max tasks:     {args.max_tasks}")
    print(f"Max workers:   {args.max_workers}")
    print(f"Output dir:    {args.output_dir}")
    print(f"dataset path:   {args.dataset_path if args.dataset_path else 'default'}")
    if args.predefine_name:
        print(f"Predefined name: {args.predefine_name}")
    if args.skip:
        print(f"Skipped:       {', '.join(args.skip)}")
    print(f"\nScripts to run: {len(scripts_to_run)}")
    for i, (name, script) in enumerate(scripts_to_run, 1):
        print(f"  {i}. {script}")

    # Overall timing
    overall_start = datetime.now()
    results = {}

    # Run each script
    try:
        for i, (name, script) in enumerate(scripts_to_run, 1):
            success = run_script(script, args, i, len(scripts_to_run))
            results[script] = success

            if not success and not args.skip:
                print("\n⚠️  Script failed. Continuing with next script...")

    except KeyboardInterrupt:
        print("\n\n⚠️  Run interrupted by user!")
        kill_descendant_processes_sigkill()
        overall_duration = datetime.now() - overall_start
        print(f"Total duration before interruption: {overall_duration}")
        return 130  # Standard exit code for SIGINT

    # Final summary
    overall_duration = datetime.now() - overall_start

    print_banner("FINAL SUMMARY - ALL EXPERIMENTS", "=")
    print(f"Overall duration: {overall_duration}")
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    successful = sum(1 for success in results.values() if success)
    failed = len(results) - successful

    print(f"Results:")
    print(f"  ✅ Successful: {successful}/{len(results)}")
    print(f"  ❌ Failed:     {failed}/{len(results)}\n")

    print("Script Status:")
    for script, success in results.items():
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"  {status}: {script}")

    print(f"\nAll outputs saved to: {args.output_dir}/")
    print("=" * 80 + "\n")

    # Return non-zero exit code if any script failed
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
