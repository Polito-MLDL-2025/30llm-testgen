# SingleAgent Test Case Generation Pipeline

## Overview

SingleAgent is a **one-step test case generation pipeline** that directly generates test cases from problem descriptions without intermediate planning steps.

**Architecture:**
```
Problem Description → [LLM] → Test Cases (1 LLM call)
```

**vs QAagent:**
```
Problem Description → [LLM] → Plan → [LLM] → Test Cases (2 LLM calls)
```

## Key Features

- **Single LLM Call**: Direct test generation without planning
- **Parallel Processing**: Concurrent test generation with ThreadPoolExecutor
- **Comprehensive Metrics**: Coverage and accuracy evaluation
- **Auto-retry**: Exponential backoff for API failures (3 attempts)

## Quick Start

```bash
# Install
pip install -r requirements.txt

# Set API key
export OPENAI_API_KEY="sk-your-api-key"

# Run
python llm30/pipeline/SingleAgent/SingleAgent.py --dataset humaneval --max-tasks 5
```

See [QUICKSTART.md](QUICKSTART.md) for detailed guide.

## Usage

### Basic Command

```bash
python llm30/pipeline/SingleAgent/SingleAgent.py \
    --dataset humaneval \
    --model gpt-4o \
    --max-tasks 10 \
    --max-workers 2
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--dataset` | `humaneval` | Dataset: `humaneval` or `mbpp` |
| `--model` | `gpt-4o` | LLM model to use |
| `--max-tasks` | All | Number of problems to process |
| `--max-workers` | `2` | Parallel workers |

### Examples

```bash
# MBPP with 4 workers
python llm30/pipeline/SingleAgent/SingleAgent.py --dataset mbpp --max-workers 4

# Different model
python llm30/pipeline/SingleAgent/SingleAgent.py --dataset humaneval --model gpt-3.5-turbo

# Full dataset
python llm30/pipeline/SingleAgent/SingleAgent.py --dataset humaneval
```

## Output

### Console

```
[1/10] HumanEval/0          | Accuracy:  87.5% | Coverage: 100.0%→100.0% | Tokens: 1052+627
[2/10] HumanEval/1          | Accuracy:  92.3% | Coverage: 100.0%→100.0% | Tokens: 1042+636
```

- **Accuracy**: % of tests that pass
- **Coverage**: First 5 tests → All tests (line coverage %)
- **Tokens**: Input + Output tokens

### Files

Results in `logs/single_agent-{dataset}-{model}-{timestamp}/`:

```
logs/single_agent-humaneval-gpt-4o-20260107_213045/
├── summary.txt                  # Overall statistics
├── details.txt                  # Per-problem results
├── pipeline.log                 # Execution log
└── HumanEval_0/
    ├── generated_tests.py       # Test cases
    ├── accuracy_report.txt      # Pass/fail results
    ├── coverage_first_five.txt  # Coverage (first 5)
    └── coverage_total.txt       # Total coverage
```

## Comparison with QAagent

| Aspect | SingleAgent | QAagent |
|--------|-------------|---------|
| LLM Calls | 1 per problem | 2 per problem |
| Steps | Direct generation | Plan → Tests |
| Token Usage | Lower (~1100 tokens) | Higher (~2200 tokens) |
| Speed | Faster | Slower |
| Complexity | Simpler | More structured |

## Installation

See [INSTALL.md](INSTALL.md) for detailed installation guide.

**Prerequisites:** Python 3.10+, OpenAI API key

**Dependencies:** `openai`, `coverage`, `beautifulsoup4`, `python-dotenv`, `httpx`

## Documentation

- [QUICKSTART.md](QUICKSTART.md) - 5-minute quick start guide
- [INSTALL.md](INSTALL.md) - Installation instructions
- [ERROR_HANDLING.md](ERROR_HANDLING.md) - Error handling details
- [BUGFIXES.md](BUGFIXES.md) - Bug fixes and optimizations

## File Structure

```
SingleAgent/
├── SingleAgent.py              # Main pipeline
├── agents/
│   └── test_generator_agent.py # Test generation
├── tools/
│   └── call_and_handle.py      # OpenAI API caller
└── utils/
    ├── utils.py                # Utilities
    ├── logging.py              # Logging
    ├── accuracy.py             # Accuracy evaluation
    └── coverage.py             # Coverage evaluation
```

## Notes

- Reuses QAagent's coverage and accuracy utilities
- Built-in retry with exponential backoff
- Real-time progress display
- Prompt templates in `pipeline/prompts/single_agent/`