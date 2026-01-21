# Quick Start

Get started in under 5 minutes!

## Setup

```bash
# 1. Install
pip install -r requirements.txt

# 2. Set API key
export OPENAI_API_KEY="sk-your-api-key"

# 3. Run
python llm30/pipeline/SingleAgent/SingleAgent.py --dataset humaneval --max-tasks 3
```

**Windows**: Use `set OPENAI_API_KEY=sk-your-key` (CMD) or `$env:OPENAI_API_KEY="sk-your-key"` (PowerShell)

## Output

```
============================================================
Single Agent Test Case Generation Pipeline
============================================================
[1/3] HumanEval/0          | Accuracy:  87.5% | Coverage: 100.0%→100.0% | Tokens: 1052+627
[2/3] HumanEval/1          | Accuracy:  92.3% | Coverage: 100.0%→100.0% | Tokens: 1042+636
[3/3] HumanEval/2          | Accuracy:  57.1% | Coverage: 100.0%→100.0% | Tokens: 1011+323
============================================================
Single Agent Pipeline Completed!
============================================================
Average accuracy: 79.00%
Results saved to: logs/single_agent-humaneval-gpt-4o-20260107_213045
```

## Usage Examples

```bash
# Different dataset
python llm30/pipeline/SingleAgent/SingleAgent.py --dataset mbpp --max-tasks 5

# Different model
python llm30/pipeline/SingleAgent/SingleAgent.py --dataset humaneval --model gpt-3.5-turbo --max-tasks 10

# More workers (faster)
python llm30/pipeline/SingleAgent/SingleAgent.py --dataset humaneval --max-workers 4 --max-tasks 20

# Full dataset (164 problems)
python llm30/pipeline/SingleAgent/SingleAgent.py --dataset humaneval
```

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--dataset` | `humaneval` | Dataset: `humaneval` or `mbpp` |
| `--model` | `gpt-4o` | LLM model to use |
| `--max-tasks` | All | Number of problems to process |
| `--max-workers` | `2` | Parallel workers (increase for speed) |

## Results

Results saved to `logs/single_agent-{dataset}-{model}-{timestamp}/`:
- `summary.txt` - Overall statistics
- `details.txt` - Per-problem results
- `HumanEval_X/generated_tests.py` - Generated test cases
- `HumanEval_X/accuracy_report.txt` - Pass/fail results
- `HumanEval_X/coverage_total.txt` - Coverage report

## Next Steps

- [README.md](README.md) - Full documentation
- [INSTALL.md](INSTALL.md) - Installation guide
- Logs: `logs/single_agent-*/pipeline.log` for debugging