# Test sets

Frozen once used in a comparison (R9). To change one, add a new version (`*_v2.jsonl`) and re-run the old
system on it. `example_inputs.jsonl` is only a smoke test for `--dry-run`; it is not a course deliverable.

Line format (JSONL): `{"id": "w1-01", "text": "...", "ingredients": ["question", "look-up", "action",
"unanswerable", "multi-step", "untrusted-input", "exact-id"], "expected": "..."}` (`expected` from week 2).
