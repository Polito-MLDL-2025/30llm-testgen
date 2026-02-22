import os
import sys
import concurrent.futures
import json
import re


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if PROJECT_ROOT not in sys.path:
    # Allow running this file directly from any working directory.
    sys.path.insert(0, PROJECT_ROOT)

from llm30.pipeline.QAagent.utils.utils import read_problems, add_plan, add_canonical_solution, parse_args, \
    update_total_stats
from llm30.pipeline.QAagent.utils.logging import write_plan_and_tests_qa, create_log_folder, setup_logger, log_results, \
    write_summary, write_details, ensure_stream_handler
from llm30.pipeline.QAagent.agents.code_architect_agent import architect_code
from llm30.pipeline.QAagent.agents.test_generator_agent import generate_test_code
from llm30.pipeline.QAagent.agents.judge_agent import judge_single_test_suite
from llm30.pipeline.QAagent.utils.coverage import get_coverage, extract_coverage_percentages
from llm30.pipeline.QAagent.utils.accuracy import get_accuracy


def _test_suite_heuristic_score(tests: str):
    if not tests:
        return 0, 0, 0
    lines = tests.splitlines()
    assert_lines = [line.strip() for line in lines if line.strip().startswith("assert ")]
    unique_asserts = len(set(assert_lines))
    total_asserts = len(assert_lines)
    literal_tokens = set(re.findall(r"(?:'[^']*'|\"[^\"]*\"|\b\d+\b)", tests))
    literal_count = len(literal_tokens)
    return unique_asserts, literal_count, total_asserts


def save_all_agents_results(log_folder, problem_id, agent_results):
    """
    Save all agent results (plan, tests, metrics, coverage, and test results) for each agent in a problem.
    Each agent gets its own subfolder under the problem folder, with clearly named files.
    """
    import json

    def write_text_file(folder, filename, content):
        with open(os.path.join(folder, filename), 'w') as f:
            f.write(content if isinstance(content, str) else str(content))

    problem_folder = os.path.join(log_folder, f'problem_{problem_id}')
    competitive_folder = os.path.join(problem_folder, 'competitive_artifacts')
    os.makedirs(competitive_folder, exist_ok=True)

    for agent in agent_results:
        agent_index = agent["agent_index"] + 1  # 1-based index for readability
        agent_folder = os.path.join(competitive_folder, f'agent_{agent_index}')
        os.makedirs(agent_folder, exist_ok=True)

        # Save plan and tests
        write_text_file(agent_folder, 'pseudocode.txt', agent["plan"])
        write_text_file(agent_folder, 'generated_tests.txt', agent["tests"])

        # Save metrics in a more readable format
        metrics = (
            f"first_five_coverage: {agent.get('first_five_coverage', 'N/A')}\n"
            f"total_coverage: {agent.get('total_coverage', 'N/A')}\n"
            f"accuracy: {agent.get('accuracy', 'N/A')}\n"
            f"input_tokens: {agent['input_tokens']}\n"
            f"output_tokens: {agent['output_tokens']}\n"
            f"is_selected: {agent.get('is_selected', False)}\n"
            f"llm_score: {agent.get('llm_score', 'N/A')}\n"
        )
        write_text_file(agent_folder, 'metrics.txt', metrics)

        # Save coverage reports
        write_text_file(agent_folder, 'first_five_coverage_report.txt', agent.get("first_five_coverage_report", "N/A"))
        write_text_file(agent_folder, 'total_coverage_report.txt', agent.get("total_coverage_report", "N/A"))

        # Save test results (pretty JSON if possible)
        test_results = agent.get("test_results", "N/A")
        try:
            test_results_str = json.dumps(test_results, indent=2, ensure_ascii=False)
        except Exception:
            test_results_str = str(test_results)
        write_text_file(agent_folder, 'test_results.txt', test_results_str)


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


def competitive_qaAgent(problem_name, dataset, model_name, code_architect_prompts, test_generator_prompt, log_folder,
                        logger, metadata=None):
    problem_id = problem_name["task_id"]
    logger.info(f'Starting Competitive QA Agent pipeline for problem ID {problem_id}')
    agent_results = []
    total_input_tokens = 0
    total_output_tokens = 0
    judge_prompt_path = (metadata or {}).get("judge_prompt_path")
    judge_data = {"candidates": []}
    ranking = []
    judge_input_tokens = 0
    judge_output_tokens = 0

    for i, code_architect_prompt in enumerate(code_architect_prompts):
        plan, plan_input_tokens, plan_output_tokens = generate_plan(problem_name, code_architect_prompt, model_name,
                                                                    logger)
        total_input_tokens += plan_input_tokens
        total_output_tokens += plan_output_tokens
        try:
            tests, test_input_tokens, test_output_tokens = generate_tests(problem_name, plan, test_generator_prompt,
                                                                          model_name, logger)
        except Exception:
            continue
        total_input_tokens += test_input_tokens
        total_output_tokens += test_output_tokens
        agent = {
            "plan": plan,
            "tests": tests,
            "input_tokens": plan_input_tokens + test_input_tokens,
            "output_tokens": plan_output_tokens + test_output_tokens,
            "agent_index": i
        }

        # Judge each pipeline output immediately after generation.
        if judge_prompt_path:
            try:
                score, reason, in_toks, out_toks, raw = judge_single_test_suite(
                    problem_name=problem_name,
                    candidate=agent,
                    prompt_path=judge_prompt_path,
                    model=model_name,
                    logger=logger,
                    candidate_idx=i + 1,
                )
                judge_input_tokens += in_toks
                judge_output_tokens += out_toks
                agent["llm_score"] = score
                ranking.append({"candidate": i + 1, "score": score, "reason": reason})
                judge_data["candidates"].append({"candidate": i + 1, "raw": raw})
            except Exception as e:
                logger.error(f"Judge agent failed for candidate {i + 1}: {e}")
                agent["llm_score"] = None
                ranking.append({"candidate": i + 1, "score": None, "reason": f"judge_error: {e}"})
        else:
            agent["llm_score"] = None

        agent_results.append(agent)
    if not agent_results:
        return 0, 0, 0, total_input_tokens, total_output_tokens

    # Black-box selection: choose by maximum LLM score with a static tiebreaker.
    valid_scores = [item for item in ranking if isinstance(item.get("score"), (int, float))]
    if valid_scores:
        best_score = max(item["score"] for item in valid_scores)
        top_items = [item for item in valid_scores if item["score"] == best_score]
        if len(top_items) == 1:
            best_item = top_items[0]
            best_idx = int(best_item["candidate"]) - 1
            selection_reason = str(best_item["reason"])
        else:
            tied = []
            for item in top_items:
                idx = int(item["candidate"]) - 1
                heuristic = _test_suite_heuristic_score(agent_results[idx]["tests"])
                tied.append((heuristic, -idx, item))
            best_heuristic, _, best_item = max(tied, key=lambda x: (x[0], x[1]))
            best_idx = int(best_item["candidate"]) - 1
            selection_reason = f"{best_item['reason']} (tie-breaker: heuristic={best_heuristic})"
    elif not judge_prompt_path:
        logger.warning("Judge prompt path not provided. Falling back to agent 1.")
        best_idx = 0
        selection_reason = "Fallback selection (agent 1): judge prompt missing."
    else:
        logger.warning("No valid judge scores available. Falling back to agent 1.")
        best_idx = 0
        selection_reason = "Fallback selection (agent 1): no valid judge score."

    total_input_tokens += judge_input_tokens
    total_output_tokens += judge_output_tokens
    best_agent = agent_results[best_idx]
    best_agent["is_selected"] = True

    problem_folder = os.path.join(log_folder, f'problem_{problem_id}')
    os.makedirs(problem_folder, exist_ok=True)
    competitive_folder = os.path.join(problem_folder, "competitive_artifacts")
    os.makedirs(competitive_folder, exist_ok=True)
    with open(os.path.join(competitive_folder, "llm_selection.json"), "w") as f:
        json.dump(
            {
                "selected_agent": best_idx + 1,
                "selection_reason": selection_reason,
                "judge_raw": judge_data,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    logger.info(
        f"Judge selected pipeline {best_idx + 1} for problem {problem_id}: {selection_reason}"
    )

    # Evaluate selected suite after selection for reporting metrics.
    canonical_solution = (
        add_canonical_solution(problem_name) if dataset == "humaneval"
        else problem_name["canonical_solution"]
    )
    first_five_coverage_report, total_coverage_report = get_coverage(
        canonical_solution,
        best_agent["tests"],
        problem_id,
        log_folder
    )
    accuracy, test_results = get_accuracy(
        canonical_solution,
        best_agent["tests"],
        problem_folder,
        problem_id
    )
    first_five_coverage, total_coverage = extract_coverage_percentages(problem_folder, problem_name)

    best_agent["first_five_coverage_report"] = first_five_coverage_report
    best_agent["total_coverage_report"] = total_coverage_report
    best_agent["first_five_coverage"] = first_five_coverage
    best_agent["total_coverage"] = total_coverage
    best_agent["accuracy"] = accuracy
    best_agent["test_results"] = test_results

    # Analysis-only metrics for all non-selected candidates.
    # This does not affect selection and keeps the decision black-box.
    for idx, agent in enumerate(agent_results):
        if idx == best_idx:
            continue
        candidate_eval_id = f"{problem_id.replace('/', '_')}_candidate_{idx + 1}"
        analysis_root = os.path.join(competitive_folder, "eval_workspace")
        os.makedirs(analysis_root, exist_ok=True)
        candidate_folder = os.path.join(analysis_root, f"problem_{candidate_eval_id}")
        candidate_first_five_report, candidate_total_report = get_coverage(
            canonical_solution,
            agent["tests"],
            candidate_eval_id,
            analysis_root
        )
        candidate_accuracy, candidate_test_results = get_accuracy(
            canonical_solution,
            agent["tests"],
            candidate_folder,
            candidate_eval_id
        )
        candidate_first_five, candidate_total = extract_coverage_percentages(candidate_folder, problem_name)

        agent["first_five_coverage_report"] = candidate_first_five_report
        agent["total_coverage_report"] = candidate_total_report
        agent["first_five_coverage"] = candidate_first_five
        agent["total_coverage"] = candidate_total
        agent["accuracy"] = candidate_accuracy
        agent["test_results"] = candidate_test_results

    # Save all agent artifacts (selected one also contains computed metrics).
    save_all_agents_results(log_folder, problem_id, agent_results)
    write_plan_and_tests_qa(log_folder, problem_id, best_agent["plan"], best_agent["tests"])
    log_results(
        os.path.join(log_folder, f'problem_{problem_id}'),
        best_agent["first_five_coverage_report"],
        best_agent["total_coverage_report"],
        best_agent["test_results"],
        logger,
        total_input_tokens,
        total_output_tokens
    )
    return (
        best_agent["first_five_coverage"],
        best_agent["total_coverage"],
        best_agent["accuracy"],
        total_input_tokens,
        total_output_tokens
    )


def process_problem_competitive(problem, model, dataset, log_folder, code_architect_prompts, test_generator_prompt,
                                logger, judge_prompt_path=None,
                                timeout_seconds=300, max_attempts=3):
    try:
        result = competitive_qaAgent(
            problem_name=problem,
            dataset=dataset,
            model_name=model,
            code_architect_prompts=code_architect_prompts,
            test_generator_prompt=test_generator_prompt,
            log_folder=log_folder,
            logger=logger,
            metadata={
            "judge_prompt_path": judge_prompt_path
            })
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
        return problem["task_id"], 0, 0, 0.0, 0.0, 0.0


def main(argv=None) -> int:
    args = parse_args(argv)

    # Setup
    model = args.model
    dataset = args.dataset
    log_folder = create_log_folder(dataset=dataset, model=model, prefix="QAagent_competitive")
    logger = setup_logger(log_folder)
    ensure_stream_handler(logger)

    print(f"\n{'=' * 60}")
    print("QA Agent Competitive Test Case Generation Pipeline")
    print(f"{'=' * 60}")
    print(f"Model: {model}")
    print(f"Dataset: {dataset}")
    print(f"Log folder: {log_folder}")
    print(f"Max workers: {args.max_workers}")

    pipeline_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    prompt_paths = {
        "humaneval": {
            "code_architect": [
                os.path.join(pipeline_dir, "prompts", "v1", "code_architect_humaneval_prompt_1.txt"),
                os.path.join(pipeline_dir, "prompts", "v1", "code_architect_humaneval_prompt_2.txt"),
                os.path.join(pipeline_dir, "prompts", "v1", "code_architect_humaneval_prompt_3.txt")],
            "test_generator": os.path.join(pipeline_dir, "prompts", "v1", "test_generator_humaneval_prompt.txt"),
            "test_generator_original": os.path.join(pipeline_dir, "prompts", "v1",
                                                    "test_generator_humaneval_prompt_original.txt"),
            "judge": os.path.join(pipeline_dir, "prompts", "v1", "judge_competitive_humaneval_prompt.txt"),
        },
        "mbpp": {
            "code_architect": [os.path.join(pipeline_dir, "prompts", "v1", "code_architect_mbpp_prompt.txt")],
            "test_generator": os.path.join(pipeline_dir, "prompts", "v1", "test_generator_mbpp_prompt.txt"),
            "judge": os.path.join(pipeline_dir, "prompts", "v1", "judge_competitive_humaneval_prompt.txt"),
        }
    }
    code_architect_prompts = prompt_paths[args.dataset]["code_architect"]
    test_generator_prompt = prompt_paths[args.dataset]["test_generator"]
    if args.generator_prompt == "original":
        test_generator_prompt = prompt_paths[args.dataset].get("test_generator_original", test_generator_prompt)
    judge_prompt_path = prompt_paths[args.dataset].get("judge")
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
    print(f"Processing {total_problems} problems (index {start_index} to {end_index - 1})")
    print(f"{'=' * 60}\n")

    # Create a ThreadPoolExecutor and process problems
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        future_to_problem = {
            executor.submit(
                process_problem_competitive,
                problems[i],
                model,
                args.dataset,
                log_folder,
                code_architect_prompts,
                test_generator_prompt,
                logger,
                judge_prompt_path,
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
    print(f"\n{'=' * 60}")
    print("QA Agent Competitive Pipeline Completed!")
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
