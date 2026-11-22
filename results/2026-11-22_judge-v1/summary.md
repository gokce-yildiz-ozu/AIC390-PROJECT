# W2.6 judge_v1 vs blind human labels

Conditions: commit e13d61d, judge model qwen/qwen3.8-27b (returned: qwen/qwen3.8-27b), prompt judge_v1, T=0.0, sheet sha256 95860d3dc3d0f67096a1c5da5bb2d52cbba113ae9d8931cbb01e49064b4a973a (labels commit e13d61d). Script `eval/judge.py`.

**Cohen's kappa: 0.802**, bootstrap 95% [0.500, 1.000] (2000 resamples of the 20 answers, seed 0, percentile; 0 resamples undefined and left out).
Raw agreement: 18/20 = 0.900, Wilson 95% [0.699, 0.972].
Human labels: 11/20 pass, 9/20 fail.
Invalid judge rows: 0 (an invalid judge row (judge_pass null) counts as a disagreement: it takes the opposite of the human label, which also shifts the judge's class rates used in kappa's expected agreement). Failed API calls: 0 (the run stops on one and is resumed; no row is recorded from a failed call).
Plan threshold (docs/STATUS.md): kappa >= 0.6; met: True.

| human \ judge | pass | fail | invalid |
|---|---|---|---|
| pass | 9 | 2 | 0 |
| fail | 0 | 9 | 0 |

| Source run | n | human pass | agree |
|---|---|---|---|
| 2026-11-16_baseline_openai-gpt-oss-120b | 9 | 2 | 7 |
| 2026-11-22_e2e_v1-stub-seed_openai-gpt-oss-120b | 11 | 9 | 11 |

Disagreements (judge reason at item level):

- w1-09 (2026-11-16_baseline_openai-gpt-oss-120b): human True, judge False. must_include not met: 'sonrasında 0'
- w1-19 (2026-11-16_baseline_openai-gpt-oss-120b): human True, judge False. must_include not met: 'not tahmini yapmaz'; must_not met: 'geçme ya da kalma tahmini yapmak' (evidence: 'If you can achieve that, you’ll pass; if not, you’ll need extra credit')
