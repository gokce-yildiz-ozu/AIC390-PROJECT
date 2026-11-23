# W3.6 faithfulness_v1: judge vs two blind raters

Conditions: commit 3226f8f, judge model qwen/qwen3.8-27b (returned: qwen/qwen3.8-27b), prompt faithfulness_v1, T=0.0, answers from results/2026-11-23_e2e_w3-real-ansv2_openai-gpt-oss-120b, labels rater1 sha256 33d4d95b7b41f310611ff219789a3f865e69f1a7e6501418421ed09dd3c0f8f7; rater2 sha256 4fd435297e0e2baa48ba65cc123d642fb52cbfecb974392ce468e57111aa5a05 (labels commit 3226f8f). Script `eval/faithfulness.py`.

Claims: 13 (0 without a marker, judged against every source of their answer). Sample: all eligible claims if there are at most 40; otherwise random.Random(0).sample(the eligible claims in file order, 40), shown in file order; eligible claims 13.
Bootstrap: 2000 resamples of the claims, seed 0, percentile.
Invalid judge replies: 0 (an invalid judge reply (supported null) counts as a disagreement in each kappa: it takes the opposite of that rater's label, which also shifts the judge's class rates used in kappa's expected agreement). Failed API calls: 0 (the run stops on one and is resumed; no row is recorded from a failed call).

| Pair | Cohen's kappa | bootstrap 95% | raw agreement |
|---|---|---|---|
| judge_vs_rater1 | 0.629 | [0.000, 1.000] | 12/13 = 0.923, Wilson 95% [0.667, 0.986] |
| judge_vs_rater2 | 0.629 | [0.000, 1.000] | 12/13 = 0.923, Wilson 95% [0.667, 0.986] |
| rater1_vs_rater2 | 1.000 | [1.000, 1.000] | 13/13 = 1.000, Wilson 95% [0.772, 1.000] |

judge_vs_rater1:

| | judge_supported | judge_unsupported | judge_invalid |
|---|---|---|---|
| rater1_supported | 11 | 0 | 0 |
| rater1_unsupported | 1 | 1 | 0 |

judge_vs_rater2:

| | judge_supported | judge_unsupported | judge_invalid |
|---|---|---|---|
| rater2_supported | 11 | 0 | 0 |
| rater2_unsupported | 1 | 1 | 0 |

rater1_vs_rater2:

| | rater2_supported | rater2_unsupported |
|---|---|---|
| rater1_supported | 11 | 0 |
| rater1_unsupported | 0 | 2 |

Plan threshold (docs/STATUS.md): judge kappa >= 0.6 against both raters; met: True.

**unsupported_claims (judge)**: 1/13 = 0.077, Wilson 95% [0.014, 0.333]. Rule: claims the judge marked unsupported / claims with a valid judge reply.
Invalid judge replies left out: 0. Worst case (judge unsupported + invalid replies / all claims): 1/13 = 0.077, Wilson 95% [0.014, 0.333].

Disagreements:

- w1-12#2 (w1-12): rater1 False, rater2 False, judge True [judge_vs_rater1, judge_vs_rater2]. Claim: Bu durum, Yönetmelik Madde 14 kapsamında dersin öğretim üyesinin belirlediği kurala göre uygulanır ve ders politikası bu şekilde belirtilmiştir.
