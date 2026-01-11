import os
import sys
import concurrent.futures

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if PROJECT_ROOT not in sys.path:
    # Allow running this file directly from any working directory.
    sys.path.insert(0, PROJECT_ROOT)

from llm30.pipeline.QAagent.utils.utils import read_problems, add_plan, add_canonical_solution, parse_args, update_total_stats
from llm30.pipeline.QAagent.utils.logging import write_plan_and_tests_qa, create_log_folder, setup_logger, log_results, write_summary, write_details
from llm30.pipeline.QAagent.agents.code_architect_agent import architect_code
from llm30.pipeline.QAagent.agents.test_generator_agent import generate_test_code
from llm30.pipeline.QAagent.utils.coverage import get_coverage, extract_coverage_percentages
from llm30.pipeline.QAagent.utils.accuracy import get_accuracy


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
    os.makedirs(problem_folder, exist_ok=True)

    for agent in agent_results:
        agent_index = agent["agent_index"] + 1  # 1-based index for readability
        agent_folder = os.path.join(problem_folder, f'agent_{agent_index}')
        os.makedirs(agent_folder, exist_ok=True)

        # Save plan and tests
        write_text_file(agent_folder, 'pseudocode.txt', agent["plan"])
        write_text_file(agent_folder, 'generated_tests.txt', agent["tests"])

        # Save metrics in a more readable format
        metrics = (
            f"first_five_coverage: {agent['first_five_coverage']}\n"
            f"total_coverage: {agent['total_coverage']}\n"
            f"accuracy: {agent['accuracy']}\n"
            f"input_tokens: {agent['input_tokens']}\n"
            f"output_tokens: {agent['output_tokens']}\n"
        )
        write_text_file(agent_folder, 'metrics.txt', metrics)

        # Save coverage reports
        write_text_file(agent_folder, 'first_five_coverage_report.txt', agent["first_five_coverage_report"])
        write_text_file(agent_folder, 'total_coverage_report.txt', agent["total_coverage_report"])

        # Save test results (pretty JSON if possible)
        test_results = agent["test_results"]
        try:
            test_results_str = json.dumps(test_results, indent=2, ensure_ascii=False)
        except Exception:
            test_results_str = str(test_results)
        write_text_file(agent_folder, 'test_results.txt', test_results_str)

def generate_plan(problem_name, code_architect_prompt, model_name, logger):
    logger.info(f'Generating pseudocode for problem ID {problem_name["task_id"]}')
    plan, plan_input_tokens, plan_output_tokens = architect_code(problem_name, code_architect_prompt, model_name)
    logger.info(f'Generated plan: {plan}\nInput tokens: {plan_input_tokens}, Output tokens: {plan_output_tokens}')
    return plan, plan_input_tokens, plan_output_tokens

def generate_tests(problem_name, plan, test_generator_prompt, model_name, logger):
    logger.info(f'Generating tests for problem ID {problem_name["task_id"]}')
    try:
        tests, test_input_tokens, test_output_tokens, _ = generate_test_code(
            add_plan(problem_name, plan), problem_name["task_id"], test_generator_prompt, model_name, logger
        )
        logger.info(f'Generated tests: {tests}\nInput tokens: {test_input_tokens}, Output tokens: {test_output_tokens}')
        return tests, test_input_tokens, test_output_tokens
    except Exception as e:
        logger.error(f'Error generating tests: {e}')
        raise

def competitive_qaAgent(problem_name, dataset, model_name, code_architect_prompts, test_generator_prompt, log_folder, logger):
    problem_id = problem_name["task_id"]
    logger.info(f'Starting competitive QA for problem ID {problem_id}')
    agent_results = []
    for i, code_architect_prompt in enumerate(code_architect_prompts):
        plan, plan_input_tokens, plan_output_tokens = generate_plan(problem_name, code_architect_prompt, model_name, logger)
        try:
            tests, test_input_tokens, test_output_tokens = generate_tests(problem_name, plan, test_generator_prompt, model_name, logger)
        except Exception:
            continue
        logger.info(f'Checking code coverage for problem ID {problem_id} (agent {i+1})')
        first_five_coverage_report, total_coverage_report = get_coverage(
            add_canonical_solution(problem_name) if dataset == "humaneval" else problem_name["canonical_solution"],
            tests, problem_id, log_folder
        )
        problem_folder = os.path.join(log_folder, f'problem_{problem_id}')
        accuracy, test_results = get_accuracy(
            add_canonical_solution(problem_name) if dataset == "humaneval" else problem_name["canonical_solution"],
            tests, problem_folder, problem_id
        )
        first_five_coverage, total_coverage = extract_coverage_percentages(problem_folder, problem_name)
        total_input_tokens = plan_input_tokens + test_input_tokens
        total_output_tokens = plan_output_tokens + test_output_tokens
        agent_results.append({
            "plan": plan,
            "tests": tests,
            "first_five_coverage_report": first_five_coverage_report,
            "total_coverage_report": total_coverage_report,
            "first_five_coverage": first_five_coverage,
            "total_coverage": total_coverage,
            "accuracy": accuracy,
            "test_results": test_results,
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "agent_index": i
        })
    if not agent_results:
        return 0, 0, 0, 0, 0
    # Save all agent results before selecting the best
    save_all_agents_results(log_folder, problem_id, agent_results)
    best_agent = max(agent_results, key=lambda x: (x["total_coverage"], x["accuracy"]))
    write_plan_and_tests_qa(log_folder, problem_id, best_agent["plan"], best_agent["tests"])
    log_results(
        os.path.join(log_folder, f'problem_{problem_id}'),
        best_agent["first_five_coverage_report"],
        best_agent["total_coverage_report"],
        best_agent["test_results"],
        logger,
        best_agent["input_tokens"],
        best_agent["output_tokens"]
    )
    return (
        best_agent["first_five_coverage"],
        best_agent["total_coverage"],
        best_agent["accuracy"],
        best_agent["input_tokens"],
        best_agent["output_tokens"]
    )

def process_problem_competitive(problem, model, dataset, log_folder, code_architect_prompts, test_generator_prompt, logger):
    try:
        curr_first_five_coverage_percentage, curr_total_coverage_percentage, accuracy_percentage, curr_num_input_tokens, curr_num_output_tokens = competitive_qaAgent(
            problem, dataset, model, code_architect_prompts, test_generator_prompt, log_folder, logger
        )
        return problem["task_id"], curr_num_input_tokens, curr_num_output_tokens, curr_first_five_coverage_percentage, curr_total_coverage_percentage, accuracy_percentage
    except Exception as e:
        logger.error(f'Error in problem ID {problem["task_id"]}: {e}')
        with open(os.path.join(log_folder, 'errors.txt'), 'a') as f:
            f.write(f'Error in problem ID {problem["task_id"]}: {e}\n')
        return problem["task_id"], 0, 0, 0.0, 0.0, 0.0

if __name__ == "__main__":
    args = parse_args()
    model = args.model
    dataset = args.dataset
    log_folder = create_log_folder(prefix="QAagent_competitive")
    logger = setup_logger(log_folder)
    pipeline_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    prompt_paths = {
        "humaneval": {
            "code_architect": [
                os.path.join(pipeline_dir, "prompts", "v1", "code_architect_humaneval_prompt_1.txt"),
                os.path.join(pipeline_dir, "prompts", "v1", "code_architect_humaneval_prompt_2.txt"),
                os.path.join(pipeline_dir, "prompts", "v1", "code_architect_humaneval_prompt_3.txt")],
            "test_generator": os.path.join(pipeline_dir, "prompts", "v1", "test_generator_humaneval_prompt.txt"),
        },
        "mbpp": {
            "code_architect": [os.path.join(pipeline_dir, "prompts", "v1", "code_architect_mbpp_prompt.txt")],
            "test_generator": os.path.join(pipeline_dir, "prompts", "v1", "test_generator_mbpp_prompt.txt"),
        }
    }
    code_architect_prompts = prompt_paths[args.dataset]["code_architect"]
    test_generator_prompt = prompt_paths[args.dataset]["test_generator"]
    dataset_map = {
        "humaneval": os.path.join(pipeline_dir, "datasets", "humaneval", "problems.jsonl"),
        "mbpp": os.path.join(pipeline_dir, "datasets", "mbpp", "problems.jsonl")
    }
    problems = read_problems(dataset_map[args.dataset])
    print(f"Loaded problems from: {dataset_map[args.dataset]}")
    total_stats = {
        'input_tokens': 0,
        'output_tokens': 0,
        'first_five_coverage': 0.0,
        'coverage': 0.0,
        'accuracy': 0.0,
        'evaluated': 0
    }
    start_index = 0
    dataset_limit = 164 if args.dataset == "humaneval" else 500
    end_index = min(dataset_limit, len(problems))
    if args.max_tasks is not None:
        if args.max_tasks < 0:
            raise ValueError("max_tasks must be non-negative.")
        end_index = min(end_index, start_index + args.max_tasks)
    if args.max_workers <= 0:
        raise ValueError("max_workers must be positive.")
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
            ): i
            for i in range(start_index, end_index)
        }
        for future in concurrent.futures.as_completed(future_to_problem):
            problem_index = future_to_problem[future]
            try:
                result = future.result()
                if result:
                    update_total_stats(result, total_stats)
                    write_summary(log_folder, total_stats)
                    write_details(log_folder, result)
            except Exception as e:
                logger.error(f"Error processing problem: {e}")
