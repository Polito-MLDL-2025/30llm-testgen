# Selected 20 HumanEval Tasks (Updated Classification)

## Task List by Difficulty

### Easy / Basic
1. **HumanEval/16 (`count_distinct_characters`)**
   - **Domain**: String
   - **Reason**: Basic set operations and string handling.
2. **HumanEval/21 (`rescale_to_unit`)**
   - **Domain**: List/Math
   - **Reason**: Simple mathematical transformation of a list.
3. **HumanEval/23 (`strlen`)**
   - **Domain**: String
   - **Reason**: Return length of a string. Very basic string operation.
4. **HumanEval/53 (`add`)**
   - **Domain**: Math
   - **Reason**: Basic addition of two integers. Simplest possible starting point.

### Medium / Intermediate
1. **HumanEval/46 (`fib4`)**
   - **Domain**: Sequences/DP
   - **Reason**: Computing a sequence similar to Fibonacci, requires iterative approach or DP.
2. **HumanEval/65 (`circular_shift`)**
   - **Domain**: String/Logic
   - **Reason**: Involves string manipulation and conditional logic based on input magnitude.
3. **HumanEval/70 (`strange_sort_list`)**
   - **Domain**: List
   - **Reason**: Custom sorting logic requiring list manipulation.
4. **HumanEval/83 (`starts_one_ends`)**
   - **Domain**: Math
   - **Reason**: Combinatorics/Counting problem.
5. **HumanEval/93 (`encode`)**
   - **Domain**: String
   - **Reason**: Complex string transformation involving case swapping and vowel shifting.
6. **HumanEval/113 (`odd_count`)**
   - **Domain**: String/List
   - **Reason**: Parsing strings inside a list and applying logic to digits.

### Medium-Hard / Complex
1. **HumanEval/6 (`parse_nested_parens`)**
   - **Domain**: String
   - **Reason**: Slightly more complex string parsing involving nesting depth.
2. **HumanEval/9 (`rolling_max`)**
   - **Domain**: List
   - **Reason**: Standard list traversal and state maintenance.
3. **HumanEval/32 (`find_zero`)**
   - **Domain**: Math
   - **Reason**: Numerical method (root finding) for a polynomial.
4. **HumanEval/109 (`move_one_ball`)**
   - **Domain**: Algorithms
   - **Reason**: Logic puzzle involving array rotation and sorting properties.
5. **HumanEval/118 (`get_closest_vowel`)**
   - **Domain**: String Search
   - **Reason**: Conditional search within a string with specific constraints.
6. **HumanEval/153 (`Strongest_Extension`)**
   - **Domain**: Parsing/Classes
   - **Reason**: Involves class-like structures and custom scoring logic for strings.

### Hard / Advanced
1. **HumanEval/39 (`prime_fib`)**
   - **Domain**: Math/Logic
   - **Reason**: Combining two concepts: Fibonacci sequence and Prime checking.
2. **HumanEval/59 (`largest_prime_factor`)**
   - **Domain**: Math
   - **Reason**: Number theory (prime factorization).
3. **HumanEval/129 (`minPath`)**
   - **Domain**: Graph/Grid
   - **Reason**: Pathfinding in a grid with lexicographical optimization, requiring DFS/BFS or DP.
4. **HumanEval/141 (`file_name_check`)**
   - **Domain**: Validation
   - **Reason**: Real-world style validation with multiple conflicting rules.

## Curated 20 Subset Distribution

- Easy / Basic: 4/20 tasks - 20.00%
- Medium / Intermediate: 6/20 tasks - 30.00%
- Medium-Hard / Complex: 6/20 tasks - 30.00%
- Hard / Advanced: 4/20 tasks - 20.00%

## HumanEval Full DatasetClassification Distribution 

- Easy / Basic: 51/164 tasks - 31.10%
- Medium / Intermediate: 42/164 tasks - 25.61%
- Medium-Hard / Complex: 39/164 tasks - 23.78%
- Hard / Advanced: 32/164 tasks - 19.51%

## Classification Logic

Classification is rule-based and evaluated from highest to lowest difficulty:

- Hard / Advanced: assigned when a task has at least 12 lines of code, or it contains nested loops.
- Medium-Hard / Complex: assigned when a task has at least 2 `if` statements, or at least 2 loops, or at least 8 lines of code.
- Medium / Intermediate: assigned when a task has at least 1 `if` statement, or at least 1 loop, or at least 4 lines of code.
- Easy / Basic: assigned only when none of the above conditions are met.
