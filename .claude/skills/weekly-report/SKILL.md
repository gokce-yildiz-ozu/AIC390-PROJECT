---
name: weekly-report
description: Draft or check reports/week-N.md against the course template and rules before tagging and submitting.
argument-hint: "[week number]"
disable-model-invocation: true
---

Prepare the week $ARGUMENTS report.

1. If `reports/week-$ARGUMENTS.md` does not exist, copy `docs/weekly_report_template.md` to it. Keep every heading
   in order; write "none this week" rather than deleting a section.
2. **Deliverables table:** one row per W$ARGUMENTS.x ID from `docs/course/requirements.md`, status
   (done / partial / not done) and a repo-relative evidence link that exists. Check each link resolves.
3. **Scoreboard:** paste `eval/scoreboard.json` as produced by the harness at this commit. Do not edit numbers by
   hand. Every key present; unmeasured = null.
4. **Experiments and failures:** take them from `results/` and `docs/STATUS.md`. Every number needs n, an interval
   where it is a proportion, and its script.
5. **Contributions:** build from `git log --since` the previous `week-N` tag, grouped by author and area prefix.
   Flag any member with no commits this week, and anyone still missing a second role area.
6. **AI tools used:** summarise from handoffs and commit trailers.
7. Run the checks and print a pass/fail list: word count ≤ 1,500 excluding tables and the JSON block; all section
   headings present and ordered; last week's feedback (section 6) answered point by point; no claim without a
   number; no text addressed to a grader or evaluator.
8. Hand the draft to the `reviewer` subagent for a rubric A–E score with reasons. Report its scores; don't inflate.

Do not tag or push. Tell the user the remaining manual steps: commit, `git tag week-$ARGUMENTS`, push with tags,
submit the link at least 24 hours before class.
