import argparse


def config_run_agent_parser(parser):
    parser.add_argument("--runs", type=int, default=10, help="Number of sequential runs.")
    parser.add_argument("--dataset", default="humaneval", help="Dataset to use.")
    parser.add_argument("--model", default="meta/llama3-8b-instruct", help="Model name.")
    parser.add_argument("--max-tasks", type=int, default=20, help="Maximum tasks per run.")
    parser.add_argument("--max-workers", type=int, default=4, help="Workers per run.")
    parser.add_argument("--output-dir", default="logs", help="Directory for the CSV output.")
    parser.add_argument(
        "--predefine-name",
        default=None,
        help="Base name for output CSVs (suffixes _default.csv/_original.csv are added).",
    )
    parser.add_argument(
        "--dataset-path",
        default=None,
        help="Path to the dataset file (e.g., humaneval.jsonl or mbpp.jsonl). if not specified, will use the default path for the chosen dataset."
    )
    return parser


def build_argv_agent(args: argparse.Namespace, generator_prompt: str) -> list[str]:
    argv = [
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
    ]
    if args.dataset_path:
        argv.extend(["--dataset-path", args.dataset_path])
    return argv
