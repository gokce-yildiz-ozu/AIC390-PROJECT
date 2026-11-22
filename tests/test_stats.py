import pytest

from aic390.stats import cohen_kappa, kappa_bootstrap_ci, mcnemar_exact, proportion_ci


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


# Cohen's kappa (W2.6) -----------------------------------------------------------------------------------------


def test_kappa_perfect_agreement_is_one():
    labels = [True, True, False, True, False]
    assert cohen_kappa(labels, list(labels)) == pytest.approx(1.0)


def test_kappa_textbook_two_by_two():
    # 50 items: both yes 20, A yes B no 5, A no B yes 10, both no 15. p_o = 0.70, p_e = 0.50, kappa = 0.40.
    a = [True] * 20 + [True] * 5 + [False] * 10 + [False] * 15
    b = [True] * 20 + [False] * 5 + [True] * 10 + [False] * 15
    assert cohen_kappa(a, b) == pytest.approx(0.4)


def test_kappa_one_class_is_none():
    assert cohen_kappa([True] * 4, [True] * 4) is None
    assert cohen_kappa([False] * 3, [False] * 3) is None


def test_kappa_opposite_single_classes_is_zero():
    # p_e = 0 when each rater uses a different single class: no agreement, kappa 0
    assert cohen_kappa([True] * 4, [False] * 4) == pytest.approx(0.0)


def test_kappa_bad_input():
    with pytest.raises(ValueError):
        cohen_kappa([True], [True, False])
    with pytest.raises(ValueError):
        cohen_kappa([], [])


def test_kappa_bootstrap_is_seeded_and_brackets_the_estimate():
    a = [True] * 20 + [True] * 5 + [False] * 10 + [False] * 15
    b = [True] * 20 + [False] * 5 + [True] * 10 + [False] * 15
    first = kappa_bootstrap_ci(a, b, n_resamples=500, seed=0)
    assert first == kappa_bootstrap_ci(a, b, n_resamples=500, seed=0)
    lo, hi, undefined = first
    assert lo < 0.4 < hi and undefined == 0


def test_kappa_bootstrap_all_one_class_is_undefined():
    assert kappa_bootstrap_ci([True] * 5, [True] * 5, n_resamples=50) == (None, None, 50)
