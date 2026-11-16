# Use case brief (W1.2)

Owner: agent and tools lead. Facts below come from the proposal (`docs/proposal/`) and D-003/D-004.
Replace every `TODO` with your own sentences; delete the hints when done.

## First customer

<!-- Who pays and who uses it. Facts: payer hypothesis = LMS add-on sold to universities, per student per month
(D-004, proposal slide 8); stays a hypothesis until the week-5 pricing task. -->

TODO

## The job done by hand today

<!-- Facts (proposal slide 1): deadlines are spread over emails, LMS posts and syllabi; instructors change dates in
reply threads; announcements sit in each course separately; late, make-up and withdrawal rules are buried in PDFs;
students learn the rule only when it is too late. -->

TODO

## Persona

<!-- Facts: an undergraduate taking 4–6 courses who checks each channel by hand. Give the persona a name, a week
and one concrete moment where things go wrong. Keep it fictional (R10). -->

TODO

## User stories (5)

<!-- Format: "As a <persona>, I want <thing>, so that <reason>." One story per job below; each should map to at
least one input in eval/testsets/week1_inputs.jsonl. -->

| # | Job (from the proposal) | Story | Example input |
|---|---|---|---|
| 1 | Turn an email or LMS post into dated deadlines | TODO | w1-01, w1-03 |
| 2 | Keep the newer date when a deadline moves | TODO | w1-05, w1-23 |
| 3 | Ask what is due and when | TODO | w1-14, w1-16 |
| 4 | Ask a course or regulation rule and get a cited answer | TODO | w1-09, w1-12 |
| 5 | Get a reminder proposed and confirm it | TODO | w1-17, w1-22 |

## In scope / out of scope

| In scope (scope A, D-004) | Out of scope |
|---|---|
| Deadline extraction from emails, LMS posts and syllabi, with source and verified flag | Real mailboxes or LMS access (R11); all data synthetic (R10) |
| Relative dates and date changes resolved in code | Sending emails, deleting data, payments (no tool can do these) |
| Cited answers to course and regulation questions, or "not in the documents" | Grade predictions and exceptions not in the documents (must not answer) |
| Reminder in a sandbox calendar after preview and confirmation | Code assignments, automatic submission |

TODO: check this table and add anything you disagree with.
