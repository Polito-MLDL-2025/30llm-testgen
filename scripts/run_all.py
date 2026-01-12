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
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def print_banner(title: str, char: str = "=") -> None:
    """Print a formatted banner."""
    print(f"\n{char * 80}")
    print(f"{title:^80}")
    print(f"{char * 80}\n")


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
    
    # Build command
    command = [
        sys.executable,
        str(script_path),
        "--runs", str(args.runs),
        "--dataset", args.dataset,
        "--model", args.model,
        "--max-tasks", str(args.max_tasks),
        "--max-workers", str(args.max_workers),
        "--output-dir", args.output_dir,
    ]
    
    if args.predefine_name:
        # Add timestamp prefix to distinguish between different run_all executions
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        predefined = f"{timestamp}_{args.predefine_name}_{script_name.replace('.py', '')}"
        command.extend(["--predefine-name", predefined])
    
    print_banner(f"[{script_number}/{total_scripts}] Running: {script_name}", "=")
    print(f"Command: {' '.join(command)}")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    start_time = datetime.now()
    
    try:
        result = subprocess.run(command, check=True)
        duration = datetime.now() - start_time
        
        print_banner(f"✅ {script_name} completed successfully!", "-")
        print(f"Duration: {duration}")
        print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        return True
        
    except subprocess.CalledProcessError as e:
        duration = datetime.now() - start_time
        
        print_banner(f"❌ {script_name} failed with error!", "-")
        print(f"Error code: {e.returncode}")
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
  # Run with default settings (10 runs per config, 20 tasks, 6 workers)
  python scripts/run_all.py
  
  # Custom configuration
  python scripts/run_all.py --runs 5 --max-tasks 10 --max-workers 4
  
  # With predefined output name
  python scripts/run_all.py --runs 3 --predefine-name experiment_batch_1
  
  # Different model
  python scripts/run_all.py --model gpt-4o --max-tasks 50
        """
    )
    
    parser.add_argument(
        "--runs",
        type=int,
        default=10,
        help="Number of sequential runs per configuration (default: 10)"
    )
    parser.add_argument(
        "--dataset",
        default="humaneval",
        help="Dataset to use (default: humaneval)"
    )
    parser.add_argument(
        "--model",
        default="nvidia/nemotron-3-nano-30b-a3b",
        help="Model name (default: nvidia/nemotron-3-nano-30b-a3b)"
    )
    parser.add_argument(
        "--max-tasks",
        type=int,
        default=20,
        help="Maximum tasks per run (default: 20)"
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=5,
        help="Workers per run (default: 5)"
    )
    parser.add_argument(
        "--output-dir",
        default="logs",
        help="Directory for CSV outputs (default: logs)"
    )
    parser.add_argument(
        "--predefine-name",
        default=None,
        help="Base name for output files (timestamp and script name will be prepended)"
    )
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
        ("qaagent", "run_qaagent_10x.py"),
        ("competitive", "run_qaagent_competitive_10x.py"),
        ("merge", "run_qaagent_merge_10x.py"),
        ("singleagent", "run_singleagent_10x.py"),
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
    print(f"Max tasks:     {args.max_tasks}")
    print(f"Max workers:   {args.max_workers}")
    print(f"Output dir:    {args.output_dir}")
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
    print("="*80 + "\n")
    
    # Return non-zero exit code if any script failed
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
