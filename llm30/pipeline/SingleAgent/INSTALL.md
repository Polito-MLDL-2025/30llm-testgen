# Installation Guide

## Quick Start

```bash
cd /path/to/30llm-testgen
pip install -r requirements.txt
export OPENAI_API_KEY="sk-your-api-key"
python llm30/pipeline/SingleAgent/SingleAgent.py --dataset humaneval --max-tasks 5
```

## Requirements

- Python 3.10+
- OpenAI API key
- Internet connection

Check version: `python --version`

## Installation Steps

### 1. Virtual Environment (Recommended)

```bash
# Create and activate
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
# OR
.venv\Scripts\activate           # Windows
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

Core packages: `openai`, `coverage`, `beautifulsoup4`, `python-dotenv`, `httpx`

### 3. Set API Key

```bash
export OPENAI_API_KEY="sk-your-api-key"              # macOS/Linux
# OR
set OPENAI_API_KEY=sk-your-api-key                   # Windows CMD
# OR
$env:OPENAI_API_KEY="sk-your-api-key"                # Windows PowerShell
```

Verify: `python -c "import os; print('Found' if os.getenv('OPENAI_API_KEY') else 'Missing')"`

### 4. Test Installation

```bash
python llm30/pipeline/SingleAgent/SingleAgent.py --dataset humaneval --max-tasks 1
```

Success output:
```
============================================================
Single Agent Test Case Generation Pipeline
============================================================
[1/1] HumanEval/0          | Accuracy:  87.5% | Coverage: 100.0%→100.0% | ...
```

## Usage Examples

```bash
# Process 10 problems
python llm30/pipeline/SingleAgent/SingleAgent.py --dataset humaneval --max-tasks 10

# Use different model
python llm30/pipeline/SingleAgent/SingleAgent.py --dataset humaneval --model gpt-3.5-turbo

# Full MBPP dataset with 4 workers
python llm30/pipeline/SingleAgent/SingleAgent.py --dataset mbpp --max-workers 4
```

## Getting Help

- [README.md](README.md) - Full documentation
- [QUICKSTART.md](QUICKSTART.md) - 5-minute guide
- Logs: `logs/single_agent-*/pipeline.log`