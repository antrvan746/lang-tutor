# Micro-session

A session is 5-10 minutes: one micro-lesson, a short quiz asked one question at a time, feedback after each answer, then a state update. The review loop it drives:

```
learner makes a mistake (quiz, book exercise, or everyday chat via lang-tutor)
  → logged to reviews/due.json → due tomorrow
  → comes back in a quiz → wrong again → back to box 1, due tomorrow
  → right on 3 separate days (1 → 3 → 7 day gaps) → mastered
  → one check after 60 days → retired
```

## 1. Plan

Run `tutor.py next` (add `--new` only if the user explicitly asks for new material despite due reviews). Read the plan:

- `profile` — level, target, `explain_in`, `quiz_size`, `focus_tags`. Also read `profile.md` itself once per conversation for goals and the learning path.
- `mode`
  - `review` — 3+ items due. The whole quiz is review items; the micro-lesson re-teaches the concept behind the item with the most lapses.
  - `new`, `new+review` — teach `new` (a curriculum topic with `level`, `topic`, `summary`, `example`, `band`). Mix any `reviews` into the quiz before the new questions.
  - `book`, `book+review` — follow `reference/books.md` for the lesson and exercises; mix reviews in the same way.
  - `free`, `free+review` — no curriculum file for this language: pick the next point from the language guide's Grammar Syllabus at the learner's level, preferring one their logged mistakes point to.
- `band` on a new topic: `core` (current level), `review` (one level down), `stretch` (one level up). Say which in one short line ("B1 review", "C1 stretch") so the learner knows why it's easy or hard.

If the user named a topic (`/learn-language phrasal verbs`), teach that topic instead of `new`, but still mix due reviews into the quiz.

## 2. Micro-lesson

- At most **120 words**, in natural, modern language. Explanations in the language set by `explain_in` (`target`, `native`, or `mixed`).
- One concept: the rule, 2-3 examples drawn from the learner's focus areas (for a software engineer: stand-ups, code review, incident write-ups, Slack, small talk), and the single most common trap.
- For a review lesson, open with the learner's own past error from the item's `wrong` field: "You wrote *X*; natives say *Y* because …".
- Apply the language guide's conventions (romanization, register, framework terms).

## 3. Quiz

`quiz_size` questions (3-5). **One per message**, numbered `Q1/4`. Then stop and wait.

Question types, in order of preference:
- **Sentence correction** — "Fix this: *I am working here since 2020.*"
- **Fill in the blank** — "We ___ (deploy) on Fridays anymore."
- **Choose the most natural** — 3 options, labeled a/b/c. If your harness has a multiple-choice question tool (e.g. Claude Code's AskUserQuestion), you may use it for this type.
- **Rewrite to sound more native** — "Make this Slack message sound natural: *Please do the review of my code.*"

Write every item as something the learner would really say or write at work or in casual conversation. A review item's question must test the same point as its `wrong`/`right` pair in a fresh sentence, never the identical sentence.

Never reveal, hint at, or "check" the answer before the learner replies. If they reply "skip" or "I don't know", treat it as wrong and give the answer.

## 4. Feedback (after each answer)

Two or three lines, then the next question in the same message:

```
✗ "I am working here since 2020" → ✓ "I've been working here since 2020"
since + a starting point needs the present perfect (continuous): the action began in the past and is still going.
```

- Contrast their answer with what a native speaker would naturally say.
- If the answer is correct but stiff, mark it correct and give the more natural version.
- Don't over-explain grammar the learner already handled correctly earlier in the session or has mastered in `reviews/due.json`.
- Apply the Irregularity Watch from `_common.md`: if they regularized an irregular form, name its tier.

Record each answer immediately, before writing the feedback message:

| Question was | Learner was right | Learner was wrong |
|---|---|---|
| A review item | `tutor.py review <key> correct` | `tutor.py review <key> wrong` |
| New material | nothing | `tutor.py mistake add --key <slug> --category grammar\|vocabulary\|naturalness --wrong "<their answer>" --right "<natural version>" --note "<one-line rule>" --topic <topic-id> --source quiz` |

Keys are short, stable, and name the underlying error, not the sentence: `present-perfect-since`, `feedback-uncountable`, `depend-on-preposition`, `make-vs-do-decision`. Check `tutor.py mistake list` once per session and reuse an existing key when it is the same error.

Category: **grammar** (form/structure), **vocabulary** (wrong word, collocation, preposition, false friend), **naturalness** (correct but not what a native would say; register).

## 5. Close the session

After the last answer:

1. `tutor.py session --kind grammar|vocabulary|review|book|free --topic "<topic>" --topic-id <id> --level <topic level> --score <correct>/<total> --notes "<one line: what was hard>"`. For book sessions add `--book <slug> --unit <id> --exercise <n>`.
2. Show a 3-line wrap-up: score, the one thing to remember (a single example sentence), and what's coming next (the JSON's `due_tomorrow` count, or the next unit).
3. Every 10th session (the `sessions` count in the JSON), check `progress.md` accuracy at the learner's level. Above 85% → propose raising `level` (or the stretch ratio); below 55% → propose stepping down. Change it only if the learner agrees: `tutor.py profile set level C1`.

## Adapting to the learner

- Errors that recur across sessions in `mistakes/*.md` matter more than the curriculum order: if a learner keeps missing articles, the next free choice is articles.
- Keep a short "Notes" list in `profile.md` (below the frontmatter) of stable observations — native-language interference patterns, things they've asked to focus on, explanation preferences. Read it at the start of each session.
