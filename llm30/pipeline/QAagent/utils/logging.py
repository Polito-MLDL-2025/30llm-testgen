import os
import logging
from datetime import datetime


def write_plan_and_tests_qa(log_folder, problem_id, pseudocode, tests):
    # Write results to files
    result_folder = os.path.join(log_folder, f'problem_{problem_id}')
    os.makedirs(result_folder, exist_ok=True)

    with open(os.path.join(result_folder, 'pseudocode.txt'), 'w') as f:
        f.write(pseudocode)

    with open(os.path.join(result_folder, 'generated_tests.txt'), 'w') as f:
        f.write(tests)

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


def create_log_folder(dataset=None, model=None,prefix='QAagent'):
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
    folder_parts = [prefix]
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
    logger = logging.getLogger('MultiAgentLogger')
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
            f"Accuracy: {total_stats['accuracy'] / evaluated}\n"
            f"First five coverage: {total_stats['first_five_coverage'] / evaluated}\n"
            f"Coverage: {total_stats['coverage'] / evaluated}\n"
            f"Input tokens: {total_stats['input_tokens']}\nOutput tokens: {total_stats['output_tokens']}\n")


def write_details(log_folder, result):
    """Write detailed results for each problem to file."""
    problem_id, cur_num_input_tokens, cur_num_output_tokens, cur_first_five_coverage, cur_total_coverage, cur_accuracy = result
    with open(os.path.join(log_folder, 'details.txt'), 'a') as details_file:
        details_file.write(
            f"Problem ID: {problem_id}\nAccuracy: {cur_accuracy}\n"
            f"First five coverage: {cur_first_five_coverage}\n"
            f"Coverage: {cur_total_coverage}\n"
            f"Input tokens: {cur_num_input_tokens}\nOutput tokens: {cur_num_output_tokens}\n")
