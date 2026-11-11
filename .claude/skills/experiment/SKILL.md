---
name: experiment
description: Run a measured comparison or ablation whose numbers will go into a weekly report or the scoreboard. Use whenever comparing prompt versions, temperatures, retrieval settings, models, or agent configurations.
argument-hint: "[short description of the change to test]"
---

Run this experiment so it is reportable under the course rules: $ARGUMENTS

1. **Write the hypothesis first** in one sentence, including which metric should move and in which direction.
2. **One change only.** Name the baseline config and the single variable that differs. Same test set file for
   both arms; if the right test set does not exist yet, stop and say so instead of improvising one.
3. **Budget check.** Count calls = cases × arms × repeats. If over 50 paid calls, show the estimated cost from
   `config/prices.json` and ask before running.
4. Run both arms through the harness (never ad-hoc notebook code). Save to `results/<YYYY-MM-DD>_<slug>/`:
   `config.json` (commit, prompt versions, model, temperature, test set path, n), raw outputs, `summary.json`.
5. Report per arm: value, n, 95% CI (`aic390.stats.proportion_ci`). For paired accuracy comparisons on the same
   cases, add McNemar (`aic390.stats.mcnemar_exact`) and state the discordant counts.
6. Look at the failures, not only the totals: give 2–3 concrete failing inputs with a root-cause category
   (prompt, retrieval, generation, tool design, loop, data, security, evaluation).
7. Write a **decision**: adopt, reject, or inconclusive (overlapping CIs or p ≥ 0.05 is inconclusive; say what
   larger n would be needed). Append a row to the Experiments table in `docs/STATUS.md`.
