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

Each agent follows the same two-stage pipeline as the collaborative approach: a code architect generates pseudocode using a specific reasoning strategy, followed by a test generator producing test cases. However, each agent pair operates independently without sharing information during generation. All agent outputs are evaluated against the canonical solution using coverage and accuracy metrics.

The final test suite is selected by ranking agents according to total line coverage as the primary criterion and test accuracy as a tiebreaker. This ensures the system delivers the most comprehensive and correct test suite from among all candidates. All intermediate results from competing agents are preserved for analysis.

This competitive architecture allows direct comparison of different reasoning strategies under identical conditions. By evaluating each approach independently, the system avoids potential quality degradation from merging incompatible test cases while ensuring delivery of the best-performing solution.

## Experiments

### Evaluation Metrics

Test quality is assessed using three complementary metrics that capture different aspects of test effectiveness:

**Coverage:** Line coverage percentage measures the proportion of source code lines executed during test execution. Coverage for both the first five generated tests and the complete test suite are reported.

**Accuracy:** Test accuracy is defined as the proportion of generated tests that pass when executed against the canonical solution. This metric validates that generated tests correctly specify expected behavior and do not contain false positives. Accuracy is computed by executing each test case individually and recording pass/fail outcomes.

**Tokens:** Average total token usage (Input + Output) provides insights into computational cost and efficiency of different strategies.

These metrics provide complementary perspectives: coverage measures thoroughness of test exploration, accuracy measures correctness of test specifications, and tokens measure resource efficiency. High-quality test suites achieve both comprehensive coverage and high accuracy while maintaining reasonable token usage.

### Experimental Setup

All experiments (single agent, multi agent cooperative, multi agent competitive, QAagent) are conducted on 20 functions selected from the HumanEval benchmark (average of 10 runs), then on the complete HumanEval benchmark (1 run).

For single-agent experiments, each problem is evaluated once with the baseline configuration. Multi-agent experiments generate multiple independent planning perspectives per problem, which are then either merged or evaluated competitively depending on the architecture being tested.

Prompt strategy:
- **single-agent**, available prompts are: 
  - **default** (assign role, task, rules, formatting rule, few-shots)
  - **zero-shot** (assign role, task, formatting rule)
  - **original** (assign role, task, formatting rule, few-shots)
- **multi-agent cooperative** and **multi-agent competitive**:
  - **Architect**: Chain-of-Thought with few-shots and zero-shot, and ReAct with few-shots
  - **Generator**: **default** (assign role, task, rules, formatting rule, few-shots) or **original** (assign role, task, formatting rule, few-shots)
- **QAagent**:
  - **Architect**: Chain-of-Thought (assign role, task, plan formatting, few-shots)
  - **Generator**: **default** (assign role, task, rules, formatting rule, few-shots) or **original** (assign role, task, formatting rule, few-shots)


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

| Strategy             | Variant             | Accuracy | Coverage |     Tokens |
| :------------------- | :------------------ | -------: | -------: | ---------: |
| QA Agent             | Default             |    97.65 |    99.40 | 106,228.40 |
| QA Agent             | Original            |    71.76 |    93.86 |  73,580.40 |
| QA Agent Competitive | Default             |    98.93 |    99.20 | 333,891.50 |
| QA Agent Competitive | Original            |    87.17 |    90.08 | 245,753.70 |
| QA Agent Merge       | Default (Accuracy)  |   100.00 |    99.39 | 333,524.30 |
| QA Agent Merge       | Default (Concat)    |    97.61 |    99.25 | 334,223.40 |
| QA Agent Merge       | Original (Accuracy) |    91.00 |    88.87 | 235,632.30 |
| QA Agent Merge       | Original (Concat)   |    72.94 |    93.58 | 241,940.20 |
| Single Agent         | Default             |    98.48 |    98.92 |  82,873.70 |
| Single Agent         | Original            |    78.89 |    84.66 |  49,949.10 |
| Single Agent         | Zero Shot           |    48.66 |    57.15 |  47,511.50 |

#### HumanEval - Full Dataset (164 Problems) (1 Run)

| Strategy             | Variant             | Accuracy | Coverage |       Tokens |
| :------------------- | :------------------ | -------: | -------: | -----------: |
| QA Agent             | Default             |    96.50 |    98.57 |   824,319.00 |
| QA Agent             | Original            |    82.77 |    95.43 |   586,740.00 |
| QA Agent Competitive | Default             |    96.92 |    97.92 | 2,564,180.00 |
| QA Agent Competitive | Original            |    93.17 |    97.31 | 1,822,078.00 |
| QA Agent Merge       | Default (Accuracy)  |    97.56 |    97.35 | 2,560,891.00 |
| QA Agent Merge       | Default (Concat)    |    95.41 |    98.27 | 2,575,158.00 |
| QA Agent Merge       | Original (Accuracy) |    96.95 |    96.62 | 1,890,739.00 |
| QA Agent Merge       | Original (Concat)   |    81.17 |    93.82 | 1,845,532.00 |
| Single Agent         | Default             |    97.24 |    98.77 |   641,483.00 |
| Single Agent         | Original            |    86.65 |    91.93 |   405,078.00 |
| Single Agent         | Zero Shot           |    60.61 |    68.11 |   362,462.00 |

### Observations & Conclusion
1.  **Prompt Engineering Matters**: Across all strategies, the "Default" (optimized) prompts consistently outperforms "Original" and "Zero Shot" prompts. Zero Shot performance is significantly lower, highlighting the importance of few-shot examples or better instructions. **Prompt engineering is as important as strategy selection.** A well-designed prompt with explicit rules and examples can improve accuracy by 20-50%. 
2.  **High Accuracy in Selected Subset**: The **QA Agent Merge (Default, Accuracy)** strategy achieves a perfect **100% accuracy** on the 20-problem subset and 97.56% on full dataset, demonstrating exceptional reliability on this curated set.
3. **Best coverage**: QA Agent default on 20 selected (99.40%) and Single Agent default on full (98.77%).
4. **Competitive vs. Efficient**:
    *   **Single Agent (Default)** is highly efficient (lowest token usage among high performers) while maintaining very high accuracy (97.24% on full dataset), making it a strong candidate for resource-constrained environments.
    *   **QA Agent Competitive** and **Merge** strategies offer slight accuracy gains (reaching 97.56%) but at a substantial cost in token usage (approx. 3-4x more tokens than Single Agent).
5. **Cost-Benefit Analysis**: For most general use cases, the **Single Agent (Default)** strategy provides the best balance of performance and cost. However, for critical tasks where every percentage point of accuracy counts, **QA Agent Merge (Accuracy)** is the superior choice.

## Project Organization

```
├── LICENSE            <- Open-source license if one is chosen
├── Makefile           <- Makefile with convenience commands like `make data` or `make train`
├── README.md          <- The top-level README for developers using this project.
├── data
│   ├── external       <- Data from third party sources.
│   ├── interim        <- Intermediate data that has been transformed.
│   ├── processed      <- The final, canonical data sets for modeling.
│   └── raw            <- The original, immutable data dump.
│
├── docs               <- MkDocs project for documentation
│
├── models             <- Trained and serialized models, model predictions, or model summaries
│
├── notebooks          <- Jupyter notebooks. Naming convention is a number (for ordering),
│                         the creator's initials, and a short `-` delimited description, e.g.
│                         `1.0-jqp-initial-data-exploration`.
│
├── pyproject.toml     <- Project configuration file with package metadata for 
│                         llm30 and configuration for tools like ruff
│
├── references         <- Data dictionaries, manuals, and all other explanatory materials.
│
├── reports            <- Generated analysis as HTML, PDF, LaTeX, etc.
│   └── figures        <- Generated graphics and figures to be used in reporting
│
├── requirements.txt   <- The requirements file for reproducing the analysis environment, e.g.
│                         generated with `pip freeze > requirements.txt`
│
├── tests              <- Unit tests and fixtures for the project
│
├── adsp               <- Legacy template module retained for reference
│
└── llm30   <- Primary source code for use in this project.
    │
    ├── __init__.py             <- Makes llm30 a Python module
    │
    ├── config.py               <- Store useful variables and configuration
    │
    ├── dataset.py              <- Scripts to download or generate data
    │
    ├── features.py             <- Code to create features for modeling
    │
    ├── modeling                
    │   ├── __init__.py 
    │   ├── predict.py          <- Code to run model inference with trained models          
    │   └── train.py            <- Code to train models
    │
    └── plots.py                <- Code to create visualizations
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
