# Use case brief (W1.2)

Owner: agent and tools lead. Sources: the proposal (`docs/proposal/`), D-003 and D-004.

## First customer

The user is an undergraduate student taking 4–6 courses. Master's students are left out for now: they take fewer
courses, and our test inputs are written for undergraduates.

The payer is the university. The LMS is the school's own system, so we would sell to the school directly, not to an
LMS vendor. This also removes the dependence on a third-party platform for access to the data.

Why the school would pay is still an assumption, not a finding: fewer missed deadlines, fewer make-up and appeal
requests, and happier students. Our first customer is a private university, which competes for students; a tool
like this is also good publicity for the school. Who pays stays a hypothesis (D-004).

## The job done by hand today

Today the student builds the deadline list by hand, in four places:

1. **Inbox.** Read every course email. A reply in an old thread can move a date: in w1-05 the instructor moves
   Homework 2 from 20 to 23 November in a reply, and the LMS is not updated.
2. **LMS.** Open each course's announcements one by one. One post can hold two deadlines (w1-03).
3. **Syllabus PDF.** Search the PDF for the late rule, usually only after the deadline is already close (w1-09: 10 %
   per day, at most 3 days).
4. **Calendar.** Copy every date into a calendar by hand, and fix it again when a date moves.

Nothing connects these four places, so a moved date or a rule found too late is the student's problem.

## Persona

Deniz is a third-year undergraduate taking CS-301, MATH-212, ECON-101 and AIC 390 (fictional student, R10).

On Friday 13 November, Deniz thinks the ECON-101 Assignment 2 is due tonight at 23:59 (w1-14). An email that
arrived the same day moved it to Monday 16 November (w1-23), but Deniz has not read it. CS-301 Lab Report 3 says
"due next Friday", and Deniz cannot tell whether that means 13 or 20 November (w1-02). Deniz asks if ECON-101 work
can be one day late: the course policy says no (w1-12), but the answer is in a PDF Deniz never opened.

In AIC 390 the weekly report is due on Tuesday at 12:30, 24 hours before class, but Deniz's team agreed to submit by
10:00 that morning. One deliverable now has two times, and Deniz has to decide which one goes on the list. (This
case is not in `week1_inputs.jsonl`, which is frozen after the baseline (R9); we add it to the week-2 test set,
W2.3.)

## User stories (5)

| # | Job (from the proposal) | Story | Example input |
|---|---|---|---|
| 1 | Turn an email or LMS post into dated deadlines | As Deniz, I want every deadline in an email or LMS post turned into a dated entry, so that I don't have to read each message and copy dates by hand. | w1-01, w1-03 |
| 2 | Keep the newer date when a deadline moves | As Deniz, I want the newer date to replace the old one when an instructor moves a deadline, so that I don't work towards a date that is no longer valid. | w1-05, w1-23 |
| 3 | Ask what is due and when | As Deniz, I want to ask "what's due this week?" and get a list from my deadlines, with unclear dates marked, so that I know what to work on first. | w1-14, w1-16 |
| 4 | Ask a course or regulation rule and get a cited answer | As Deniz, I want to ask a rule question and get an answer with its source, or "not in the documents", so that I can trust the answer before I act on it. | w1-09, w1-12 |
| 5 | Get a reminder proposed and confirm it | As Deniz, I want the assistant to propose a reminder and add it only after I confirm, so that nothing is written to my calendar without my approval. | w1-17, w1-22 |

## In scope / out of scope

| In scope (scope A, D-004) | Out of scope |
|---|---|
| Deadline extraction from emails, LMS posts and syllabi, with source and verified flag | Real mailboxes or LMS access (R11); all data synthetic (R10) |
| Relative dates and date changes resolved in code | Sending emails, deleting data, payments (no tool can do these) |
| Cited answers to course and regulation questions, or "not in the documents" | Grade predictions and exceptions not in the documents (must not answer) |
| Reminder in a sandbox calendar after preview and confirmation | Code assignments, automatic submission |
| First user: undergraduates taking 4–6 courses | Master's students (later: thesis deadlines live outside email and the LMS) |
