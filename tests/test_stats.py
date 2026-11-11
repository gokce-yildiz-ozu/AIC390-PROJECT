import pytest

from aic390.stats import mcnemar_exact, proportion_ci


def test_normal_ci_matches_handbook_example():
    # Handbook scoreboard example: abstention 0.80 on n=5 -> [0.45, 1.00]
    lo, hi = proportion_ci(4, 5)
    assert lo == pytest.approx(0.449, abs=1e-3)
    assert hi == 1.0


def test_wilson_does_not_collapse_at_perfect_score():
    lo, hi = proportion_ci(5, 5, method="wilson")
    assert lo < 1.0 and hi == pytest.approx(1.0)
    assert proportion_ci(5, 5) == (1.0, 1.0)


def test_mcnemar_exact_known_values():
    assert mcnemar_exact(0, 0) == 1.0
    assert mcnemar_exact(5, 5) == 1.0
    # all 6 discordant pairs favour one system: 2 * 0.5**6
    assert mcnemar_exact(6, 0) == pytest.approx(0.03125)


@pytest.mark.parametrize("k,n", [(-1, 5), (6, 5), (0, 0)])
def test_invalid_counts(k, n):
    with pytest.raises(ValueError):
        proportion_ci(k, n)
