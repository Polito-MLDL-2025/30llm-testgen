# 30llm: Multi-Agent LLM Systems for Collaborative Test Case Generation

<a target="_blank" href="https://cookiecutter-data-science.drivendata.org/">
    <img src="https://img.shields.io/badge/CCDS-Project%20template-328F97?logo=cookiecutter" />
</a>

This project investigates how Large Language Model (LLM) agents can be used to automatically
generate high-quality software test cases. Traditional automated testing tools struggle with tasks
that require multi-perspective reasoning—such as understanding user intent, exploring edge cases, or
applying domain knowledge. In contrast, multi-agent LLM architectures enable multiple specialized
agents to collaborate, debate, or compete to produce more comprehensive test artefacts.

## Main Goal

The primary goal of this project is to determine whether multi-agent LLM systems can outperform
single-agent or traditional methods in generating comprehensive, diverse, and effective test cases.

This project builds upon the [QAagent framework](https://github.com/AkhilDeo/QAagent), a multi-agent system designed for unit test generation through natural language pseudocode. The original QAagent approach employs a two-stage pipeline where a code architect agent first generates an implementation plan in natural language and pseudocode, followed by a test generator agent that produces test cases based on this plan. This separation of concerns allows different perspectives to be incorporated into the test generation process, demonstrating superior performance on the HumanEval benchmark.

This framework is adapted and extended by modifying the prompting strategies and introducing additional interaction mechanisms to better suit function-level test generation. The modifications include support for different reasoning styles in the planning phase and multiple strategies for combining outputs from multiple agents, enabling systematic comparison of collaborative versus competitive multi-agent architectures.

## Methodology

This project evaluates three distinct approaches to LLM-based test generation, progressing from simple single-agent baselines to sophisticated multi-agent architectures and compares them with QAagent framework.

### Single Agent

The single-agent approach serves as a baseline, generating test cases directly from the problem description in a single inference pass.
This approach is computationally efficient, requiring only a single model invocation per problem with minimal token usage. However, it is inherently limited by single-perspective reasoning and may underrepresent challenging edge cases or uncommon execution paths, motivating the exploration of multi-agent alternatives.

### Multi-Agent Collaborative

The collaborative multi-agent system separates test generation into distinct planning and execution phases, mimicking real-world software development workflows.

The system operates through a linear pipeline where three code architect agents independently analyze each problem and generate natural language pseudocode describing likely implementations. Each architect employs a different reasoning strategy—Chain-of-Thought with few-shots and zero-shot, and ReAct with few-shots—to maximize diversity in the generated plans. These plans are then consolidated and provided to a test generator agent, which produces comprehensive test suites covering both basic functionality and edge cases.

After test generation, a merger agent reconciles outputs using one of two strategies. The **concat** strategy performs basic concatenation of all generated tests after removing empty entries. The **accuracy** strategy extend **concat** strategy by adding validations like filtering tests with syntax errors, AST-based deduplication, filtering of tests with incorrect function names, and retaining only those that pass successfully by executing them against the canonical solution.

This architecture enables complementary reasoning strategies to be combined, potentially improving coverage and robustness on complex functions. The separation of planning and testing roles allows each agent to focus on its specialized task, while the merge phase ensures coherent final test suites.

### Multi-Agent Competitive

The competitive multi-agent approach generates complete test suites independently from each agent configuration and selects the highest-quality output. Rather than combining outputs, agents compete to produce the best solution.

Each agent follows the same two-stage pipeline as the collaborative approach: a code architect generates pseudocode using a specific reasoning strategy, followed by a test generator producing test cases. However, each agent pair operates independently without sharing information during generation. All agent outputs are evaluated against the canonical solution using coverage and execution success rate metrics.

The final test suite is selected by ranking agents according to total line coverage as the primary criterion and test execution success rate as a tiebreaker. This ensures the system delivers the most comprehensive and correct test suite from among all candidates. All intermediate results from competing agents are preserved for analysis.

This competitive architecture allows direct comparison of different reasoning strategies under identical conditions. By evaluating each approach independently, the system avoids potential quality degradation from merging incompatible test cases while ensuring delivery of the best-performing solution.

## Experiments

### Evaluation Metrics

Test quality is assessed using three complementary metrics that capture different aspects of test effectiveness:

**Coverage:** Line coverage percentage measures the proportion of source code lines executed during test execution. Coverage for both the first five generated tests and the complete test suite are reported.

**Execution Success Rate:** Test execution success rate is defined as the proportion of generated tests that pass when executed against the canonical solution. This metric validates that generated tests correctly specify expected behavior and do not contain false positives. Execution success rate is computed by executing each test case individually and recording pass/fail outcomes.

**Tokens:** Average total token usage (Input + Output) provides insights into computational cost and efficiency of different strategies.

These metrics provide complementary perspectives: coverage measures thoroughness of test exploration, accuracy measures correctness of test specifications, and tokens measure resource efficiency. High-quality test suites achieve both comprehensive coverage and high accuracy while maintaining reasonable token usage.

### Experimental Setup

All experiments (single agent, multi agent cooperative, multi agent competitive, QAagent) are conducted on 20 functions selected from the HumanEval benchmark (average of 10 runs), then on the complete HumanEval benchmark (1 run).

For single-agent experiments, each problem is evaluated once with the baseline configuration. Multi-agent experiments generate multiple independent planning perspectives per problem, which are then either merged or evaluated competitively depending on the architecture being tested.

Prompt strategy:
- **Single-Agent**, available prompts are: 
  - **Augmented Few-Shot** (assign role, task, rules, formatting rule, few-shots)
  - **Zero-Shot** (assign role, task, formatting rule)
  - **original** (assign role, task, formatting rule, few-shots)
- **Multi-Agent cooperative** and **Multi-Agent competitive**:
  - **Architect**: Chain-of-Thought with few-shots and zero-shot, and ReAct with few-shots
  - **Generator**: **Augmented Few-Shot** (assign role, task, rules, formatting rule, few-shots) or **Standard Few-Shot** (assign role, task, formatting rule, few-shots)
- **QAagent**:
  - **Architect**: Chain-of-Thought (assign role, task, plan formatting, few-shots)
  - **Generator**: **Augmented Few-Shot** (assign role, task, rules, formatting rule, few-shots) or **Standard Few-Shot** (assign role, task, formatting rule, few-shots)


### Model Choice

Model selected for these experiments is **nvidia/nemotron-3-nano-30b-a3b** because:
* Using a single fixed model isolates the impact of strategy and prompt changes, making comparisons fairer.

Strengths highlighted in the model card:
* Open model family with open weights, training data, and recipes.
* Hybrid MoE architecture (Mamba-2 + attention) with 3.5B active parameters and 30B total parameters, favoring efficiency.
* Unified reasoning and non-reasoning model with configurable reasoning traces (accuracy vs. direct-answer trade-off).
* Long-context support: model card notes up to a 1M context size (HF default 256k due to VRAM needs).
* Fine-tuned for code, math, science, tool calling, instruction following, and structured outputs.
* Multilingual support (English, German, Spanish, French, Italian, Japanese) and marked as ready for commercial use.

All experiments use consistent decoding parameters (temperature, top-p) across configurations to isolate the effects of architectural choices.

### Results

#### HumanEval - 20 Selected Problems (Average of 10 Runs)

| Strategy                               | Prompt                    | Execution Success Rate | Coverage | Tokens/Problem |
| :------------------------------------- | :------------------------ | ---------------------: | -------: | -------------: |
| Single Agent                           | Zero Shot (Baseline)      |                  61.55 |    68.03 |       2,372.58 |
| Single Agent                           | Standard Few-Shot         |                  88.38 |    96.57 |       2,287.66 |
| QA Agent                               | Standard Few-Shot         |                  88.47 |    97.17 |       3,651.18 |
| Multi-Agent Competitive (LLM scorer)   | Standard Few-Shot         |                  93.94 |    98.12 |      19,047.33 |
| Multi-Agent Competitive (LLM selector) | Standard Few-Shot         |                  93.07 |    98.04 |      17,783.04 |
| Multi-Agent Merge (Accuracy)           | Standard Few-Shot         |                  86.59 |    91.78 |      12,278.32 |
| Multi-Agent Merge (Concat)             | Standard Few-Shot         |                  90.09 |    97.05 |      12,183.05 |
| Multi-Agent Merge (LLM)                | Standard Few-Shot         |                  90.86 |    98.76 |      21,144.74 |
| Multi-Agent Merge (LLM-Multi-Steps)    | Standard Few-Shot         |                  93.73 |    97.69 |      34,127.11 |
| Single Agent                           | Rule-Augmented Few-Shot   |                  98.00 |    98.44 |       4,143.58 |
| Multi-Agent                            | Rule-Augmented Few-Shot   |                  98.36 |    99.25 |       5,404.83 |
| Multi-Agent Competitive (LLM scorer)   | Rule-Augmented Few-Shot   |                  98.15 |    98.96 |      23,382.68 |
| Multi-Agent Competitive (LLM selector) | Rule-Augmented Few-Shot   |                  97.55 |    99.11 |      22,155.49 |
| Multi-Agent Merge (Accuracy)           | Rule-Augmented Few-Shot   |                  96.57 |    99.23 |      17,386.96 |
| Multi-Agent Merge (Concat)             | Rule-Augmented Few-Shot   |                  96.96 |    99.34 |      17,666.72 |
| Multi-Agent Merge (LLM)                | Rule-Augmented Few-Shot   |                  96.50 |    99.19 |      24,080.56 |

#### HumanEval - Full Dataset (164 Problems) (1 Run)

| Strategy                               | Prompt                    | Execution Success Rate | Coverage | Tokens/Problem |
| :------------------------------------- | :------------------------ | ---------------------: | -------: | -------------: |
| Single Agent                           | Zero Shot (Baseline)      |                  62.76 |    69.61 |       2,241.52 |
| Single Agent                           | Standard Few-Shot         |                  90.48 |    96.01 |       2,194.08 |
| QA Agent                               | Standard Few-Shot         |                  90.58 |    97.66 |       3,437.36 |
| Multi-Agent Competitive (LLM scorer)   | Standard Few-Shot         |                  92.64 |    98.41 |      18,181.55 |
| Multi-Agent Competitive (LLM selector) | Standard Few-Shot         |                  94.03 |    98.96 |      17,168.58 |
| Multi-Agent Merge (Accuracy)           | Standard Few-Shot         |                  90.23 |    96.98 |      11,247.51 |
| Multi-Agent Merge (Concat)             | Standard Few-Shot         |                  89.43 |    97.72 |      11,517.63 |
| Multi-Agent Merge (LLM)                | Standard Few-Shot         |                  92.18 |    98.94 |      20,502.63 |
| Single Agent                           | Rule-Augmented Few-Shot   |                  97.31 |    98.83 |       3,873.74 |
| Multi-Agent                            | Rule-Augmented Few-Shot   |                  96.45 |    98.97 |       5,294.81 |
| Multi-Agent Competitive (LLM scorer)   | Rule-Augmented Few-Shot   |                  97.25 |    99.62 |      22,125.34 |
| Multi-Agent Competitive (LLM selector) | Rule-Augmented Few-Shot   |                  97.15 |    99.75 |      21,573.32 |
| Multi-Agent Merge (Accuracy)           | Rule-Augmented Few-Shot   |                  96.23 |    99.03 |      16,547.70 |
| Multi-Agent Merge (Concat)             | Rule-Augmented Few-Shot   |                  96.55 |    99.65 |      16,874.83 |
| Multi-Agent Merge (LLM)                | Rule-Augmented Few-Shot   |                  96.25 |    99.55 |      23,436.51 |

#### HumanEval - Full Dataset (164 Problems) (10 Runs)
| Strategy                               | Prompt                    | Execution Success Rate | Coverage | Tokens/Problem |
| :------------------------------------- | :------------------------ |-----------------------:|---------:|---------------:|
| Single Agent                           | Zero Shot (Baseline)      |                  62.17 |    68.00 |       2,149.84 |
| Single Agent                           | Standard Few-Shot         |                  91.11 |    95.94 |       2,400.29 |
| QA Agent                               | Standard Few-Shot         |                  88.65 |    96.12 |       3,521.80 |
| Multi-Agent Competitive (LLM scorer)   | Standard Few-Shot         |                  93.02 |    97.83 |      17,584.13 |
| Multi-Agent Competitive (LLM selector) | Standard Few-Shot         |                  92.51 |    98.39 |      16,968.47 |
| Multi-Agent Merge (Accuracy)           | Standard Few-Shot         |                  91.50 |    96.99 |      11,672.22 |
| Multi-Agent Merge (Concat)             | Standard Few-Shot         |                  89.78 |    96.29 |      11,609.57 |
| Multi-Agent Merge (LLM)                | Standard Few-Shot         |                  91.96 |    97.65 |      20,432.18 |
| Single Agent                           | Rule-Augmented Few-Shot   |                  96.98 |    99.06 |       3,843.29 |
| Multi-Agent                            | Rule-Augmented Few-Shot   |                  96.42 |    98.98 |       5,140.45 |
| Multi-Agent Competitive (LLM scorer)   | Rule-Augmented Few-Shot   |                  96.89 |    99.25 |      21,635.40 |
| Multi-Agent Competitive (LLM selector) | Rule-Augmented Few-Shot   |                  96.37 |    99.37 |      21,154.44 |
| Multi-Agent Merge (Accuracy)           | Rule-Augmented Few-Shot   |                  96.28 |    99.54 |      16,279.48 |
| Multi-Agent Merge (Concat)             | Rule-Augmented Few-Shot   |                  96.41 |    99.54 |      16,197.11 |
| Multi-Agent Merge (LLM)                | Rule-Augmented Few-Shot   |                  96.12 |    99.46 |      23,078.21 |


### Observations & Conclusion
1.  **Prompt Engineering Matters**: Across all strategies, **Rule-Augmented Few-Shot** consistently outperforms **Standard Few-Shot** and **Zero Shot**, confirming that prompt quality remains a major driver of both execution success and coverage.
2.  **Best Execution Success Rate**: On the 20-problem subset, **Multi-Agent (Rule-Augmented Few-Shot)** reaches **98.36%**; on the full dataset, **Single Agent (Rule-Augmented Few-Shot)** achieves **97.31%**.
3.  **Best Coverage**: On the 20-problem subset, **Multi-Agent Merge (Concat, Rule-Augmented Few-Shot)** reaches **99.34%** coverage; on the full dataset, **Multi-Agent Competitive (LLM selector, Rule-Augmented Few-Shot)** reaches **99.75%**.
4.  **Competitive vs. Efficient**:
    *   **Single Agent** variants remain the most token-efficient and still deliver strong performance.
    *   **Multi-Agent** competitive/merge variants can improve peak metrics, but usually require significantly higher token budgets.
5.  **Cost-Benefit Analysis**: For most practical workloads, **Single Agent (Rule-Augmented Few-Shot)** provides the strongest balance of quality and compute cost, while multi-agent variants are more suitable when maximizing top-end quality is worth the additional tokens.

## Running Experiment Scripts

### 1) Environment setup
Create a virtual environment, install dependencies, and set your API key:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Set environment variables (or create a `.env` file in the project root with the same keys):

```bash
export OPENAI_API_KEY="sk-your-key"
# Optional: custom OpenAI-compatible endpoint
export OPENAI_URL_BASE="https://your-openai-compatible-base-url"
```

Optional model override env vars for QAagent pipelines (`QAagent.py`, `QAagent_merge.py`, `QAagent_competitive.py`):

```bash
# Shared override for all QAagent stages
export QAAGENT_MODEL="meta/llama3-8b-instruct"

# Stage-specific overrides
export QAAGENT_PLAN_MODEL="meta/llama3-8b-instruct"
export QAAGENT_TEST_MODEL="meta/llama3-8b-instruct"
export QAAGENT_JUDGE_MODEL="meta/llama3-8b-instruct"
export QAAGENT_MERGE_MODEL="meta/llama3-8b-instruct"

# Backward-compatible shared fallback
export OPENAI_API_MODEL="meta/llama3-8b-instruct"
```

Model selection priority:
- Plan model: CLI `--qaagent-plan-model` -> CLI `--qaagent-model` -> CLI `--model` -> env `QAAGENT_PLAN_MODEL` -> env `QAAGENT_MODEL` -> env `OPENAI_API_MODEL` -> built-in default (`meta/llama3-8b-instruct`)
- Test model: CLI `--qaagent-test-model` -> CLI `--qaagent-model` -> CLI `--model` -> env `QAAGENT_TEST_MODEL` -> env `QAAGENT_MODEL` -> env `OPENAI_API_MODEL`
- Judge model (competitive): CLI `--qaagent-judge-model` -> CLI `--qaagent-model` -> CLI `--model` -> env `QAAGENT_JUDGE_MODEL` -> env `QAAGENT_MODEL` -> env `OPENAI_API_MODEL` -> resolved test model
- Merge model (merge pipeline): CLI `--qaagent-merge-model` -> CLI `--qaagent-model` -> CLI `--model` -> env `QAAGENT_MERGE_MODEL` -> env `QAAGENT_MODEL` -> env `OPENAI_API_MODEL` -> resolved test model

### 2) Run scripts
All experiment runners live in `scripts/`.

```bash
# HumanEval curated subset (20 selected problems, averaged over 10 runs)
python scripts/run_all.py \
  --dataset humaneval \
  --dataset-path llm30/pipeline/datasets/humaneval/problems_selected.jsonl \
  --model nvidia/nemotron-3-nano-30b-a3b \
  --runs 10 \
  --max-tasks 20 \
  --max-workers 4

# HumanEval full dataset (164 problems, single run)
python scripts/run_all.py \
  --dataset humaneval \
  --dataset-path llm30/pipeline/datasets/humaneval/problems_original.jsonl \
  --model nvidia/nemotron-3-nano-30b-a3b \
  --runs 1 \
  --max-tasks 164 \
  --max-workers 4
```

Available scripts:
- `scripts/run_all.py`
- `scripts/run_qaagent_10x.py`
- `scripts/run_qaagent_competitive_10x.py`
- `scripts/run_qaagent_merge_10x.py`
- `scripts/run_singleagent_10x.py`

Outputs are written to `logs/` as CSVs. For full argument lists, output naming, and runtime estimates, see `scripts/README.md`.

## Project Organization

```
30llm/
├── llm30/              <- Core Python package and multi-agent pipelines
├── scripts/            <- Experiment runners and orchestration utilities
├── data/               <- Dataset assets and data artifacts
├── logs/               <- Generated run logs and CSV summaries
├── report/             <- Experiment reports and result summaries
├── docs/               <- Documentation sources
├── tests/              <- Test suite
├── notebooks/          <- Exploratory analysis notebooks
├── models/             <- Model artifacts
├── references/         <- External references and notes
├── temp/               <- Temporary workspace files
├── README.md           <- Project overview and usage
├── pyproject.toml      <- Project and tooling configuration
├── requirements.txt    <- Python dependencies
├── Makefile            <- Convenience commands
└── LICENSE             <- Project license
```

--------


## How to contribute

### **Commit Message and Branch Naming Rules**

1. **Commit Message Format**
    - Use the following format for commit messages:
      ```
      <type>: <short description>
      ```
    - **Types**:
      - `feature` or`feat`: A new feature
      - `fix`: A bug fix
      - `docs`: Documentation changes
      - `chore`: maintenance tasks, repo setup, config, etc.
      - `style`: Code style changes (formatting, missing semicolons, etc.)
      - `refactor`: Code refactoring without adding features or fixing bugs
      - `test`: adding or updating tests.
    - Example:
      ```
      feat: add data preprocessing pipeline
      fix: resolve issue with model training script
      ```
    - Details: [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) 

2. **Branch Naming Convention**
    - Use the following format for branch names:
      ```
      <type>/<short-description>
      ```
    - **Types**:
      - `main` or `master`: Stable, production-ready code
      - `develop`: Integration branch for features before release (optional)
      - `feature` or `feat`: For new features or enhancements
      - `fix`: For bug fixes
      - `hotfix`: For urgent production fixes
      - `chore`: For maintenance, build, or config tasks
      - `docs`: For documentation-only changes
      - `refactor`: For code refactoring without behavior change
      - `test`: For adding or updating tests
      - `release`: For preparing production releases
    - Example:
     ```
     feat/add-preprocessing-pipeline
     fix/model-training-bug
     ```
    - Details: [Git Branch Naming Convention](https://conventional-branch.github.io/#specification)
    
    - Branch Flow:
    ```
    main <--- release <--- develop <--- feature
     ^                         |
     |                         |
     └-------- hotfix ---------┘
   ```
### **Jupyter Notebook Usage**

1. **Notebook Organization**
    - Notebooks must be stored in the `notebooks/` directory.
    - Naming convention: `PHASE.NOTEBOOK-INITIALS-DESCRIPTION.ipynb`
        
        Example: `0.01-pjb-data-source-1.ipynb`
        
        - `PHASE` codes:
            - `0` – Data exploration
            - `1` – Data cleaning & feature engineering
            - `2` – Visualization
            - `3` – Modeling
            - `4` – Publication
        - `INITIALS` – Your initials; helps identify the author and avoid conflicts.
        - `DESCRIPTION` – Short, clear description of the notebook's purpose.

### **Code Reusability & Refactoring Regulation**

1. **Refactor Shared Code into Modules**
    - Store reusable code in the `src/` package.
    - Add the following cell at the top of each notebook:

    ```python
    %load_ext autoreload
    %autoreload 2
    ```
