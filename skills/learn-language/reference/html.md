# HTML quiz (only on explicit request)

Use this route only when the user asks for an HTML/printable/browser quiz (`/learn-language html`, "make this a web page"). Quizzes otherwise stay in the chat.

1. Choose questions: the quiz in progress, or a fresh set built the same way as a session quiz (`tutor.py next`, reviews first). 5-10 questions is fine here since it isn't interactive with you.
2. Write the quiz to a temporary JSON file:

```json
{
  "title": "Present perfect review",
  "language": "English",
  "topic": "B1 · present perfect vs past simple",
  "questions": [
    {"type": "choice", "prompt": "Which is more natural?", "options": ["I've finished it yesterday.", "I finished it yesterday."], "answer": 1, "explanation": "A finished time (yesterday) takes the past simple.", "key": "present-perfect-finished-time"},
    {"type": "fill", "prompt": "We ___ (work) on this since Monday.", "answer": "have been working", "accept": ["'ve been working"], "explanation": "since + start point → present perfect continuous."},
    {"type": "correct", "prompt": "Thanks for your feedbacks.", "answer": "Thanks for your feedback.", "explanation": "feedback is uncountable."},
    {"type": "rewrite", "prompt": "Please do the review of my code.", "answer": "Could you review my code when you get a chance?", "explanation": "Use the verb, and soften the request."}
  ]
}
```

   `type` is `choice` (with `options`; `answer` is an index or the option text), `fill`, `correct`, or `rewrite` (self-graded against the model answer). Set `key` on questions that come from review items.
3. `tutor.py html --quiz <file.json>` writes a self-contained page to `<workspace>/quizzes/` (or `--out <path>`). Give the user the path (on macOS offer `open <path>`).
4. The page ends with a "Copy results" block. When the user pastes it back, record each line as in a normal session: `review <key> correct|wrong` for keyed questions, `mistake add` for wrong new ones, then `session --kind review|grammar|vocabulary --score x/y`.
