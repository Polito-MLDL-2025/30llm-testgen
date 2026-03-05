import os
import logging
from datetime import datetime


def sanitize_problem_id(problem_id):
    """
    Sanitize problem ID for use in file/folder names.
    Replaces '/' with '_' to avoid filesystem issues.

    Examples:
        'HumanEval/0' -> 'HumanEval_0'
        'Mbpp/1' -> 'Mbpp_1'
    """
    return problem_id.replace('/', '_')


def write_tests_single_agent(log_folder, problem_id, tests):
    """Write generated tests to file for single agent approach."""
    safe_problem_id = sanitize_problem_id(problem_id)
    result_folder = os.path.join(log_folder, safe_problem_id)
    os.makedirs(result_folder, exist_ok=True)

    with open(os.path.join(result_folder, 'generated_tests.py'), 'w') as f:
        f.write(tests)


def create_log_folder(dataset=None, model=None):
    """
    Creates a timestamped folder for logs with dataset and model info.

    Args:
        dataset: Dataset name (e.g., 'humaneval', 'mbpp')
        model: Model name (e.g., 'gpt-4o')

    Returns:
        str: Path to created log folder
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Build folder name with context
    folder_parts = ['single_agent']
    if dataset:
        folder_parts.append(dataset)
    if model:
        # Sanitize model name for filesystem
        safe_model = model.replace('/', '_').replace(':', '_')
        folder_parts.append(safe_model)
    folder_parts.append(timestamp)

    folder_name = '-'.join(folder_parts)
    log_folder = os.path.join('logs', folder_name)
    os.makedirs(log_folder, exist_ok=True)
    return log_folder


def setup_logger(log_folder):
    """Sets up the logger to log into the timestamped folder."""
    logger = logging.getLogger('SingleAgentLogger')
    logger.setLevel(logging.INFO)

    if logger.handlers:
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()

    file_handler = logging.FileHandler(os.path.join(log_folder, 'pipeline.log'))
    file_handler.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    return logger


def log_results(problem_folder, first_five_coverage_report, total_coverage_report, test_results, logger, num_input_tokens, num_output_tokens):
    """Logs results and writes them to files."""
    with open(os.path.join(problem_folder, 'accuracy_report.txt'), 'w') as f:
        f.write(test_results)

    with open(os.path.join(problem_folder, 'coverage_first_five.txt'), 'w') as f:
        f.write(first_five_coverage_report)

    with open(os.path.join(problem_folder, 'coverage_total.txt'), 'w') as f:
        f.write(total_coverage_report)

    logger.info(f'Tokens - Input: {num_input_tokens}, Output: {num_output_tokens}')


def write_summary(log_folder, total_stats):
    """Write summary statistics to file."""
    evaluated = total_stats['evaluated']
    with open(os.path.join(log_folder, 'summary.txt'), 'w') as summary_file:
        summary_file.write(
            f"Tasks evaluated: {evaluated}\n"
            f"Accuracy: {total_stats['accuracy'] / evaluated}\n"
            f"First five coverage: {total_stats['first_five_coverage'] / evaluated}\n"
            f"Coverage: {total_stats['coverage'] / evaluated}\n"
            f"Input tokens: {total_stats['input_tokens']}\nOutput tokens: {total_stats['output_tokens']}\n")


def init_difficulty_stats():
    """Initialize per-difficulty statistics dictionaries."""
    difficulties = ["Easy / Basic", "Medium / Intermediate", "Medium-Hard / Complex", "Hard / Advanced"]
    return {
        difficulty: {
            'evaluated': 0,
            'accuracy': 0.0,
            'first_five_coverage': 0.0,
            'coverage': 0.0,
            'input_tokens': 0,
            'output_tokens': 0
        }
        for difficulty in difficulties
    }


def write_difficulty_summaries(log_folder, difficulty_stats, difficulty_mapping=None):
    """Write per-difficulty summary statistics to files in a subfolder."""
    difficulty_folder = os.path.join(log_folder, 'difficulty_summaries')
    os.makedirs(difficulty_folder, exist_ok=True)
    
    # Write individual difficulty summaries
    for difficulty, stats in difficulty_stats.items():
        if stats['evaluated'] == 0:
            continue
        
        safe_filename = difficulty.replace(' / ', '_').replace(' ', '_').lower() + '.txt'
        with open(os.path.join(difficulty_folder, safe_filename), 'w') as f:
            f.write(
                f"Difficulty: {difficulty}\n"
                f"Tasks evaluated: {stats['evaluated']}\n"
                f"Accuracy: {stats['accuracy'] / stats['evaluated']}\n"
                f"First five coverage: {stats['first_five_coverage'] / stats['evaluated']}\n"
                f"Coverage: {stats['coverage'] / stats['evaluated']}\n"
                f"Input tokens: {stats['input_tokens']}\n"
                f"Output tokens: {stats['output_tokens']}\n"
            )
    
    # Write aggregated summary
    with open(os.path.join(difficulty_folder, 'all_difficulties.txt'), 'w') as f:
        for difficulty, stats in difficulty_stats.items():
            if stats['evaluated'] == 0:
                continue
            f.write(
                f"\n{difficulty}:\n"
                f"  Tasks evaluated: {stats['evaluated']}\n"
                f"  Accuracy: {stats['accuracy'] / stats['evaluated']:.2f}\n"
                f"  First five coverage: {stats['first_five_coverage'] / stats['evaluated']:.2f}\n"
                f"  Coverage: {stats['coverage'] / stats['evaluated']:.2f}\n"
                f"  Input tokens: {stats['input_tokens']}\n"
                f"  Output tokens: {stats['output_tokens']}\n"
            )
    
    # Write problem lists per difficulty
    if difficulty_mapping:
        with open(os.path.join(difficulty_folder, 'problem_lists.txt'), 'w') as f:
            f.write("Problem Lists by Difficulty\n")
            f.write("="*60 + "\n")
            for difficulty in sorted(difficulty_stats.keys()):
                problems = sorted([task_id for task_id, diff in difficulty_mapping.items() if diff == difficulty])
                if problems:
                    f.write(f"\n{difficulty} ({len(problems)} problems):\n")
                    for problem in problems:
                        f.write(f"  - {problem}\n")


def write_details(log_folder, result):
    """Write detailed results for each problem to file."""
    problem_id, cur_num_input_tokens, cur_num_output_tokens, cur_first_five_coverage, cur_total_coverage, cur_accuracy = result
    with open(os.path.join(log_folder, 'details.txt'), 'a') as details_file:
        details_file.write(
            f"Problem ID: {problem_id}\nAccuracy: {cur_accuracy}\n"
            f"First five coverage: {cur_first_five_coverage}\n"
            f"Coverage: {cur_total_coverage}\n"
            f"Input tokens: {cur_num_input_tokens}\nOutput tokens: {cur_num_output_tokens}\n")
