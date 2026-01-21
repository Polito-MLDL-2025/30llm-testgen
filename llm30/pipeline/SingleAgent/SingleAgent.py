import os
import sys
import logging
import multiprocessing
import queue as queue_module
import time
import concurrent.futures

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if PROJECT_ROOT not in sys.path:
    # Allow running this file directly from any working directory.
    sys.path.insert(0, PROJECT_ROOT)

from llm30.pipeline.SingleAgent.utils.utils import read_problems, add_canonical_solution, parse_args, update_total_stats
from llm30.pipeline.SingleAgent.utils.logging import (
    write_tests_single_agent, create_log_folder, setup_logger,
    log_results, write_summary, write_details, sanitize_problem_id
)
from llm30.pipeline.SingleAgent.agents.test_generator_agent import generate_test_code
from llm30.pipeline.SingleAgent.utils.coverage import get_coverage, extract_coverage_percentages
from llm30.pipeline.SingleAgent.utils.accuracy import get_accuracy


def _ensure_stream_handler(logger):
    if not any(
        isinstance(handler, logging.StreamHandler) and handler.stream is sys.stdout
        for handler in logger.handlers
    ):
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)


def _single_agent_worker(
    result_queue,
    output_queue,
    problem,
    dataset,
    model,
    test_generator_prompt,
    log_folder,
):
    class QueueWriter:
        def __init__(self, queue):
            self.queue = queue

        def write(self, data):
            if data:
                self.queue.put(data)

        def flush(self):
            return None

    sys.stdout = QueueWriter(output_queue)
    sys.stderr = QueueWriter(output_queue)

    logger = setup_logger(log_folder)
    _ensure_stream_handler(logger)
    try:
        result = singleAgent(problem, dataset, model, test_generator_prompt, log_folder, logger)
        result_queue.put(("ok", result))
    except Exception as exc:
        logger.exception("Worker error for problem %s: %s", problem.get("task_id"), exc)
        result_queue.put(("error", str(exc)))


def _run_single_agent_with_timeout(
    problem,
    dataset,
    model,
    test_generator_prompt,
    log_folder,
    logger,
    timeout_seconds=180,
    max_attempts=3,
):
    problem_id = problem.get("task_id")
    ctx = multiprocessing.get_context("spawn")
    for attempt in range(1, max_attempts + 1):
        result_queue = ctx.Queue()
        output_queue = ctx.Queue()
        process = ctx.Process(
            target=_single_agent_worker,
            args=(
                result_queue,
                output_queue,
                problem,
                dataset,
                model,
                test_generator_prompt,
                log_folder,
            ),
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
                try:
                    status, payload = result_queue.get_nowait()
                except queue_module.Empty:
                    logger.warning(
                        "Problem %s finished without result (attempt %s/%s). Retrying.",
                        problem_id,
                        attempt,
                        max_attempts,
                    )
                    break
                if status == "ok":
                    return payload
                logger.error(
                    "Problem %s failed (attempt %s/%s): %s",
                    problem_id,
                    attempt,
                    max_attempts,
                    payload,
                )
                break

            if time.monotonic() - last_output > timeout_seconds:
                logger.warning(
                    "Problem %s had no output for %ss (attempt %s/%s). Restarting.",
                    problem_id,
                    timeout_seconds,
                    attempt,
                    max_attempts,
                )
                process.terminate()
                process.join(timeout=10)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=5)
                break

    logger.error("Problem %s failed after %s attempts.", problem_id, max_attempts)
    return None


def singleAgent(problem_name, dataset, model_name, test_generator_prompt, log_folder, logger):
    """
    Single Agent pipeline for test case generation.
    Directly generates test cases from problem description without intermediate planning.

    This is a one-step approach (vs QAagent's two-step approach):
    - QAagent: Step 1: Generate plan → Step 2: Generate tests from plan
    - SingleAgent: Step 1: Generate tests directly from problem description

    Args:
        problem_name: Problem dictionary with prompt and task_id
        dataset: Dataset name (humaneval or mbpp)
        model_name: LLM model to use
        test_generator_prompt: Path to prompt template
        log_folder: Folder to save logs
        logger: Logger instance

    Returns:
        tuple: (first_five_coverage, total_coverage, accuracy, input_tokens, output_tokens)
    """
    problem_id = problem_name["task_id"]
    logger.info(f'Starting Single Agent test generation for problem ID {problem_id}')

    # Generate tests directly from problem description (single LLM call)
    try:
        generated_tests, num_input_tokens, num_output_tokens = generate_test_code(
            problem_name["prompt"],
            problem_id,
            test_generator_prompt,
            model_name,
            logger
        )
        logger.info(f'Generated {len(generated_tests.splitlines())} lines of tests. '
                   f'Tokens - Input: {num_input_tokens}, Output: {num_output_tokens}')
    except Exception as e:
        logger.error(f'Failed to generate tests for problem {problem_id}: {e}')
        return 0, 0, 0, 0, 0

    # Log generated tests
    write_tests_single_agent(log_folder, problem_id, generated_tests)

    # Prepare canonical solution (avoid repeated calculation)
    canonical_solution = (
        add_canonical_solution(problem_name) if dataset == "humaneval"
        else problem_name["canonical_solution"]
    )

    # Check the code coverage of the generated tests
    logger.info(f'Checking code coverage for problem ID {problem_id}')

    # Get coverage reports
    first_five_coverage_report, total_coverage_report = get_coverage(
        canonical_solution,
        generated_tests,
        problem_id,
        log_folder
    )

    # Calculate generated tests accuracy on the canonical solution
    safe_problem_id = sanitize_problem_id(problem_id)
    problem_folder = os.path.join(log_folder, safe_problem_id)
    accuracy, test_results = get_accuracy(
        canonical_solution,
        generated_tests,
        problem_folder,
        problem_id
    )

    # Extract and log test coverage
    # Note: Coverage files are in problem_{problem_id} folder (e.g., problem_HumanEval/0)
    coverage_folder = os.path.join(log_folder, f'problem_{problem_id}')
    first_five_coverage, total_coverage = extract_coverage_percentages(coverage_folder, problem_name)

    # Log results
    log_results(problem_folder, first_five_coverage_report, total_coverage_report, test_results, logger, num_input_tokens, num_output_tokens)

    return first_five_coverage, total_coverage, accuracy, num_input_tokens, num_output_tokens


def process_problem(problem, model, dataset, log_folder, test_generator_prompt, logger):
    """
    Process a single problem using the SingleAgent approach.

    Returns:
        tuple: (task_id, input_tokens, output_tokens, first_five_coverage, total_coverage, accuracy)
    """
    task_id = problem["task_id"]
    try:
        result = _run_single_agent_with_timeout(
            problem,
            dataset,
            model,
            test_generator_prompt,
            log_folder,
            logger,
        )
        if result is None:
            return task_id, 0, 0, 0.0, 0.0, 0.0
        first_five_coverage, total_coverage, accuracy, input_tokens, output_tokens = result
        return task_id, input_tokens, output_tokens, first_five_coverage, total_coverage, accuracy
    except Exception as e:
        logger.error(f'Error processing problem {task_id}: {e}')
        with open(os.path.join(log_folder, 'errors.txt'), 'a') as f:
            f.write(f'Error in problem ID {task_id}: {e}\n')
        return task_id, 0, 0, 0.0, 0.0, 0.0


def main(argv=None) -> int:
    args = parse_args(argv)

    # Setup
    model = args.model
    dataset = args.dataset
    log_folder = create_log_folder(dataset=dataset, model=model)
    logger = setup_logger(log_folder)

    print(f"\n{'='*60}")
    print(f"Single Agent Test Case Generation Pipeline")
    print(f"{'='*60}")
    print(f"Model: {model}")
    print(f"Dataset: {dataset}")
    print(f"Generator prompt: {args.generator_prompt}")
    print(f"Log folder: {log_folder}")
    print(f"Max workers: {args.max_workers}")

    pipeline_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    # Load prompts
    if args.dataset == "humaneval":
        if args.generator_prompt == "default":
            test_generator_prompt = os.path.join(pipeline_dir, "prompts", "single_agent", "single_agent_humaneval_prompt.txt")
        elif args.generator_prompt == "original":
            test_generator_prompt = os.path.join(pipeline_dir, "prompts", "single_agent", "single_agent_humaneval_prompt_original.txt")
        elif args.generator_prompt == "zero_shot":
            test_generator_prompt = os.path.join(pipeline_dir, "prompts", "single_agent", "single_agent_humaneval_prompt_zero_shot.txt")
        else:
            raise ValueError(f"Unknown generator prompt: {args.generator_prompt}")
    elif args.dataset == "mbpp":
        test_generator_prompt = os.path.join(pipeline_dir, "prompts", "single_agent", "single_agent_mbpp_prompt.txt")
    else:
        raise ValueError(f"Unknown dataset: {args.dataset}")

    # Load dataset
    dataset_map = {
        "humaneval": os.path.join(pipeline_dir, "datasets", "humaneval", "problems.jsonl"),
        "mbpp": os.path.join(pipeline_dir, "datasets", "mbpp", "problems.jsonl")
    }
    problems = read_problems(dataset_map[args.dataset])
    print(f"Loaded {len(problems)} problems from: {dataset_map[args.dataset]}")

    # Initialize statistics
    total_stats = {
        'input_tokens': 0,
        'output_tokens': 0,
        'first_five_coverage': 0.0,
        'coverage': 0.0,
        'accuracy': 0.0,
        'evaluated': 0
    }

    # Determine problem range
    start_index = 0
    dataset_limit = 164 if args.dataset == "humaneval" else 500
    end_index = min(dataset_limit, len(problems))
    if args.max_tasks is not None:
        if args.max_tasks < 0:
            raise ValueError("max_tasks must be non-negative.")
        end_index = min(end_index, start_index + args.max_tasks)
    if args.max_workers <= 0:
        raise ValueError("max_workers must be positive.")

    total_problems = end_index - start_index
    print(f"Processing {total_problems} problems (index {start_index} to {end_index-1})")
    print(f"{'='*60}\n")

    # Create a ThreadPoolExecutor and process problems
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        # Submit all problems to the executor
        future_to_problem = {
            executor.submit(
                process_problem,
                problems[i],
                model,
                args.dataset,
                log_folder,
                test_generator_prompt,
                logger,
            ): i
            for i in range(start_index, end_index)
        }

        # Process completed tasks
        completed = 0
        for future in concurrent.futures.as_completed(future_to_problem):
            problem_index = future_to_problem[future]
            completed += 1
            try:
                result = future.result()
                if result:
                    task_id, input_tokens, output_tokens, first_five_cov, total_cov, accuracy = result
                    update_total_stats(result, total_stats)
                    write_summary(log_folder, total_stats)
                    write_details(log_folder, result)

                    # Compact progress output with key metrics
                    print(f"[{completed}/{total_problems}] {task_id:<20} | "
                          f"Accuracy: {accuracy:>5.1f}% | "
                          f"Coverage: {first_five_cov:>5.1f}%→{total_cov:>5.1f}% | "
                          f"Tokens: {input_tokens}+{output_tokens}")
            except Exception as e:
                logger.error(f"Error processing problem at index {problem_index}: {e}")
                print(f"[{completed}/{total_problems}] Error at index {problem_index}")

    # Final summary
    print(f"\n{'='*60}")
    print(f"Single Agent Pipeline Completed!")
    print(f"{'='*60}")
    if total_stats['evaluated'] > 0:
        print(f"Problems evaluated: {total_stats['evaluated']}")
        print(f"Average accuracy: {total_stats['accuracy'] / total_stats['evaluated']:.2f}%")
        print(f"Average first-five coverage: {total_stats['first_five_coverage'] / total_stats['evaluated']:.2f}%")
        print(f"Average total coverage: {total_stats['coverage'] / total_stats['evaluated']:.2f}%")
        print(f"Total input tokens: {total_stats['input_tokens']}")
        print(f"Total output tokens: {total_stats['output_tokens']}")
    print(f"Results saved to: {log_folder}")
    print(f"{'='*60}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
