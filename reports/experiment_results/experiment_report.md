# Experiment Report: Gemini Analysis

## Introduction
This report summarizes the experimental findings for various LLM-based code generation strategies. The experiments were conducted to evaluate the performance of different agentic workflows using the **nvidia/nemotron-3-nano-30b-a3b** model.

### Model Choice
We selected **nvidia/nemotron-3-nano-30b-a3b** for these experiments because:
* Using a single fixed model isolates the impact of strategy and prompt changes, making comparisons fairer.

Strengths highlighted in the model card:
* Open model family with open weights, training data, and recipes.
* Hybrid MoE architecture (Mamba-2 + attention) with 3.5B active parameters and 30B total parameters, favoring efficiency.
* Unified reasoning and non-reasoning model with configurable reasoning traces (accuracy vs. direct-answer trade-off).
* Long-context support: model card notes up to a 1M context size (HF default 256k due to VRAM needs).
* Fine-tuned for code, math, science, tool calling, instruction following, and structured outputs.
* Multilingual support (English, German, Spanish, French, Italian, Japanese) and marked as ready for commercial use.

## Methodology

### Datasets
1.  **HumanEval - 20 Selected Problems**: A curated subset of 20 problems, executed 10 times per strategy to ensure statistical robustness.
2.  **HumanEval - Full Dataset**: The complete set of 164 problems, executed once per strategy.

### Metrics
*   **Accuracy**: The percentage of problems solved correctly.
*   **Coverage**: The extent to which the solution covers the problem requirements (based on test cases).
*   **Tokens**: Average total token usage (Input + Output).

### Strategies & Variants
*   **Single Agent**: A baseline approach using a single LLM call.
*   **QA Agent**: An agentic approach involving Quality Assurance.
*   **QA Agent Competitive**: A variant where agents compete/generate multiple solutions.
*   **QA Agent Merge**: A variant merging outputs from multiple agents.
    *   *Accuracy*: Selection based on internal accuracy metrics.
    *   *Concat*: Concatenation of results.

**Prompts:**
*   **Default**: Enhanced prompts with detailed guidelines and critical rules, including few-shot examples, optimized for the task.
*   **Original**:  Simpler role-based prompts with few-shot examples, from original research.
*   **Zero Shot**: Prompts without few-shot examples.

## Results

### HumanEval - 20 Selected Problems (Average of 10 Runs)

| Strategy             | Variant             |   Accuracy |   Coverage |    Tokens |
|:---------------------|:--------------------|-----------:|-----------:|----------:|
| QA Agent             | Default             |      97.65 |      99.40 | 106,228.40 |
| QA Agent             | Original            |      71.76 |      93.86 |  73,580.40 |
| QA Agent Competitive | Default             |      98.93 |      99.20 | 333,891.50 |
| QA Agent Competitive | Original            |      87.17 |      90.08 | 245,753.70 |
| QA Agent Merge       | Default (Accuracy)  |     100.00 |      99.39 | 333,524.30 |
| QA Agent Merge       | Default (Concat)    |      97.61 |      99.25 | 334,223.40 |
| QA Agent Merge       | Original (Accuracy) |      91.00 |      88.87 | 235,632.30 |
| QA Agent Merge       | Original (Concat)   |      72.94 |      93.58 | 241,940.20 |
| Single Agent         | Default             |      98.48 |      98.92 |  82,873.70 |
| Single Agent         | Original            |      78.89 |      84.66 |  49,949.10 |
| Single Agent         | Zero Shot           |      48.66 |      57.15 |  47,511.50 |

### HumanEval - Full Dataset (164 Problems) (1 Runs)

| Strategy             | Variant             |   Accuracy |   Coverage |     Tokens |
|:---------------------|:--------------------|-----------:|-----------:|-----------:|
| QA Agent             | Default             |      96.50 |      98.57 |  824,319.00 |
| QA Agent             | Original            |      82.77 |      95.43 |  586,740.00 |
| QA Agent Competitive | Default             |      96.92 |      97.92 | 2,564,180.00 |
| QA Agent Competitive | Original            |      93.17 |      97.31 | 1,822,078.00 |
| QA Agent Merge       | Default (Accuracy)  |      97.56 |      97.35 | 2,560,891.00 |
| QA Agent Merge       | Default (Concat)    |      95.41 |      98.27 | 2,575,158.00 |
| QA Agent Merge       | Original (Accuracy) |      96.95 |      96.62 | 1,890,739.00 |
| QA Agent Merge       | Original (Concat)   |      81.17 |      93.82 | 1,845,532.00 |
| Single Agent         | Default             |      97.24 |      98.77 |  641,483.00 |
| Single Agent         | Original            |      86.65 |      91.93 |  405,078.00 |
| Single Agent         | Zero Shot           |      60.61 |      68.11 |  362,462.00 |

## Observations & Conclusion

1.  **Prompt Engineering Matters**: Across all strategies, the "Default" (optimized) prompts consistently outperformed "Original" and "Zero Shot" prompts. Zero Shot performance was significantly lower, highlighting the importance of few-shot examples or better instructions. **Prompt engineering is as important as strategy selection.** A well-designed prompt with explicit rules and examples can improve accuracy by 20-50%. 
2.  **High Accuracy in Selected Subset**: The **QA Agent Merge (Default, Accuracy)** strategy achieved a perfect **100% accuracy** on the 20-problem subset and 97.56% on full dataset, demonstrating exceptional reliability on this curated set.
3. **Best coverage**: QA Agent default on 20 selected (99.40%) and Single Agent default on full (98.77%).
4. **Competitive vs. Efficient**:
    *   **Single Agent (Default)** is highly efficient (lowest token usage among high performers) while maintaining very high accuracy (97.24% on full dataset), making it a strong candidate for resource-constrained environments.
    *   **QA Agent Competitive** and **Merge** strategies offer slight accuracy gains (reaching 97.56%) but at a substantial cost in token usage (approx. 3-4x more tokens than Single Agent).
5. **Cost-Benefit Analysis**: For most general use cases, the **Single Agent (Default)** strategy provides the best balance of performance and cost. However, for critical tasks where every percentage point of accuracy counts, **QA Agent Merge (Accuracy)** is the superior choice.
