# Architecture

Each owner writes the rows of their own components; the evaluation and safety lead assembles the file and the
diagram (STATUS row 12b). Numbers name their run and its conditions (D-009 rule 3).

## Components: agent and tools

Entry point: `aic390.agent.pipeline.run_case(case, client, search=None, table=None, prompts=None)` (interface 4).
Every model call goes through `aic390.jsoncall.call_json`: T = 0, the reply must be one JSON object that passes a
pydantic schema, one retry with the validation error, then a fixed fallback; each call's tokens, latency, prompt
version and error are in `trace`.

| Component | Input | Output | Model, T | Prompt | The model decides | The code decides | On failure | Measured (run, conditions) |
|---|---|---|---|---|---|---|---|---|
| Classifier `aic390.classifier.classify` | channel, received_at, course, sender, text (labels never) | `{intent, course, urgency, multi_step}` | gpt-oss-120b, 0 | `classifier_v1` | the intent, the course code, urgency, multi_step | nothing beyond the schema | invalid twice or API error → `other`, `valid: false` | intent correct 39/42 (every v1 failure is an intent error: w1-19, w1-20, w2-14), v1 run 2026-11-22, stub search, seed table. `urgency` is not graded by any case: not measured (D-009 rule 5) |
| Extraction `aic390.agent.extract.extract` | an email or LMS message, the student's current rows for that course | deadline rows (interface 5), `ask_user`, `untrusted_flag`, `sources`, `dropped` | gpt-oss-120b, 0 | `extract_v1` (v2, v3 planned in STATUS) | which deadlines the text sets or changes, item_key, a date *expression*, the stated time | trust (only `instructor:` senders reach the model), course check (a message changes only its own course), every date (`aic390.dates`), the old date of a moved deadline (table as at `received_at`), "in class" time and calendar anchors (search, cited), `ask_user` | invalid twice → no rows, `valid: false`; a date that cannot be resolved → row with `status: unverified`, never a guess | `deadlines` field correct on all 42 cases in the v1 run 2026-11-22 (stub search, seed table with expected rows: an upper bound) |
| Rule answer `aic390.agent.answer.rule_answer` | the question, course, search hits (k = 5, `as_of` = received_at) | answer text, cited `{doc_id, section}`, `abstain` | gpt-oss-120b, 0 | `answer_v1` | the answer and which numbered sources it cites, or to abstain | no hits → fixed "not in the documents" reply without a model call; only cited hits become `sources`; an abstaining answer cites nothing; answer language (from the question's words) | invalid twice → fixed "not found" reply, `abstain: true` | `sources` and `abstain` correct in the v1 run except where the intent was wrong; prose (must_include, must_not) waits for the W2.6 judge |
| Look-up and reminder `aic390.agent.answer.lookup_answer` | the student's chat message | listed rows, `count`, `ask_user`, reminder `action` (preview, `requires_confirmation: true`) | gpt-oss-120b, 0 | `lookup_v1` | a plan: course, items, kind, period, nearest or all, count asked, reminder timing, another student asked about | which rows (deadline table as at received_at), the count, whether two readings matter (`needs_asking`), the reminder time (due minus 24 h by default), the reply text (a template: every date and number comes from the table) | invalid twice → fixed reply, `abstain: true`; another student's rows → refused | v1 run 2026-11-22: every look-up and reminder case correct except w2-14 (intent) |
| Deadline table `aic390.tools.deadlines` | `data/db/deadlines_seed.jsonl` | rows as they stood at a time; filters; `needs_asking` | none | none | nothing | everything | not applicable | unit tests (`tests/test_agent.py`) |
| Temporary search `aic390.agent.search_stub.search` | interface 2 | the gold sections of the Facts table, word overlap | none | none | nothing | everything | no hits → the caller abstains | is an oracle: kept as `--search oracle` for the W3.8 retrieval-versus-generation test |

Security checks in code, measured in `docs/injection_tests.md` (W2.8): untrusted sender, course check. Nothing is
written anywhere yet: a reminder is only a preview with `requires_confirmation: true` (the write action is week 5).
