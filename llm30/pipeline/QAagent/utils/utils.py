import json
import argparse
from typing import Dict, Iterable


def read_problems(filename: str) -> list:
    return list(stream_jsonl(filename))


def stream_jsonl(filename: str) -> Iterable[Dict]:
    # Parses each jsonl line from a .jsonl file and yields it as a dictionary.
    with open(filename, "r") as fp:
        for line in fp:
            if any(not x.isspace() for x in line):
                yield json.loads(line)


def add_plan(problem_name, pseudocode):
    return f"""{problem_name["prompt"]}

{pseudocode}
"""


def add_canonical_solution(problem_name):
    return f"""{problem_name["prompt"]}
{problem_name["canonical_solution"]}
"""


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Specify dataset and model.")

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
        "--merge-strategy",
        choices=["concat", "concat-enhanced", "llm", "llm_multi_steps", "accuracy"],
        default="concat",
        help=(
            "Strategy to merge test sets: 'concat' (concatenate all, default), "
            "'concat-enhanced' (concat with syntax validation and deduplication), "
            "'llm' (use one LLM call to merge), "
            "'llm_multi_steps' (two-step LLM filter + aggregate), or "
            "'accuracy' (filter to tests that pass the canonical solution)."
        )
    )
    parser.add_argument(
        "--generator-prompt",
        choices=["default", "original"],
        default="default",
        help=(
            "Test generator prompt to use: 'default' uses the standard prompt, "
            "'original' uses the original humaneval prompt when available."
        )
    )
    parser.add_argument(
        "--judge-strategy",
        choices=["scorer", "selector"],
        default="selector",
        help=(
            "Judge strategy to use: 'scorer' judges each candidate independently, "
            "'selector' (default) judges all candidates together in a single call."
        )
    )
    parser.add_argument(
        "--dataset-path",
        default=None,
        help="Path to the dataset file (e.g., humaneval.jsonl or mbpp.jsonl). if not specified, will use the default path for the chosen dataset."
    )
    parser.add_argument(
        "--debug-mode",
        action="store_true",
        help="Enable debug logging and write detailed merger outputs to log files."
    )
    parser.add_argument(
        "--retry-sleep-seconds",
        type=int,
        default=60,
        help="Seconds to sleep between retry attempts after a failed/timed-out run."
    )
    return parser.parse_args(argv)


def update_total_stats(result, total_stats):
    problem_id, cur_num_input_tokens, cur_num_output_tokens, cur_first_five_coverage, cur_total_coverage, cur_accuracy = result
    total_stats['input_tokens'] += cur_num_input_tokens
    total_stats['output_tokens'] += cur_num_output_tokens
    total_stats['first_five_coverage'] += cur_first_five_coverage
    total_stats['coverage'] += cur_total_coverage
    total_stats['accuracy'] += cur_accuracy
    total_stats['evaluated'] += 1
