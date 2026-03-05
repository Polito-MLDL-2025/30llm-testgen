from pathlib import Path


def infer_tasks_evaluated(summary_path: Path, values: dict[str, str]) -> int:
    """Read tasks evaluated from summary or difficulty files for backward compatibility."""
    if "tasks evaluated" in values:
        return int(values["tasks evaluated"])

    difficulty_folder = summary_path.parent / "difficulty_summaries"
    if not difficulty_folder.exists():
        return 0

    total_tasks = 0
    for difficulty_file in difficulty_folder.glob("*.txt"):
        if difficulty_file.name in {"all_difficulties.txt", "problem_lists.txt"}:
            continue
        with difficulty_file.open() as handle:
            for line in handle:
                if ":" not in line:
                    continue
                key, _, value = line.partition(":")
                if key.strip().lower() != "tasks evaluated":
                    continue
                try:
                    total_tasks += int(value.strip())
                except ValueError:
                    pass
                break

    return total_tasks

def compute_avg_tokens_per_task(input_tokens: int, output_tokens: int, tasks_evaluated: int) -> float:
    if tasks_evaluated <= 0:
        return 0.0
    return (input_tokens + output_tokens) / tasks_evaluated