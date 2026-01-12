# Selected 20 HumanEval Tasks

This dataset contains a subset of 20 tasks selected from the original HumanEval dataset. The tasks were chosen to ensure:
1.  **Diversity**: Covering various domains such as string manipulation, mathematics, list processing, logic/algorithms, and complex validation.
2.  **Increasing Difficulty**: The tasks are ordered roughly from easiest to hardest, allowing for a progressive evaluation of model capabilities.

## Task List & Reasoning

### Easy / Basic
1.  **HumanEval/53 (`add`)**
    *   **Domain**: Math
    *   **Reason**: Basic addition of two integers. Simplest possible starting point.
2.  **HumanEval/23 (`strlen`)**
    *   **Domain**: String
    *   **Reason**: Return length of a string. Very basic string operation.
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

---

# Selected 20 MBPP Tasks

This section contains a subset of 20 tasks selected from the MBPP dataset.

## Task List & Reasoning

### Easy / Basic
1.  **MBPP/17 (`square_perimeter`)**
    *   **Domain**: Math
    *   **Reason**: Basic formula application.
2.  **MBPP/62 (`smallest_num`)**
    *   **Domain**: List
    *   **Reason**: Simple list traversal/min function.
3.  **MBPP/118 (`string_to_list`)**
    *   **Domain**: String
    *   **Reason**: Basic string splitting.
4.  **MBPP/53 (`check_Equality`)**
    *   **Domain**: String
    *   **Reason**: Simple indexing and comparison.
5.  **MBPP/234 (`volume_cube`)**
    *   **Domain**: Math
    *   **Reason**: Cubic volume calculation.

### Medium / Intermediate
6.  **MBPP/16 (`text_lowercase_underscore`)**
    *   **Domain**: Regex
    *   **Reason**: Pattern matching with regular expressions.
7.  **MBPP/22 (`find_first_duplicate`)**
    *   **Domain**: List/Set
    *   **Reason**: Finding duplicates using hashing or iteration.
8.  **MBPP/57 (`find_Max_Num`)**
    *   **Domain**: Logic/Sorting
    *   **Reason**: Digit manipulation and sorting for largest number.
9.  **MBPP/130 (`max_occurrences`)**
    *   **Domain**: List/Dict
    *   **Reason**: Frequency counting and finding max.
10. **MBPP/160 (`solution`)**
    *   **Domain**: Math
    *   **Reason**: Solving a linear equation ax + by = n for integers.
11. **MBPP/83 (`get_Char`)**
    *   **Domain**: String/ASCII
    *   **Reason**: Character manipulation based on ASCII values.

### Medium-Hard / Complex
12. **MBPP/129 (`magic_square_test`)**
    *   **Domain**: Matrix
    *   **Reason**: Validating a magic square involves summing rows, cols, diagonals.
13. **MBPP/39 (`rearange_string`)**
    *   **Domain**: Heap/Greedy
    *   **Reason**: Rearranging string to avoid adjacent duplicates.
14. **MBPP/108 (`merge_sorted_list`)**
    *   **Domain**: Heap/Iterators
    *   **Reason**: Merging multiple sorted inputs efficiently.
15. **MBPP/123 (`amicable_numbers_sum`)**
    *   **Domain**: Math
    *   **Reason**: Summing proper divisors and checking amicable property.

### Hard / Advanced
16. **MBPP/60 (`max_len_sub`)**
    *   **Domain**: DP
    *   **Reason**: Longest subsequence with difference constraint.
17. **MBPP/187 (`longest_common_subsequence`)**
    *   **Domain**: DP
    *   **Reason**: Classic LCS problem.
18. **MBPP/245 (`max_sum`)**
    *   **Domain**: DP
    *   **Reason**: Maximum sum bitonic subsequence.
19. **MBPP/423 (`get_maxgold`)**
    *   **Domain**: DP/Grid
    *   **Reason**: Pathfinding/Collection in a grid (Gold Mine Problem).
20. **MBPP/291 (`count_no_of_ways`)**
    *   **Domain**: DP
    *   **Reason**: Ways to paint a fence (combinatorics/DP).