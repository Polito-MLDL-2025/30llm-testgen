# Experiment Scripts

This directory contains scripts for running batch experiments with the LLM test generation pipelines.

## HumanEval Presets Used in Results

Use these commands to reproduce the two HumanEval settings reported in this project:

```bash
# 20 selected HumanEval problems (10 runs)
python scripts/run_all.py \
  --dataset humaneval \
  --dataset-path llm30/pipeline/datasets/humaneval/problems_selected.jsonl \
  --model nvidia/nemotron-3-nano-30b-a3b \
  --runs 10 \
  --max-tasks 20 \
  --max-workers 4

# Full HumanEval (164 problems, 1 run)
python scripts/run_all.py \
  --dataset humaneval \
  --dataset-path llm30/pipeline/datasets/humaneval/problems_original.jsonl \
  --model nvidia/nemotron-3-nano-30b-a3b \
  --runs 1 \
  --max-tasks 164 \
  --max-workers 4
```

The same `--dataset-path` and `--max-tasks` pattern also works for each individual script (`run_qaagent_10x.py`, `run_qaagent_competitive_10x.py`, `run_qaagent_merge_10x.py`, `run_singleagent_10x.py`).

## Available Scripts

### 1. `run_all.py` - Run All Experiments
Orchestrates running all experiment scripts sequentially.

**Usage:**
```bash
# Run with default settings
python scripts/run_all.py

# Custom configuration
python scripts/run_all.py --runs 5 --max-tasks 10 --max-workers 4

# With predefined output name
python scripts/run_all.py --runs 3 --predefine-name experiment_batch_1

# Skip specific scripts
python scripts/run_all.py --skip merge competitive

# Different model
python scripts/run_all.py --model gpt-4o --max-tasks 50
```

**Scripts executed (in order):**
1. `run_qaagent_10x.py` - Standard QA Agent
2. `run_qaagent_competitive_10x.py` - Competitive QA Agent
3. `run_qaagent_merge_10x.py` - QA Agent with merge strategies
4. `run_singleagent_10x.py` - Single Agent

---

### 2. `run_qaagent_10x.py` - QA Agent Experiments
Runs QA Agent with both default and original prompts.

**Configurations:**
- `default` prompt
- `original` prompt

**Usage:**
```bash
# Default: 10 runs, 20 tasks, 6 workers
python scripts/run_qaagent_10x.py

# Custom configuration
python scripts/run_qaagent_10x.py --runs 5 --max-tasks 10 --max-workers 4 --model gpt-4o
```

**Outputs:**
- `logs/<timestamp>_qaagen_humaneval_<model>_default.csv`
- `logs/<timestamp>_qaagen_humaneval_<model>_original.csv`

---

### 3. `run_qaagent_competitive_10x.py` - Competitive QA Agent
Runs QA Agent Competitive (multiple code architect prompts) with both generator prompts.

**Configurations:**
- `default` prompt
- `original` prompt

**Usage:**
```bash
python scripts/run_qaagent_competitive_10x.py --runs 10 --max-tasks 20
```

**Outputs:**
- `logs/<timestamp>_qaagen_competitive_humaneval_<model>_default.csv`
- `logs/<timestamp>_qaagen_competitive_humaneval_<model>_original.csv`

---

### 4. `run_qaagent_merge_10x.py` - QA Agent with Merge Strategies
Runs QA Agent with different merge strategies for combining test sets.

**Configurations (2 prompts × 3 strategies = 6 total):**
- `default` + `concat`
- `default` + `concat-enhanced`
- `default` + `llm`
- `original` + `concat`
- `original` + `concat-enhanced`
- `original` + `llm`

**Usage:**
```bash
# Default: 2 runs per config (6 configs total)
python scripts/run_qaagent_merge_10x.py

# More runs per configuration
python scripts/run_qaagent_merge_10x.py --runs 5
```

**Outputs:**
- `logs/<timestamp>_qaagen_merge_<dataset>_<model>_<prompt>_<strategy>.csv`
- Example: `logs/20260112_183045_qaagen_merge_humaneval_gpt4o_default_concat.csv`

---

### 5. `run_singleagent_10x.py` - Single Agent Experiments
Runs Single Agent (direct test generation) with both prompts.

**Configurations:**
- `default` prompt
- `original` prompt

**Usage:**
```bash
python scripts/run_singleagent_10x.py --runs 10 --max-tasks 20
```

**Outputs:**
- `logs/<timestamp>_singleagent_humaneval_<model>_default.csv`
- `logs/<timestamp>_singleagent_humaneval_<model>_original.csv`

---

## Common Arguments

All scripts support the following arguments:

| Argument | Default | Description |
|----------|---------|-------------|
| `--runs` | 10 (2 for merge) | Number of sequential runs per configuration |
| `--dataset` | humaneval | Dataset to use (humaneval or mbpp) |
| `--model` | nvidia/nemotron-3-nano-30b-a3b | LLM model name |
| `--max-tasks` | 20 (2 for merge) | Maximum number of tasks per run |
| `--max-workers` | 6 (2 for merge) | Number of parallel workers |
| `--output-dir` | logs | Directory for CSV outputs |
| `--predefine-name` | None | Base name for output files |

---

## Output Format

Each script generates CSV files with the following columns:

| Column | Description |
|--------|-------------|
| `run` | Run number (1, 2, ..., N) or "aggregate" for summary |
| `log_dir` | Path to the log directory for this run |
| `accuracy` | Test accuracy percentage |
| `first_five_coverage` | Coverage of first 5 lines (%) |
| `coverage` | Total code coverage (%) |
| `input_tokens` | Total input tokens used |
| `output_tokens` | Total output tokens used |

**Example CSV:**
```csv
run,log_dir,accuracy,first_five_coverage,coverage,input_tokens,output_tokens
1,logs/QAagent-20260112_180234,85.5,72.3,89.7,12345,6789
2,logs/QAagent-20260112_181456,87.2,74.1,91.2,12456,6823
aggregate,,86.35,73.2,90.45,24801,13612
```

---

## Progress Output

All scripts now provide real-time feedback:

**Per-Run Output:**
```
→ Run 1 complete: Accuracy=85.50%, Coverage=72.30%→89.70%, Tokens=12345+6789
```

**Configuration Summary:**
```
============================================================
[default] Configuration Complete - Summary of 10 runs:
============================================================
Average Accuracy:          86.35%
Average First-Five Cov:    73.20%
Average Total Coverage:    90.45%
Total Input Tokens:        123,450
Total Output Tokens:       67,890
CSV saved to: logs/20260112_183045_qaagen_humaneval_gpt4o_default.csv
============================================================
```

---

## Estimating Runtime

Approximate time per run (depends on model, tasks, and workers):

- **Single run** (20 tasks, 6 workers): ~3-5 minutes
- **10 runs**: ~30-50 minutes per configuration
- **run_qaagent_10x.py**: ~1-2 hours (2 configs)
- **run_qaagent_competitive_10x.py**: ~1-2 hours (2 configs)
- **run_qaagent_merge_10x.py**: ~30-60 minutes (6 configs × 2 runs default)
- **run_singleagent_10x.py**: ~1-2 hours (2 configs)
- **run_all.py**: ~4-8 hours total

---

## Tips

1. **Start Small**: Test with `--runs 2 --max-tasks 5` before full runs
2. **Use Predefined Names**: Helps organize experiments
   ```bash
   python scripts/run_all.py --predefine-name phase1_gpt4o --runs 5
   ```
3. **Skip Expensive Experiments**: Use `--skip` for run_all.py
   ```bash
   python scripts/run_all.py --skip merge  # Skip the 6-config merge experiment
   ```
4. **Monitor Progress**: All scripts show real-time progress and summaries
5. **Check Logs**: Each run creates detailed logs in `logs/` directory

---

## Troubleshooting

**Script fails midway:**
- Individual runs that fail will show errors but the script continues
- Check `logs/errors.txt` in the run's log directory
- The aggregate CSV will still be generated with completed runs

**Out of memory:**
- Reduce `--max-workers`
- Reduce `--max-tasks`

**Token quota exceeded:**
- Check your API limits
- Use `--max-tasks` to limit workload
- Add delays between runs if needed

---

## Example Workflows

### Quick Test
```bash
# Test all pipelines with minimal runs
python scripts/run_all.py --runs 2 --max-tasks 5 --max-workers 2
```

### Full Evaluation
```bash
# Complete evaluation with 10 runs per config
python scripts/run_all.py --runs 10 --max-tasks 50 --max-workers 6
```

### Model Comparison
```bash
# Run with different models
python scripts/run_all.py --model gpt-4o --predefine-name gpt4o_eval
python scripts/run_all.py --model gpt-3.5-turbo --predefine-name gpt35_eval
```

### Focused Experiment
```bash
# Only run specific pipeline
python scripts/run_singleagent_10x.py --runs 20 --max-tasks 100
```

---

## Directory Structure After Running

```
logs/
├── 20260112_183045_qaagen_humaneval_gpt4o_default.csv
├── 20260112_183045_qaagen_humaneval_gpt4o_original.csv
├── 20260112_190234_qaagen_competitive_humaneval_gpt4o_default.csv
├── 20260112_190234_qaagen_competitive_humaneval_gpt4o_original.csv
├── 20260112_193456_singleagent_humaneval_gpt4o_default.csv
├── 20260112_193456_singleagent_humaneval_gpt4o_original.csv
├── QAagent-20260112_180234/
│   ├── summary.txt
│   ├── details.txt
│   ├── problem_HumanEval_0/
│   └── ...
└── ...
```
