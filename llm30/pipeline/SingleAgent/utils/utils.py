import json
import argparse
from typing import Dict, Iterable


def read_problems(filename: str) -> list:
    """Read problems from a JSONL file."""
    return list(stream_jsonl(filename))


def stream_jsonl(filename: str) -> Iterable[Dict]:
    """Parses each jsonl line from a .jsonl file and yields it as a dictionary."""
    with open(filename, "r") as fp:
        for line in fp:
            if any(not x.isspace() for x in line):
                yield json.loads(line)


def add_canonical_solution(problem_name):
    """Combine problem prompt with canonical solution."""
    return f"""{problem_name["prompt"]}
{problem_name["canonical_solution"]}
"""


def parse_args(argv=None):
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Single Agent Test Case Generation - Specify dataset and model.")

    parser.add_argument(
        "--dataset",
        choices=["humaneval", "mbpp"],
        default="humaneval",
        help="Choose the dataset to use (humaneval or mbpp)."
    )

    parser.add_argument(
        "--model",
        default="meta/llama3-8b-instruct",
        help="Specify the model to use."
    )

    parser.add_argument(
        "--max-tasks",
        type=int,
        default=None,
        help="Maximum number of tasks to process (default: all)."
    )

    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Number of worker threads to use (default: 4)."
    )

    parser.add_argument(
        "--generator-prompt",
        choices=["default", "original", "zero_shot"],
        default="default",
        help="Choose the generator prompt to use (default, original, or zero_shot)."
    )
    parser.add_argument(
        "--dataset-path",
        default=None,
        help="Path to the dataset file (e.g., humaneval.jsonl or mbpp.jsonl). if not specified, will use the default path for the chosen dataset."
    )

    return parser.parse_args(argv)


def update_total_stats(result, total_stats):
    """Update total statistics with results from a single problem."""
    (
        problem_id,
        cur_num_input_tokens,
        cur_num_output_tokens,
        cur_first_five_coverage,
        cur_total_coverage,
        cur_accuracy,
        *extra_metrics,
    ) = result
    cur_first_five_branch = extra_metrics[0] if len(extra_metrics) > 0 else 0.0
    cur_total_branch = extra_metrics[1] if len(extra_metrics) > 1 else 0.0
    cur_first_five_line = extra_metrics[2] if len(extra_metrics) > 2 else cur_first_five_coverage
    cur_total_line = extra_metrics[3] if len(extra_metrics) > 3 else cur_total_coverage
    total_stats['input_tokens'] += cur_num_input_tokens
    total_stats['output_tokens'] += cur_num_output_tokens
    total_stats['first_five_coverage'] += cur_first_five_coverage
    total_stats['coverage'] += cur_total_coverage
    if 'first_five_line_coverage' in total_stats:
        total_stats['first_five_line_coverage'] += cur_first_five_line
    if 'line_coverage' in total_stats:
        total_stats['line_coverage'] += cur_total_line
    if 'first_five_branch_coverage' in total_stats:
        total_stats['first_five_branch_coverage'] += cur_first_five_branch
    if 'branch_coverage' in total_stats:
        total_stats['branch_coverage'] += cur_total_branch
    total_stats['accuracy'] += cur_accuracy
    total_stats['evaluated'] += 1
