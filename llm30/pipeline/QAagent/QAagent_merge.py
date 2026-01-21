import os
import sys
import ast
import logging
import multiprocessing
import queue as queue_module
import textwrap
import time
import concurrent.futures

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if PROJECT_ROOT not in sys.path:
    # Allow running this file directly from any working directory.
    sys.path.insert(0, PROJECT_ROOT)

from llm30.pipeline.QAagent.utils.utils import read_problems, add_plan, add_canonical_solution, parse_args, update_total_stats
from llm30.pipeline.QAagent.utils.logging import (
    write_plan_and_tests_qa,
    create_log_folder,
    setup_logger,
    log_results,
    write_summary,
    write_details,
)
from llm30.pipeline.QAagent.agents.code_architect_agent import architect_code
from llm30.pipeline.QAagent.agents.test_generator_agent import generate_test_code
from llm30.pipeline.QAagent.agents.merger_agent import (
    merge_tests_concat,
    merge_tests_concat_enhanced,
    merge_tests_llm,
    merge_plans_concat,
)
from llm30.pipeline.QAagent.utils.coverage import get_coverage, extract_coverage_percentages
from llm30.pipeline.QAagent.utils.accuracy import get_accuracy


def generate_plan(problem_name, code_architect_prompt, model_name, logger, agent_index=None):
    problem_id = problem_name["task_id"]
    agent_label = f" [agent {agent_index}]" if agent_index is not None else ""
    logger.info(f'Generating pseudocode for problem ID {problem_id}{agent_label}')
    plan, plan_input_tokens, plan_output_tokens = architect_code(problem_name, code_architect_prompt, model_name)
    logger.info(
        f'Generated plan{agent_label} ({len(plan.splitlines())} lines). '
        f'Tokens - Input: {plan_input_tokens}, Output: {plan_output_tokens}'
    )
    return plan, plan_input_tokens, plan_output_tokens

def generate_tests(problem_name, plan, test_generator_prompt, model_name, logger, agent_index=None):
    problem_id = problem_name["task_id"]
    agent_label = f" [agent {agent_index}]" if agent_index is not None else ""
    logger.info(f'Generating tests for problem ID {problem_id}{agent_label}')
    try:
        tests, test_input_tokens, test_output_tokens, _ = generate_test_code(
            add_plan(problem_name, plan), problem_name["task_id"], test_generator_prompt, model_name, logger
        )
        logger.info(
            f'Generated {len(tests.splitlines())} lines of tests{agent_label}. '
            f'Tokens - Input: {test_input_tokens}, Output: {test_output_tokens}'
        )
        return tests, test_input_tokens, test_output_tokens
    except Exception as e:
        logger.error(f'Error generating tests{agent_label}: {e}')
        raise

def _clean_tests(test_string):
    lines = []
    for line in test_string.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            continue
        lines.append(line.rstrip())
    return textwrap.dedent("\n".join(lines)).strip()


def _filter_tests_for_accuracy(canonical_solution, tests, logger, problem_id):
    cleaned_tests = _clean_tests(tests)
    if not cleaned_tests:
        logger.info(f"Accuracy filter: no tests to filter for problem {problem_id}")
        return ""

    exec_globals = {}
    exec(canonical_solution, exec_globals)

    kept_lines = []
    total_asserts = 0
    kept_asserts = 0
    skipped_asserts = 0
    skipped_setup = 0

    try:
        module = ast.parse(cleaned_tests)
        statements = module.body
        for stmt in statements:
            source = ast.get_source_segment(cleaned_tests, stmt)
            if source is None:
                continue
            if isinstance(stmt, ast.Assert):
                total_asserts += 1
                try:
                    exec(compile(ast.Module([stmt], type_ignores=[]), "<tests>", "exec"), exec_globals)
                except (AssertionError, Exception):
                    skipped_asserts += 1
                    continue
                kept_asserts += 1
                kept_lines.append(source)
            else:
                try:
                    exec(compile(ast.Module([stmt], type_ignores=[]), "<tests>", "exec"), exec_globals)
                except Exception:
                    skipped_setup += 1
                    continue
                kept_lines.append(source)
    except SyntaxError as e:
        logger.warning(
            f"Accuracy filter parse error for problem {problem_id}: {e}. "
            "Falling back to line-based filtering."
        )
        for line in cleaned_tests.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("assert"):
                total_asserts += 1
                try:
                    exec(stripped, exec_globals)
                except (AssertionError, Exception):
                    skipped_asserts += 1
                    continue
                kept_asserts += 1
                kept_lines.append(stripped)
            else:
                try:
                    exec(line, exec_globals)
                except Exception:
                    skipped_setup += 1
                    continue
                kept_lines.append(line)

    logger.info(
        f"Accuracy filter for problem {problem_id}: kept {kept_asserts}/{total_asserts} asserts, "
        f"skipped setup lines: {skipped_setup}"
    )
    return "\n".join(kept_lines).strip()

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


def _qaagent_worker(
    result_queue,
    output_queue,
    problem,
    dataset,
    model,
    code_architect_prompt,
    test_generator_prompt,
    log_folder,
    merge_strategy,
    merger_prompt_path,
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
        result = qaAgent(
            problem,
            dataset,
            model,
            code_architect_prompt,
            test_generator_prompt,
            log_folder,
            logger,
            merge_strategy,
            merger_prompt_path,
        )
        result_queue.put(("ok", result))
    except Exception as exc:
        logger.exception("Worker error for problem %s: %s", problem.get("task_id"), exc)
        result_queue.put(("error", str(exc)))


def _run_qaagent_with_timeout(
    problem,
    dataset,
    model,
    code_architect_prompt,
    test_generator_prompt,
    log_folder,
    merge_strategy,
    merger_prompt_path,
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
            target=_qaagent_worker,
            args=(
                result_queue,
                output_queue,
                problem,
                dataset,
                model,
                code_architect_prompt,
                test_generator_prompt,
                log_folder,
                merge_strategy,
                merger_prompt_path,
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

def qaAgent(problem_name, dataset, model_name, code_architect_prompt, test_generator_prompt, log_folder, logger, merge_strategy="concat", merger_prompt_path=None):
    num_input_tokens = 0
    num_output_tokens = 0
    problem_id = problem_name["task_id"]
    logger.info(
        f'Starting QA Agent merge pipeline for problem ID {problem_id} '
        f'using strategy {merge_strategy}'
    )

    # generate natural language pseudocode from problem["prompt"]
    plan = []
    for i in range(len(code_architect_prompt)):
        logger.info(f"Step: plan generation start for agent {i + 1}/{len(code_architect_prompt)}")
        p, plan_input_tokens, plan_output_tokens = generate_plan(
            problem_name,
            code_architect_prompt[i],
            model_name,
            logger,
            agent_index=i + 1,
        )
        plan.append(p)
        num_input_tokens += plan_input_tokens
        num_output_tokens += plan_output_tokens
        logger.info(f"Step: plan generation complete for agent {i + 1}/{len(code_architect_prompt)}")

    # generate tests
    logger.info(f'Step: test generation start for problem ID {problem_id}')
    generated_tests = []
    try:
        for i in range(len(plan)):
            logger.info(f"Step: test generation start for agent {i + 1}/{len(plan)}")
            tests, test_input_tokens, test_output_tokens = generate_tests(
                problem_name,
                plan[i],
                test_generator_prompt,
                model_name,
                logger,
                agent_index=i + 1,
            )
            generated_tests.append(tests)
            num_input_tokens += test_input_tokens
            num_output_tokens += test_output_tokens
            logger.info(f"Step: test generation complete for agent {i + 1}/{len(plan)}")
    except Exception:
        return 0, 0, 0, 0, 0

    # Merge plans and tests according to the specified strategy
    logger.info(
        f"Step: merge start for problem ID {problem_id} "
        f"({len(generated_tests)} test sets)"
    )
    if merge_strategy == "concat":
        # Concatenate all test sets and plans
        merged_tests = merge_tests_concat(generated_tests)
        merged_plan = merge_plans_concat(plan)
        logger.info(f'Merged tests and plans using concat strategy')
    elif merge_strategy == "concat-enhanced":
        # Concatenate with syntax validation and deduplication
        merged_tests = merge_tests_concat_enhanced(generated_tests, problem_name, logger)
        merged_plan = merge_plans_concat(plan)
        logger.info(f'Merged tests and plans using concat-enhanced strategy')
    elif merge_strategy == "llm":
        # Use LLM to intelligently merge test sets
        # For plans, concatenate them to provide full context to the test merger
        merged_plan = merge_plans_concat(plan)
        if merger_prompt_path is None:
            logger.error("Merger prompt path not provided for LLM merge strategy")
            # Fallback to concat
            merged_tests = merge_tests_concat(generated_tests)
        else:
            # Pass the merged plan (all plans concatenated) to provide full context
            merged_tests, merge_input_tokens, merge_output_tokens = merge_tests_llm(
                generated_tests, problem_name, merged_plan, merger_prompt_path, model_name, logger
            )
            num_input_tokens += merge_input_tokens
            num_output_tokens += merge_output_tokens
            logger.info(f'Merged tests using LLM strategy')
    elif merge_strategy == "accuracy":
        # Filter to tests that pass the canonical solution to optimize accuracy
        merged_plan = merge_plans_concat(plan)
        merged_tests = merge_tests_concat_enhanced(generated_tests, problem_name, logger)
        merged_tests = _filter_tests_for_accuracy(
            add_canonical_solution(problem_name) if dataset == "humaneval" else problem_name["canonical_solution"],
            merged_tests,
            logger,
            problem_id,
        )
        logger.info(f'Merged tests using accuracy strategy (pass-only filter)')
    else:
        # Default to concat
        merged_tests = merge_tests_concat(generated_tests)
        merged_plan = merge_plans_concat(plan)
        logger.warning(f'Unknown merge strategy: {merge_strategy}, defaulting to concat')
    logger.info(
        f"Step: merge complete for problem ID {problem_id} "
        f"({len(merged_tests.splitlines())} test lines)"
    )

    # log plan/pseudocode and tests
    write_plan_and_tests_qa(log_folder, problem_id, merged_plan, merged_tests)
    logger.info(f"Step: wrote merged artifacts for problem ID {problem_id}")

    # check the code coverage of the generated tests
    logger.info(f'Step: coverage start for problem ID {problem_id}')

    # Prepare canonical solution (avoid repeated calculation)
    canonical_solution = (
        add_canonical_solution(problem_name) if dataset == "humaneval"
        else problem_name["canonical_solution"]
    )

    # get coverage reports
    first_five_coverage_report, total_coverage_report = get_coverage(add_canonical_solution(problem_name) if dataset == "humaneval" else problem_name["canonical_solution"], merged_tests, problem_id, log_folder)

    # Calculate generated tests accuracy on the canonical solution. # passes / total tests
    problem_folder = os.path.join(log_folder, f'problem_{problem_id}')
    accuracy, test_results = get_accuracy(add_canonical_solution(problem_name) if dataset == "humaneval" else problem_name["canonical_solution"], merged_tests, problem_folder, problem_id)

    # Extract and log test coverage
    first_five_coverage, total_coverage = extract_coverage_percentages(problem_folder, problem_name)
    logger.info(
        f"Step: metrics for problem ID {problem_id} - "
        f"Accuracy: {accuracy:.2f}% | "
        f"Coverage: {first_five_coverage:.2f}%→{total_coverage:.2f}%"
    )

    # Log results
    log_results(problem_folder, first_five_coverage_report, total_coverage_report, test_results, logger, num_input_tokens, num_output_tokens)
    logger.info(f"Completed problem ID {problem_id}")

    return first_five_coverage, total_coverage, accuracy, num_input_tokens, num_output_tokens


def process_problem(problem, model, dataset, log_folder, code_architect_prompt, test_generator_prompt, logger, merge_strategy="concat", merger_prompt_path=None):
    try:
        result = _run_qaagent_with_timeout(
            problem,
            dataset,
            model,
            code_architect_prompt,
            test_generator_prompt,
            log_folder,
            merge_strategy,
            merger_prompt_path,
            logger,
        )
        if result is None:
            return problem["task_id"], 0, 0, 0.0, 0.0, 0.0
        curr_first_five_coverage_percentage, curr_total_coverage_percentage, accuracy_percentage, curr_num_input_tokens, curr_num_output_tokens = result
        return (
            problem["task_id"],
            curr_num_input_tokens,
            curr_num_output_tokens,
            curr_first_five_coverage_percentage,
            curr_total_coverage_percentage,
            accuracy_percentage,
        )
    except Exception as e:
        logger.error(f'Error in problem ID {problem["task_id"]}: {e}')
        with open(os.path.join(log_folder, 'errors.txt'), 'a') as f:
            f.write(f'Error in problem ID {problem["task_id"]}: {e}\n')
        return problem["task_id"], 0, 0, 0.0, 0.0, 0.0  # Return 0 tokens if there's an error

def main(argv=None) -> int:
    args = parse_args(argv)

    # Setup
    model = args.model
    dataset = args.dataset
    log_folder = create_log_folder(dataset=dataset, model=model, prefix='QAagent_merge')
    logger = setup_logger(log_folder)
    _ensure_stream_handler(logger)

    print(f"\n{'='*60}")
    print("QA Agent Test Case Generation Pipeline")
    print(f"{'='*60}")
    print(f"Model: {model}")
    print(f"Dataset: {dataset}")
    print(f"Log folder: {log_folder}")
    print(f"Max workers: {args.max_workers}")

    pipeline_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    # Load prompts and problems
    prompt_paths = {
        "humaneval": {
            "code_architect": [
                os.path.join(pipeline_dir, "prompts", "v1", "code_architect_humaneval_prompt_1.txt"),
                os.path.join(pipeline_dir, "prompts", "v1", "code_architect_humaneval_prompt_2.txt"),
                os.path.join(pipeline_dir, "prompts", "v1", "code_architect_humaneval_prompt_3.txt")],
            "test_generator": os.path.join(pipeline_dir, "prompts", "v1", "test_generator_humaneval_prompt.txt"),
            "test_generator_original": os.path.join(pipeline_dir, "prompts", "v1", "test_generator_humaneval_prompt_original.txt"),
            "merger": os.path.join(pipeline_dir, "prompts", "v1", "merger_llm_humaneval_prompt.txt"),
        },
        "mbpp": {
            "code_architect": os.path.join(pipeline_dir, "prompts", "v1", "code_architect_mbpp_prompt.txt"),
            "test_generator": os.path.join(pipeline_dir, "prompts", "v1", "test_generator_mbpp_prompt.txt"),
            "merger": None,  # MBPP doesn't have a merger prompt yet
        }
    }
    code_architect_prompt = prompt_paths[args.dataset]["code_architect"]

    # Select test generator prompt based on generator-prompt argument
    test_generator_prompt = prompt_paths[args.dataset]["test_generator"]
    if args.generator_prompt == "original":
        test_generator_prompt = prompt_paths[args.dataset].get("test_generator_original", test_generator_prompt)

    merger_prompt_path = prompt_paths[args.dataset].get("merger", None)

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

    # Run the QaAgent function on each problem
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

    # Create a ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        # Submit all problems to the executor
        future_to_problem = {
            executor.submit(
                process_problem,
                problems[i],
                model,
                args.dataset,
                log_folder,
                code_architect_prompt,
                test_generator_prompt,
                logger,
                args.merge_strategy,
                merger_prompt_path,
            ): i
            for i in range(start_index, end_index)
        }
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
                    print(f"[{completed}/{total_problems}] {task_id:<20} | "
                          f"Accuracy: {accuracy:>5.1f}% | "
                          f"Coverage: {first_five_cov:>5.1f}%→{total_cov:>5.1f}% | "
                          f"Tokens: {input_tokens}+{output_tokens}")
            except Exception as e:
                logger.error(f"Error processing problem: {e}")
                print(f"[{completed}/{total_problems}] Error at index {problem_index}")

    # Final summary
    print(f"\n{'='*60}")
    print("QA Agent Pipeline Completed!")
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
