from io import StringIO

from llm30.pipeline.QAagent.utils.extract_assert_block import extract_assert_blocks


def get_accuracy(canonical_solution, tests, log_folder, problem_id):
    test_result = StringIO()
    passed_tests = 0
    total_tests = 0

    exec(canonical_solution, globals())

    for test in extract_assert_blocks(tests):
        total_tests += 1

        try:
            exec(test, globals())
            passed_tests += 1
        except AssertionError:
            test_result.write(f"Test failed: {test}\n")
        except Exception as e:
            test_result.write(f"An error occurred during test '{test}': {str(e)}\n")

    accuracy = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
    test_result.write(f"\nPassed {passed_tests}/{total_tests} tests ({accuracy:.2f}%)\n")

    return accuracy, test_result.getvalue()
