# Onboarding (`/learn-language init`)

Runs once per target language. It produces `profile.md` with a learning path, so every later session can start without questions.

If `tutor.py init` reports `"status": "exists"`, show the current profile and ask whether to adjust specific fields (`tutor.py profile set KEY VALUE`) or start over (`--force`, which keeps history and reviews). Do not silently overwrite.

## 1. Interview (one short message, then wait)

Ask everything in a single compact message the learner can answer in one reply. Offer sensible defaults so they can answer "defaults are fine":

1. **Target language** and **native language**
2. **Current level** — self-estimate in the language's framework (CEFR A1-C2, HSK, JLPT, TOPIK, … see the language guide), or "not sure"
3. **Target level** and any deadline (exam, job interview, relocation)
4. **Where they use it** — e.g. software engineering, technical discussions, meetings, casual conversation, workplace writing, travel, exams
5. **Explanations in** — target language, native language, or mixed
6. **Session length and quiz size** — default 10 minutes, 4 questions
7. **Books or course files** they want to follow (path to PDF/DOCX/EPUB/MD), optional

## 2. Placement check (skip if the learner gave a framework level and declines)

Five quick questions, one at a time, as in a normal quiz: two at the claimed level, two one level up, one one level down. Pick them from `tutor.py curriculum list --level <L>` (or the language guide's syllabus). Don't log mistakes yet. Place the learner at the highest level where they got both right; tell them the result in one line and let them override it.

## 3. Create the workspace

```sh
tutor.py --lang <language> curriculum tags          # tag vocabulary for --focus-tags
tutor.py init --lang <language> --native <native> --framework <CEFR|HSK|JLPT|…> \
  --level <current> --target <target> --focus-tags "<tags from the list above>" \
  --focus "<their words>" --goals "<their words>" --explain-in target|native|mixed \
  --session-minutes 10 --quiz-size 4
```

Language names are lowercase English (`english`, `chinese`, `japanese`). Placement mistakes from step 2 can now be logged with `tutor.py mistake add … --source quiz` — they are real data.

## 4. Write the learning path

Edit the `## Learning path` section of `profile.md` (keep the frontmatter intact). Base it on the curriculum (`tutor.py curriculum list --level <L>`) or the language guide's Grammar Syllabus, filtered by their focus:

- **Now (next ~2 weeks)** — 4-6 named topics at their level that serve their stated use
- **Next** — 4-6 topics, including the first stretch topics toward the target
- **Ongoing** — the habits that run alongside: daily session, lang-tutor feedback while coding, book units if any
- **Milestone** — a concrete can-do statement for the target level in their context (e.g. "run a 15-minute design discussion in English without switching language")

Keep it under 25 lines. The micro-sessions don't follow it slavishly — `next` picks topics — but it is what you and the learner refer back to.

## 5. Optional book import

If they named a file, run the `book add` flow from `reference/books.md` now.

## 6. Hand-off

End with three lines: their level and target, how to practice (`/learn-language` any time; `/lang-tutor <language>` for corrections while they work), and an offer to start the first session right now.
