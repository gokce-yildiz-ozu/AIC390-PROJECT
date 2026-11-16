# Test sets

Frozen once used in a comparison (R9). To change one, add a new version (`*_v2.jsonl`) and re-run the old
system on it. `example_inputs.jsonl` is only a smoke test for `--dry-run`; it is not a course deliverable.

Line format (JSONL):

```json
{"id": "w1-01", "channel": "email", "received_at": "2026-11-09T10:15:00+03:00", "course": "CS-301",
 "sender": "instructor:Dr. Murat Öztürk", "text": "...", "ingredients": ["extraction", "exact-id"], "expected": "..."}
```

| Field | Meaning |
|---|---|
| `channel` | `email`, `lms` (course announcement) or `chat` (the student asks the assistant) |
| `received_at` | Fixed reference time. Relative dates ("next Friday") are resolved against it, so runs are reproducible (R8) |
| `course` | Course code the message is about, or `null` |
| `sender` | Who sent it, from the channel's metadata, not from the text: `instructor:<name>`, `student:<account>` or `user` (the student asking). Trust decisions use this field, never claims inside `text` |
| `ingredients` | What the input tests: `extraction`, `relative-date`, `conflict`, `needs-retrieval`, `question`, `look-up`, `action`, `unanswerable`, `multi-step`, `untrusted-input`, `exact-id` |
| `expected` | Expected outcome in one line: the deadline(s) with date and time, the answer's source, or the correct refusal |

All messages are synthetic (R10): invented courses, instructors and students.
