# Selected 20 HumanEval Tasks

This dataset contains a subset of 20 tasks selected from the original HumanEval dataset. The tasks were chosen to ensure:
1.  **Diversity**: Covering various domains such as string manipulation, mathematics, list processing, logic/algorithms, and complex validation.
2.  **Increasing Difficulty**: The tasks are ordered roughly from easiest to hardest, allowing for a progressive evaluation of model capabilities.

## Task List & Reasoning

### Easy / Basic
1.  **HumanEval/0 (`has_close_elements`)**
    *   **Domain**: List/Math
    *   **Reason**: Basic iteration and floating-point comparison. Good starting point.
2.  **HumanEval/1 (`separate_paren_groups`)**
    *   **Domain**: String/Logic
    *   **Reason**: Simple string parsing and balancing logic.
3.  **HumanEval/9 (`rolling_max`)**
    *   **Domain**: List
    *   **Reason**: Standard list traversal and state maintenance.
4.  **HumanEval/16 (`count_distinct_characters`)**
    *   **Domain**: String
    *   **Reason**: Basic set operations and string handling.
5.  **HumanEval/21 (`rescale_to_unit`)**
    *   **Domain**: List/Math
    *   **Reason**: Simple mathematical transformation of a list.

### Medium / Intermediate
6.  **HumanEval/6 (`parse_nested_parens`)**
    *   **Domain**: String
    *   **Reason**: Slightly more complex string parsing involving nesting depth.
7.  **HumanEval/65 (`circular_shift`)**
    *   **Domain**: String/Logic
    *   **Reason**: Involves string manipulation and conditional logic based on input magnitude.
8.  **HumanEval/70 (`strange_sort_list`)**
    *   **Domain**: List
    *   **Reason**: Custom sorting logic requiring list manipulation.
9.  **HumanEval/113 (`odd_count`)**
    *   **Domain**: String/List
    *   **Reason**: Parsing strings inside a list and applying logic to digits.
10. **HumanEval/83 (`starts_one_ends`)**
    *   **Domain**: Math
    *   **Reason**: Combinatorics/Counting problem.
11. **HumanEval/59 (`largest_prime_factor`)**
    *   **Domain**: Math
    *   **Reason**: Number theory (prime factorization).
12. **HumanEval/46 (`fib4`)**
    *   **Domain**: Sequences/DP
    *   **Reason**: Computing a sequence similar to Fibonacci, requires iterative approach or DP.
13. **HumanEval/39 (`prime_fib`)**
    *   **Domain**: Math/Logic
    *   **Reason**: Combining two concepts: Fibonacci sequence and Prime checking.

### Medium-Hard / Complex
14. **HumanEval/32 (`find_zero`)**
    *   **Domain**: Math
    *   **Reason**: Numerical method (root finding) for a polynomial.
15. **HumanEval/93 (`encode`)**
    *   **Domain**: String
    *   **Reason**: Complex string transformation involving case swapping and vowel shifting.
16. **HumanEval/118 (`get_closest_vowel`)**
    *   **Domain**: String Search
    *   **Reason**: Conditional search within a string with specific constraints.

### Hard / Advanced
17. **HumanEval/141 (`file_name_check`)**
    *   **Domain**: Validation
    *   **Reason**: Real-world style validation with multiple conflicting rules.
18. **HumanEval/109 (`move_one_ball`)**
    *   **Domain**: Algorithms
    *   **Reason**: Logic puzzle involving array rotation and sorting properties.
19. **HumanEval/153 (`Strongest_Extension`)**
    *   **Domain**: Parsing/Classes
    *   **Reason**: Involves class-like structures and custom scoring logic for strings.
20. **HumanEval/129 (`minPath`)**
    *   **Domain**: Graph/Grid
    *   **Reason**: Pathfinding in a grid with lexicographical optimization, requiring DFS/BFS or DP.
