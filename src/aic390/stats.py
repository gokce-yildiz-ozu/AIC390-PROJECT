"""Uncertainty for the scoreboard (handbook section 5, Module 2)."""

import math


def proportion_ci(k: int, n: int, method: str = "normal", z: float = 1.96) -> tuple[float, float]:
    """95% interval for k successes out of n.

    "normal" is the handbook formula p ± z·sqrt(p(1-p)/n), clipped to [0, 1]; use it so our numbers match the
    course. "wilson" behaves better for small n or p near 0/1 (normal collapses to [1, 1] when k == n).
    """
    if n <= 0:
        raise ValueError("n must be positive")
    if not 0 <= k <= n:
        raise ValueError("k must be between 0 and n")
    p = k / n
    if method == "normal":
        half = z * math.sqrt(p * (1 - p) / n)
        return max(0.0, p - half), min(1.0, p + half)
    if method == "wilson":
        denom = 1 + z**2 / n
        centre = (p + z**2 / (2 * n)) / denom
        half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
        return max(0.0, centre - half), min(1.0, centre + half)
    raise ValueError(f"unknown method {method!r}")


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value for paired correct/incorrect outcomes.

    b = cases only system A got right, c = cases only system B got right. Cases both got right or both got wrong
    carry no information about which system is better, so they don't enter the test.
    """
    if b < 0 or c < 0:
        raise ValueError("counts must be non-negative")
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2**n
    return min(1.0, 2 * tail)
