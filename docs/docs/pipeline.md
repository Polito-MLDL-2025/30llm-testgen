# QAagent Pipeline

The QAagent pipeline runs the end-to-end flow for test generation and evaluation: it drafts a
pseudocode plan, generates tests, then scores those tests against the canonical solution.

## Workflow

For each problem in the dataset:

1. **Plan generation**: The Code Architect agent converts the prompt into natural-language
   pseudocode.
2. **Test generation**: The Test Generator agent produces tests from the prompt + pseudocode.
3. **Evaluation**: Coverage and accuracy are computed against the canonical solution.

## Inputs

- **Datasets**: `llm30/pipeline/datasets/{humaneval,mbpp}/problems.jsonl`
- **Prompts**: `llm30/pipeline/prompts/v1/*.txt`
- **Models**: `--model` is passed to the OpenAI chat client.

Environment variables (set in your shell or `.env`):

- `OPENAI_API_KEY`
- `OPENAI_URL_BASE`

## Run

From the repository root:

```bash
python llm30/pipeline/QAagent/QAagent.py --dataset humaneval --model gpt-4o
```

Options:

- `--dataset`: `humaneval` or `mbpp`
- `--model`: model name passed to the OpenAI client

## Outputs

Each run creates a timestamped folder under `logs/`, for example:

- `logs/QAagent-YYYY-MM-DD_HH-MM-SS/QAagent.log`
- `logs/QAagent-YYYY-MM-DD_HH-MM-SS/summary.txt`
- `logs/QAagent-YYYY-MM-DD_HH-MM-SS/details.txt`
- `logs/QAagent-YYYY-MM-DD_HH-MM-SS/problem_<task_id>/pseudocode.txt`
- `logs/QAagent-YYYY-MM-DD_HH-MM-SS/problem_<task_id>/generated_tests.txt`
- `logs/QAagent-YYYY-MM-DD_HH-MM-SS/problem_<task_id>/test_results_accuracy.txt`
- `logs/QAagent-YYYY-MM-DD_HH-MM-SS/problem_<task_id>/first_five_coverage_report.txt`
- `logs/QAagent-YYYY-MM-DD_HH-MM-SS/problem_<task_id>/total_coverage_report.txt`

Coverage HTML reports are saved under each problem folder in `first_five_coverage/` and
`total_coverage/`.

## Customize

- Adjust concurrency and dataset slicing in `llm30/pipeline/QAagent/QAagent.py`.
- Edit prompt paths in `llm30/pipeline/QAagent/QAagent.py` to point at new templates.
- Extend or replace evaluation logic in `llm30/pipeline/QAagent/utils/coverage.py` and
  `llm30/pipeline/QAagent/utils/accuracy.py`.
