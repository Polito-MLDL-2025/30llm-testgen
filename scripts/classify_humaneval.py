import ast
import json
import textwrap
from pathlib import Path


def difficulty_to_filename(difficulty: str) -> str:
    mapping = {
        "Easy / Basic": "easy_basic.jsonl",
        "Medium / Intermediate": "medium_intermediate.jsonl",
        "Medium-Hard / Complex": "medium_hard_complex.jsonl",
        "Hard / Advanced": "hard_advanced.jsonl",
        "Unknown": "unknown.jsonl",
    }
    return mapping.get(difficulty, "unknown.jsonl")

def classify_difficulty(problem):
    """
    Classifies a HumanEval problem based on LOC, loops, and if-else conditions.
    """
    code = problem.get('canonical_solution', '')
    
    # Dedent to ensure valid parsing if there are leading spaces
    code = textwrap.dedent(code)
    
    # Calculate LOC (ignoring empty lines and comments)
    loc = len([line for line in code.splitlines() if line.strip() and not line.strip().startswith('#')])
    
    # Parse AST to count structures
    try:
        tree = ast.parse(code)
    except SyntaxError:
        # Fallback for solutions that might have specific indentation needs
        try:
            tree = ast.parse(textwrap.indent(code, "    "))
        except:
            return "Unknown"

    loops = 0
    ifs = 0
    nested_loops = False
    
    for node in ast.walk(tree):
        # Count Loops (For and While)
        if isinstance(node, (ast.For, ast.While)):
            loops += 1
            # Check for nested loops
            for child in ast.iter_child_nodes(node):
                for grandchild in ast.walk(child):
                    if isinstance(grandchild, (ast.For, ast.While)):
                        nested_loops = True
        
        # Count Conditionals
        if isinstance(node, ast.If):
            ifs += 1

    # Logic gates based criteria
    if loc >= 13 or nested_loops:
        return "Hard / Advanced"
    elif (loops > 1) or (loops == 1 and ifs > 2) or loc > 8:
        return "Medium-Hard / Complex"
    elif loops == 1 or ifs >= 1 or loc > 2:
        return "Medium / Intermediate"
    else:
        return "Easy / Basic"

def main():
    dataset_path = Path("llm30/pipeline/datasets/humaneval/problems_original.jsonl")
    output_dir = Path("llm30/pipeline/datasets/humaneval/by_difficulty")
    if not dataset_path.exists():
        print(f"Error: {dataset_path} not found.")
        return
    output_dir.mkdir(parents=True, exist_ok=True)

    results = {
        "Easy / Basic": [],
        "Medium / Intermediate": [],
        "Medium-Hard / Complex": [],
        "Hard / Advanced": [],
        "Unknown": [],
    }
    total = 0
    with open(dataset_path, 'r') as f:
        for line in f:
            if not line.strip():
                continue
            problem = json.loads(line)
            difficulty = classify_difficulty(problem)
            if difficulty not in results:
                difficulty = "Unknown"
            enriched_problem = dict(problem)
            enriched_problem["difficulty"] = difficulty
            results[difficulty].append(enriched_problem)
            total+=1

    # Save one JSONL file per difficulty.
    for level, tasks in results.items():
        out_path = output_dir / difficulty_to_filename(level)
        with open(out_path, "w") as out_f:
            for task in tasks:
                out_f.write(json.dumps(task, ensure_ascii=False) + "\n")
        print(f"Written {len(tasks)} tasks -> {out_path}")

    # Print summary
    print("HumanEval Classification Summary:\n" + "="*30)
    for level, tasks in results.items():
        print(f"\n### {level} :{len(tasks)}/{total} tasks - {len(tasks)/total:.2%} ")
        # Show first 5 examples for brevity if there are many
        # for task in tasks[:10]:
        #     print(f"- {task}")
        # if len(tasks) > 10:
        #     print(f"... and {len(tasks) - 10} more.")

if __name__ == "__main__":
    main()
