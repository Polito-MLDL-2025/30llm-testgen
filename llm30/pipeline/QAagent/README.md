# QAagent: Collaborative and Competitive Architectures

This folder contains the implementation of two distinct agent-based approaches for automatic test generation and evaluation: **Collaborative Pattern** and **Competitive Pattern**. Both approaches leverage multiple agent pipelines ("code architect" + "test generator" pairs), but differ in how their outputs are combined and evaluated.

## Test Generator Prompt Types

- **Basic Prompt:** The test generator agent receives only the function header, the comment describing the function’s goal, and the generated pseudocode. This approach allows the LLM to generate tests based on minimal context.
- **Guided Prompt:** The test generator agent receives, in addition to the basic information, a set of explicit rules and instructions designed to guide the LLM in producing more correct and robust tests. The guided prompt helps cover edge cases and avoid common mistakes.

## 1. Collaborative Pattern

In the collaborative approach, all three agent pipelines are run independently on each problem. Each pipeline consists of a code architect agent (which generates a plan/pseudocode) and a test generator agent (which generates tests based on the plan, using either a basic or guided prompt). After all three pipelines have produced their outputs, their generated tests are **merged** into a single, unified test suite for the problem.

### Merge Strategies (Collaborative Pattern)

After all agent pipelines have generated their test suites, a merger agent combines them into a single, unified test suite. Three merging strategies are available:
1. **Concatenation:** All tests are concatenated, filtering out only None or empty entries.
2. **Enhanced Concatenation:** Tests are concatenated and further filtered to remove syntax errors, duplicate tests (using AST analysis), and tests with incorrect function names.
3. **LLM-based Merge:** Tests are concatenated and then refined by an LLM, which removes duplicates, conflicting tests, syntax errors, and failing tests, using the function header, goal, and generated plans as context.

Plans are always concatenated after removing None or empty ones.

- **Workflow:**
  1. For each problem, run all three (code architect + test generator) pipelines.
  2. Collect the generated tests from each pipeline.
  3. Merge the tests into a single comprehensive test suite using one of the merge strategies above.
  4. Evaluate the merged test suite for coverage and accuracy against the canonical solution.
- **Rationale:**
  - The collaborative approach aims to maximize test coverage and robustness by leveraging the diversity of multiple agent pipelines and merging strategies.
  - Merging tests can uncover more edge cases and improve the overall quality of the generated test suite.
  - This approach is especially useful when individual pipelines have complementary strengths.

## 2. Competitive Pattern

In the competitive approach, all three agent pipelines are also run independently on each problem. Each pipeline consists of a code architect agent and a test generator agent, which can use either a basic or guided prompt. However, instead of merging their outputs, each pipeline's results are **evaluated separately**. The pipeline that achieves the best evaluation metric (e.g., highest coverage, then highest accuracy as a tiebreaker) is selected as the winner for that problem.

- **Workflow:**
  1. For each problem, run all three (code architect + test generator) pipelines.
  2. Evaluate each pipeline's generated tests independently.
  3. Log and save all results for each pipeline, as well as the selected best.
  4. The final test suite and plan are those from the agent with the highest coverage (and accuracy as a tiebreaker).

- **Rationale:**
  - The competitive approach is designed to identify the single best-performing pipeline for each problem, leveraging the diversity of prompt strategies.
  - It is useful for benchmarking, ablation studies, or when you want to select the most effective agent configuration.
  - This approach highlights the strengths and weaknesses of each pipeline in isolation and ensures that only the most effective test suite is retained.

## Key Differences

| Aspect         | Collaborative (Merged)         | Competitive                |
|----------------|-------------------------------|----------------------------|
| Output         | Merged test suite (all agents) | Best single pipeline's tests|
| Evaluation     | On merged tests                | On each pipeline separately|
| Goal           | Maximize overall coverage      | Find best individual agent |
| Use Case       | Robustness, completeness       | Benchmarking, selection    |

## Folder Structure

- `QAagent.py`           — Implements the collaborative pattern logic.
- `QAagent_competitive.py` — Implements the competitive pattern logic.
- `agents/`               — Agent definitions (code architect, test generator).
- `tools/`                — Utility scripts for running and evaluating agents.
- `utils/`                — Helper functions for logging, coverage, accuracy, etc.
- `prompts/`              — Prompt templates for each agent and dataset.

## Collaborative vs Competitive: Results Comparison

*This section will be completed once experimental results are available.*

- Here, we will present a quantitative and qualitative comparison between the collaborative and competitive patterns.
- Metrics such as coverage, accuracy, and robustness will be analyzed.
- Insights and recommendations will be provided based on the observed results.

## Log Directory Structure

Both collaborative and competitive pipelines generate detailed logs and results for each problem. The log directory is organized as follows:

```
logs/
  QAagent-<timestamp>/                # Collaborative run logs
    problem_<id>/                     # Folder for each problem
      pseudocode.txt                  # Plan/pseudocode used
      generated_tests.txt             # Generated tests (merged in collaborative)
      metrics.txt                     # Main metrics (coverage, accuracy, tokens)
      first_five_coverage_report.txt  # Detailed coverage report (first 5 tests)
      total_coverage_report.txt       # Detailed total coverage report
      test_results.txt                # Test execution results
    summary.txt                       # Summary of all problems
    QAagent.log                       # Main log file
    errors.txt                        # Errors encountered (if any)

  QAagent_competitive-<timestamp>/    # Competitive run logs
    problem_<id>/
      agent_1/                        # Results for agent pipeline 1
        pseudocode.txt
        generated_tests.txt
        metrics.txt
        first_five_coverage_report.txt
        total_coverage_report.txt
        test_results.txt
      agent_2/                        # Results for agent pipeline 2
        ...
      agent_3/                        # Results for agent pipeline 3
        ...
      pseudocode.txt                  # Best agent's plan
      generated_tests.txt             # Best agent's tests
      metrics.txt                     # Best agent's metrics
      first_five_coverage_report.txt  # Best agent's coverage report
      total_coverage_report.txt       # Best agent's total coverage
      test_results.txt                # Best agent's test results
    summary.txt                       # Summary of all problems
    QAagent_competitive.log           # Main log file
    errors.txt                        # Errors encountered (if any)
```

- Each problem has its own folder with all relevant outputs and metrics.
- In the competitive pipeline, each agent's results are saved separately, as well as the best agent's outputs at the problem root.
- The collaborative pipeline saves the merged results for each problem.
- Summary and log files are provided at the run root for quick overview and debugging.

## Notes
- Both approaches use the same three agent pipelines for a fair comparison.
- All intermediate and final results (plans, tests, metrics) are saved for each problem and pipeline.
- The collaborative approach assumes a merging strategy is implemented (e.g., union of tests, deduplication, etc.).
- For further details, see the code and docstrings in each script.

---

**Contact:** For questions or contributions, open an issue or contact the maintainer.
