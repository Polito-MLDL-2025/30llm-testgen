# import os
# import coverage
# from io import StringIO
# import runpy
# from llm30.pipeline.QAagent.tools.parse_coverage_html import extract_success_percentage
#
# def get_coverage(code_string, test_string, problem_id, log_folder):
#
#     # write code string to a file in the problem_id folder called temp_problem_id.py
#     os.makedirs(os.path.join(log_folder, f'problem_{problem_id}', 'first_five_coverage'), exist_ok=True)
#     os.makedirs(os.path.join(log_folder, f'problem_{problem_id}', 'total_coverage'), exist_ok=True)
#
#     test_lines = test_string.split('\n')
#     filtered_test_lines = [line for line in test_lines if
#                            line.strip() and not line.strip().startswith('#') and line.strip().startswith('assert')]
#
#     # Write the combined code and test string to separate files for full and first five tests
#     with open(os.path.join(log_folder, f'problem_{problem_id}', 'total_coverage', 'total_coverage.py'), 'w') as f2:
#         f2.write(code_string + "\n" + "\n".join(filtered_test_lines))
#
#     # If there are less than five tests, only use the available tests
#     if len(filtered_test_lines) < 5:
#         first_five_tests = "\n".join(test_lines)
#     else:
#         first_five_tests = "\n".join(filtered_test_lines[:5])
#
#     with open(os.path.join(log_folder, f'problem_{problem_id}', 'first_five_coverage', 'first_five_coverage.py'), 'w') as f2:
#         f2.write(code_string)
#         f2.write("\n" + first_five_tests)
#
#     # Set up coverages
#     cov_total = coverage.Coverage(concurrency='thread', data_suffix=True)
#     try:
#         cov_total.start()
#         # Run total tests coverage
#         runpy.run_path(os.path.join(log_folder, f'problem_{problem_id}', 'total_coverage', 'total_coverage.py'))
#         print("All tests passed successfully!")
#     except AssertionError as e:
#         print(f"Test failed: {str(e)}")
#     except Exception as e:
#         print(f"An error occurred during testing: {str(e)}")
#     finally:
#         cov_total.stop()
#         cov_total.save()
#         # Generate the coverage reports
#         report_output_total = StringIO()
#         cov_total.report(show_missing=True, file=report_output_total)
#         cov_total.html_report(directory=os.path.join(log_folder, f'problem_{problem_id}', 'total_coverage'))
#
#         # Capture the coverage reports
#         total_coverage_report = report_output_total.getvalue()
#         cov_total.erase()
#
#     # Set up coverages
#     cov_five = coverage.Coverage(concurrency='thread', data_suffix=True)
#     cov_five.start()
#     try:
#         # Run total tests coverage
#         runpy.run_path(os.path.join(log_folder, f'problem_{problem_id}', 'first_five_coverage', 'first_five_coverage.py'))
#         print("All tests passed successfully!")
#     except AssertionError as e:
#         print(f"Test failed: {str(e)}")
#     except Exception as e:
#         print(f"An error occurred during testing: {str(e)}")
#     finally:
#         cov_five.stop()
#         cov_five.save()
#         # Generate the coverage reports
#         report_output_first_five = StringIO()
#         cov_five.report(show_missing=True, file=report_output_first_five)
#         cov_five.html_report(directory=os.path.join(log_folder, f'problem_{problem_id}', 'first_five_coverage'))
#
#         # Capture the coverage reports
#         first_five_coverage_report = report_output_first_five.getvalue()
#         cov_five.erase()
#
#     return first_five_coverage_report, total_coverage_report
#
# def extract_coverage_percentages(problem_folder, problem_name):
#     """Extracts coverage percentages from HTML reports."""
#     current_first_five_coverage_percentage = 0.0
#     current_total_coverage_percentage = 0.0
#
#     try:
#         with open(os.path.join(problem_folder, 'first_five_coverage', 'function_index.html'), 'r',
#                   encoding='utf-8') as file:
#             html_content_first_five = file.read()
#         first_five_success_percentage = extract_success_percentage(html_content_first_five, problem_name["entry_point"])
#         current_first_five_coverage_percentage = float(first_five_success_percentage.rstrip('%'))
#
#         with open(os.path.join(problem_folder, 'total_coverage', 'function_index.html'), 'r', encoding='utf-8') as file:
#             html_content_total = file.read()
#         total_success_percentage = extract_success_percentage(html_content_total, problem_name["entry_point"])
#         current_total_coverage_percentage = float(total_success_percentage.rstrip('%'))
#     except ValueError as e:
#         print(e)
#
#     return current_first_five_coverage_percentage, current_total_coverage_percentage
import os
import ast
import logging
import threading
import traceback
import json
import coverage
from io import StringIO
import runpy
from llm30.pipeline.QAagent.utils.extract_assert_block import extract_assert_blocks
from dotenv import load_dotenv

load_dotenv()

def _get_pipeline_logger():
    for name in ("SingleAgentLogger", "MultiAgentLogger"):
        logger = logging.getLogger(name)
        if logger.handlers:
            return logger
    return logging.getLogger(__name__)

_COVERAGE_LOCK = threading.Lock()


def _extract_line_and_branch_from_json(json_path):
    with open(json_path, "r", encoding="utf-8") as file:
        payload = json.load(file)

    totals = payload.get("totals", {})
    covered_lines = totals.get("covered_lines", 0)
    num_statements = totals.get("num_statements", 0)
    covered_branches = totals.get("covered_branches", 0)
    num_branches = totals.get("num_branches", 0)

    line_coverage = (covered_lines / num_statements * 100.0) if num_statements else 0.0
    # If there are no branches, coverage.py conceptually has no branch obligations.
    branch_coverage = (covered_branches / num_branches * 100.0) if num_branches else 100.0
    total_items = num_statements + num_branches
    mixed_coverage = (
        (covered_lines + covered_branches) / total_items * 100.0
        if total_items
        else 0.0
    )
    return line_coverage, branch_coverage, mixed_coverage

def get_coverage(code_string, test_string, problem_id, log_folder):
    logger = _get_pipeline_logger()

    # write code string to a file in the problem_id folder called temp_problem_id.py
    os.makedirs(os.path.join(log_folder, f'problem_{problem_id}', 'first_five_coverage'), exist_ok=True)
    os.makedirs(os.path.join(log_folder, f'problem_{problem_id}', 'total_coverage'), exist_ok=True)

    raw_blocks = extract_assert_blocks(test_string)

    # Drop assert blocks that produce invalid syntax when combined with the solution code.
    def _is_valid_block(test_code):
        try:
            ast.parse(code_string + "\n" + test_code)
        except SyntaxError:
            return False
        return True

    valid_blocks = [block for block in raw_blocks if _is_valid_block(block)]

    # Write the combined code and test string to separate files for full and first five tests
    with open(os.path.join(log_folder, f'problem_{problem_id}', 'total_coverage', 'total_coverage.py'), 'w') as f2:
        f2.write(code_string + "\n" + "\n".join(valid_blocks))

    # Select the first five assert blocks to avoid cutting a test mid-assert.
    if valid_blocks:
        first_five_tests = "\n".join(valid_blocks[:5])
    else:
        # Fallback to empty tests to avoid syntax errors.
        first_five_tests = ""

    with open(os.path.join(log_folder, f'problem_{problem_id}', 'first_five_coverage', 'first_five_coverage.py'), 'w') as f2:
        f2.write(code_string)
        f2.write("\n" + first_five_tests)

    # Coverage is not thread-safe; serialize coverage execution across workers.
    with _COVERAGE_LOCK:
        # Set up coverages (suppress stdout to reduce noise)
        import sys
        from io import StringIO as StdoutCapture

        branch_env = os.environ.get("COVERAGE_BRANCH")
        if branch_env is None:
            branch = True
        else:
            branch = branch_env.strip().lower() in {"1", "true", "yes", "on"}
        total_script = os.path.join(log_folder, f'problem_{problem_id}', 'total_coverage', 'total_coverage.py')
        first_five_script = os.path.join(log_folder, f'problem_{problem_id}', 'first_five_coverage', 'first_five_coverage.py')

        cov_total = coverage.Coverage(
            concurrency='thread',
            data_suffix=True,
            branch=branch,
            include=[total_script],
        )
        try:
            cov_total.start()
            # Suppress stdout during test execution
            old_stdout = sys.stdout
            sys.stdout = StdoutCapture()
            try:
                runpy.run_path(total_script)
            finally:
                sys.stdout = old_stdout
        except (AssertionError, Exception):
            logger.warning(
                f"Coverage test failure (total tests) for problem {problem_id}:\n{traceback.format_exc()}"
            )
        finally:
            cov_total.stop()
            cov_total.save()
            # Generate the coverage reports
            report_output_total = StringIO()
            try:
                cov_total.report(show_missing=True, file=report_output_total)
                cov_total.html_report(directory=os.path.join(log_folder, f'problem_{problem_id}', 'total_coverage'))
                cov_total.json_report(outfile=os.path.join(log_folder, f'problem_{problem_id}', 'total_coverage', 'coverage.json'))
            except coverage.exceptions.CoverageException as e:
                logger.warning(f"Coverage report failure (total tests) for problem {problem_id}: {e}")

            # Capture the coverage reports
            total_coverage_report = report_output_total.getvalue()
            cov_total.erase()

        # Set up coverages for first five tests
        cov_five = coverage.Coverage(
            concurrency='thread',
            data_suffix=True,
            branch=branch,
            include=[first_five_script],
        )
        cov_five.start()
        try:
            # Suppress stdout during test execution
            old_stdout = sys.stdout
            sys.stdout = StdoutCapture()
            try:
                runpy.run_path(first_five_script)
            finally:
                sys.stdout = old_stdout
        except (AssertionError, Exception):
            logger.warning(
                f"Coverage test failure (first five tests) for problem {problem_id}:\n{traceback.format_exc()}"
            )
        finally:
            cov_five.stop()
            cov_five.save()
            # Generate the coverage reports
            report_output_first_five = StringIO()
            try:
                cov_five.report(show_missing=True, file=report_output_first_five)
                cov_five.html_report(directory=os.path.join(log_folder, f'problem_{problem_id}', 'first_five_coverage'))
                cov_five.json_report(outfile=os.path.join(log_folder, f'problem_{problem_id}', 'first_five_coverage', 'coverage.json'))
            except coverage.exceptions.CoverageException as e:
                logger.warning(f"Coverage report failure (first five tests) for problem {problem_id}: {e}")

            # Capture the coverage reports
            first_five_coverage_report = report_output_first_five.getvalue()
            cov_five.erase()

    return first_five_coverage_report, total_coverage_report

def extract_line_and_branch_coverage_percentages(problem_folder):
    logger = _get_pipeline_logger()

    first_five_json = os.path.join(problem_folder, "first_five_coverage", "coverage.json")
    total_json = os.path.join(problem_folder, "total_coverage", "coverage.json")

    first_five_line = 0.0
    total_line = 0.0
    first_five_branch = 0.0
    total_branch = 0.0
    first_five_mixed = 0.0
    total_mixed = 0.0

    try:
        first_five_line, first_five_branch, first_five_mixed = _extract_line_and_branch_from_json(first_five_json)
        total_line, total_branch, total_mixed = _extract_line_and_branch_from_json(total_json)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        logger.warning(f"Line/branch coverage extraction failed for {problem_folder}: {e}")

    return (
        first_five_line,
        total_line,
        first_five_branch,
        total_branch,
        first_five_mixed,
        total_mixed,
    )
