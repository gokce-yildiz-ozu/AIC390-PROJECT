"""Uncertainty for the scoreboard (handbook section 5, Module 2)."""

import math
import random


def proportion_ci(k: int, n: int, method: str = "normal", z: float = 1.96) -> tuple[float, float]:
    """95% interval for k successes out of n.

    "normal" is the handbook formula p ± z·sqrt(p(1-p)/n), clipped to [0, 1]. "wilson" behaves better for small n
    or p near 0/1 (normal collapses to [1, 1] when k == n), so the scoreboard uses Wilson and analysis files list
    both.
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


def cohen_kappa(a: list[bool], b: list[bool]) -> float | None:
    """Cohen's kappa for two raters' binary labels of the same items.

    kappa = (p_o - p_e) / (1 - p_e), with p_o the observed agreement and p_e the agreement expected from each
    rater's own class rates. None when p_e == 1: both raters used the same single class, so agreement beyond
    chance is undefined.
    """
    if len(a) != len(b):
        raise ValueError("both raters must label the same items")
    n = len(a)
    if n == 0:
        raise ValueError("no items")
    p_o = sum(x == y for x, y in zip(a, b, strict=True)) / n
    a_true, b_true = sum(a) / n, sum(b) / n
    p_e = a_true * b_true + (1 - a_true) * (1 - b_true)
    if math.isclose(p_e, 1.0):
        return None
    return (p_o - p_e) / (1 - p_e)


def _percentile(sorted_values: list[float], q: float) -> float:
    """Linear interpolation between the closest ranks (numpy's default method)."""
    pos = (len(sorted_values) - 1) * q
    lo = math.floor(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def kappa_bootstrap_ci(
    a: list[bool], b: list[bool], n_resamples: int = 2000, seed: int = 0, level: float = 0.95
) -> tuple[float | None, float | None, int]:
    """Percentile bootstrap interval for cohen_kappa, resampling items (pairs of labels) with replacement.

    Returns (low, high, n_undefined): resamples where kappa is undefined (one class only) are left out and
    counted. (None, None, n_resamples) when no resample gives a kappa.
    """
    if len(a) != len(b):
        raise ValueError("both raters must label the same items")
    n = len(a)
    if n == 0:
        raise ValueError("no items")
    rng = random.Random(seed)
    values, undefined = [], 0
    for _ in range(n_resamples):
        idx = [rng.randrange(n) for _ in range(n)]
        k = cohen_kappa([a[i] for i in idx], [b[i] for i in idx])
        if k is None:
            undefined += 1
        else:
            values.append(k)
    if not values:
        return None, None, undefined
    values.sort()
    tail = (1 - level) / 2
    return _percentile(values, tail), _percentile(values, 1 - tail), undefined
