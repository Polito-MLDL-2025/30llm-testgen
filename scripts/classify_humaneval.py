import ast
import json
import os
import textwrap
from collections import defaultdict
from pathlib import Path


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
    if loc >= 12 or nested_loops:
        return "Hard / Advanced"
    elif ifs >= 2 or loops >= 2 or loc >= 8:
        return "Medium-Hard / Complex"
    elif ifs >= 1 or loops >= 1 or loc >= 4:
        return "Medium / Intermediate"
    else:
        return "Easy / Basic"


def get_difficulty_mapping(dataset_path=None):
    """
    Returns a dictionary mapping task_id to difficulty level.
    
    Args:
        dataset_path: Path to the HumanEval dataset. If None, uses default path
                     relative to the script location.
        
    Returns:
        dict: {task_id: difficulty_level}
    """
    if dataset_path is None:
        script_dir = os.path.dirname(__file__)
        project_root = os.path.abspath(os.path.join(script_dir, ".."))
        dataset_path = os.path.join(project_root, "llm30", "pipeline", "datasets", "humaneval", "problems.jsonl")
    
    if not os.path.exists(dataset_path):
        return {}
    
    difficulty_map = {}
    with open(dataset_path, 'r') as f:
        for line in f:
            if not line.strip():
                continue
            problem = json.loads(line)
            difficulty = classify_difficulty(problem)
            difficulty_map[problem['task_id']] = difficulty
    
    return difficulty_map


def main():
    dataset_path = Path("llm30/pipeline/datasets/humaneval/problems_original.jsonl")
    if not dataset_path.exists():
        print(f"Error: {dataset_path} not found.")
        return

    results = {
        "Easy / Basic": [],
        "Medium / Intermediate": [],
        "Medium-Hard / Complex": [],
        "Hard / Advanced": []
    }
    total = 0
    all_tasks = []
    with open(dataset_path, 'r') as f:
        for line in f:
            if not line.strip():
                continue
            problem = json.loads(line)
            difficulty = classify_difficulty(problem)
            all_tasks.append((problem['task_id'], difficulty))
            if difficulty in results:
                results[difficulty].append(f"{problem['task_id']} ({problem['entry_point']})")
            total += 1
    filter = [53, 23, 9, 16, 21, 6, 65, 70, 113, 83, 59, 46, 39, 32, 93, 118, 141, 109, 153, 129]
    filter_string = set(f"HumanEval/{i}" for i in filter)
    # curated = defaultdict(int)
    curated = {
        "Easy / Basic": 0,
        "Medium / Intermediate": 0,
        "Medium-Hard / Complex": 0,
        "Hard / Advanced": 0
    }
    for task in all_tasks:
        if task[0] in filter_string:
            print(task)
            curated[task[1]] += 1
    print("Curated distribution:")
    for level, count in curated.items():
        print(f"{level}: {count}/{len(filter)} tasks - {count / len(filter):.2%} ")
    # Print summary
    print("\nHumanEval Classification Summary:\n" + "=" * 30)
    for level, tasks in results.items():
        print(f"\n{level}: {len(tasks)}/{total} tasks - {len(tasks) / total:.2%}")
        # Show first 5 examples for brevity if there are many
        # for task in tasks[:10]:
        #     print(f"- {task}")
        # if len(tasks) > 10:
        #     print(f"... and {len(tasks) - 10} more.")


if __name__ == "__main__":
    main()
