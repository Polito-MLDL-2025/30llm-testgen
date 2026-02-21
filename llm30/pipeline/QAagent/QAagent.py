import os
import sys
import logging
import multiprocessing
import queue as queue_module
import time
import concurrent.futures

from llm30.pipeline.QAagent.agents.process_handler import QAagentProcessHandler

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if PROJECT_ROOT not in sys.path:
    # Allow running this file directly from any working directory.
    sys.path.insert(0, PROJECT_ROOT)

from llm30.pipeline.QAagent.utils.utils import read_problems, add_plan, add_canonical_solution, parse_args, \
    update_total_stats
from llm30.pipeline.QAagent.utils.logging import (
    write_plan_and_tests_qa,
    create_log_folder,
    setup_logger,
    log_results,
    write_summary,
    write_details, ensure_stream_handler,
)
from llm30.pipeline.QAagent.agents.code_architect_agent import architect_code
from llm30.pipeline.QAagent.agents.test_generator_agent import generate_test_code
from llm30.pipeline.QAagent.utils.coverage import get_coverage, extract_coverage_percentages
from llm30.pipeline.QAagent.utils.accuracy import get_accuracy


def generate_plan(problem_name, code_architect_prompt, model_name, logger):
    logger.info(f'Generating pseudocode for problem ID {problem_name["task_id"]}')
    plan, plan_input_tokens, plan_output_tokens = architect_code(problem_name, code_architect_prompt, model_name)
    logger.info(
        f'Generated plan ({len(plan.splitlines())} lines). '
        f'Tokens - Input: {plan_input_tokens}, Output: {plan_output_tokens}'
    )
    return plan, plan_input_tokens, plan_output_tokens


def generate_tests(problem_name, plan, test_generator_prompt, model_name, logger):
    logger.info(f'Generating tests for problem ID {problem_name["task_id"]}')
    try:
        tests, test_input_tokens, test_output_tokens, _ = generate_test_code(
            add_plan(problem_name, plan), problem_name["task_id"], test_generator_prompt, model_name, logger
        )
        logger.info(
            f'Generated {len(tests.splitlines())} lines of tests. '
            f'Tokens - Input: {test_input_tokens}, Output: {test_output_tokens}'
        )
        return tests, test_input_tokens, test_output_tokens
    except Exception as e:
        logger.error(f'Error generating tests: {e}')
        raise


def process_problem(problem, model, dataset, log_folder, code_architect_prompt, test_generator_prompt, logger,
                    timeout_seconds=700, max_attempts=3):
    try:
        agent_processor = QAagentProcessHandler(
            problem=problem,
            dataset=dataset,
            model=model,
            code_architect_prompt=code_architect_prompt,
            test_generator_prompt=test_generator_prompt,
            log_folder=log_folder,
            logger=logger,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
            run_qaagent_function=qaAgent
        )
        result = agent_processor.run()
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


def qaAgent(problem_name, dataset, model_name, code_architect_prompt, test_generator_prompt, log_folder, logger,
            metadata=None):
    num_input_tokens = 0
    num_output_tokens = 0
    problem_id = problem_name["task_id"]
    logger.info(f'Starting QA Agent pipeline for problem ID {problem_id}')

    # generate natural language pseudocode from problem["prompt"]
    plan, plan_input_tokens, plan_output_tokens = generate_plan(problem_name, code_architect_prompt, model_name, logger)
    num_input_tokens += plan_input_tokens
    num_output_tokens += plan_output_tokens

    try:
        generated_tests, test_input_tokens, test_output_tokens = generate_tests(problem_name, plan,
                                                                                test_generator_prompt, model_name,
                                                                                logger)
        num_input_tokens += test_input_tokens
        num_output_tokens += test_output_tokens
    except Exception:
        return 0, 0, 0, 0, 0

    # log plan/pseudocode and tests
    write_plan_and_tests_qa(log_folder, problem_id, plan, generated_tests)

    # check the code coverage of the generated tests
    logger.info(f'Checking code coverage for problem ID {problem_id}')

    # Prepare canonical solution (avoid repeated calculation)
    canonical_solution = (
        add_canonical_solution(problem_name) if dataset == "humaneval"
        else problem_name["canonical_solution"]
    )

    # get coverage reports
    first_five_coverage_report, total_coverage_report = get_coverage(
        canonical_solution,
        generated_tests,
        problem_id,
        log_folder
    )

    # Calculate generated tests accuracy on the canonical solution. # passes / total tests
    problem_folder = os.path.join(log_folder, f'problem_{problem_id}')
    accuracy, test_results = get_accuracy(
        canonical_solution,
        generated_tests,
        problem_folder,
        problem_id
    )

    # Extract and log test coverage
    first_five_coverage, total_coverage = extract_coverage_percentages(problem_folder, problem_name)

    # Log results
    log_results(problem_folder, first_five_coverage_report, total_coverage_report, test_results, logger,
                num_input_tokens, num_output_tokens)

    return first_five_coverage, total_coverage, accuracy, num_input_tokens, num_output_tokens


def main(argv=None) -> int:
    args = parse_args(argv)

    # Setup
    model = args.model
    dataset = args.dataset
    log_folder = create_log_folder(dataset=dataset, model=model)
    logger = setup_logger(log_folder)
    ensure_stream_handler(logger)

    print(f"\n{'=' * 60}")
    print("QA Agent Test Case Generation Pipeline")
    print(f"{'=' * 60}")
    print(f"Model: {model}")
    print(f"Dataset: {dataset}")
    print(f"Log folder: {log_folder}")
    print(f"Max workers: {args.max_workers}")

    pipeline_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    # Load prompts and problems
    prompt_paths = {
        "humaneval": {
            "code_architect": os.path.join(pipeline_dir, "prompts", "v1", "code_architect_humaneval_prompt.txt"),
            "test_generator": os.path.join(pipeline_dir, "prompts", "v1", "test_generator_humaneval_prompt.txt"),
            "test_generator_original": os.path.join(pipeline_dir, "prompts", "v1",
                                                    "test_generator_humaneval_prompt_original.txt"),
        },
        "mbpp": {
            "code_architect": os.path.join(pipeline_dir, "prompts", "v1", "code_architect_mbpp_prompt.txt"),
            "test_generator": os.path.join(pipeline_dir, "prompts", "v1", "test_generator_mbpp_prompt.txt"),
        }
    }
    code_architect_prompt = prompt_paths[args.dataset]["code_architect"]
    test_generator_prompt = prompt_paths[args.dataset]["test_generator"]
    if args.generator_prompt == "original":
        test_generator_prompt = prompt_paths[args.dataset].get("test_generator_original", test_generator_prompt)

    # Load dataset default
    dataset_map = {
        "humaneval": os.path.join(pipeline_dir, "datasets", "humaneval", "problems.jsonl"),
        "mbpp": os.path.join(pipeline_dir, "datasets", "mbpp", "problems.jsonl")
    }
    dataset_path = dataset_map[args.dataset]
    if args.dataset_path:
        dataset_path = args.dataset_path
    problems = read_problems(dataset_path)
    print(f"Loaded {len(problems)} problems from: {dataset_path}")

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
    print(f"Processing {total_problems} problems (index {start_index} to {end_index - 1})")
    print(f"{'=' * 60}\n")

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
    print(f"\n{'=' * 60}")
    print("QA Agent Pipeline Completed!")
    print(f"{'=' * 60}")
    if total_stats['evaluated'] > 0:
        print(f"Problems evaluated: {total_stats['evaluated']}")
        print(f"Average accuracy: {total_stats['accuracy'] / total_stats['evaluated']:.2f}%")
        print(f"Average first-five coverage: {total_stats['first_five_coverage'] / total_stats['evaluated']:.2f}%")
        print(f"Average total coverage: {total_stats['coverage'] / total_stats['evaluated']:.2f}%")
        print(f"Total input tokens: {total_stats['input_tokens']}")
        print(f"Total output tokens: {total_stats['output_tokens']}")
    print(f"Results saved to: {log_folder}")
    print(f"{'=' * 60}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
