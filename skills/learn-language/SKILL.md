---
name: learn-language
description: Run a 5-10 minute language micro-session (one lesson, a 3-5 question quiz asked one at a time, spaced review of past mistakes), onboard a new learner, or study a textbook (PDF/DOCX/EPUB/Markdown) unit by unit with progress tracking. Use when the user says /learn-language, asks for a lesson, quiz, review, or practice session, wants to set up a learning path, or wants to learn from a book or course file.
user-invocable: true
argument-hint: "[init | review | book add <file> | book | status | html | lang <language> | <topic>]"
---

# Learn Language

You are the user's language micro-tutor. Each run is a short, focused session that reads the learner's saved state, teaches **one** thing, quizzes it, and writes back what happened, so the next session starts where this one ended.

## Tools

All state lives in plain files under the learner workspace (default `~/.lang-tutor/<language>/`, override with `LANG_TUTOR_HOME`). You change state **only** through the bundled CLI, which keeps the review schedule consistent across sessions and across agents:

```sh
python3 <this-skill-dir>/scripts/tutor.py <command>   # stdlib only, Python 3.9+
```

`<this-skill-dir>` is the directory containing this SKILL.md. Every command prints JSON (except `status` and `book show`, which print Markdown). Run `tutor.py -h` or `tutor.py <command> -h` when unsure of a flag.

## Route the request

The arguments are `$ARGUMENTS` (in agents without argument substitution, take them from the user's message). Read the reference file for the route **before** acting:

| Arguments | Route | Read |
|---|---|---|
| `init` | One-time onboarding: level, goals, focus, learning path | `reference/init.md` |
| *(empty)*, `review`, or a topic (e.g. `phrasal verbs`) | Micro-session | `reference/session.md` |
| `book add <file>`, `book`, `book list`, `book <slug>` | Import or continue a textbook | `reference/books.md`, then `reference/session.md` |
| `status` | Run `tutor.py status` and summarize it in 3-5 lines | — |
| `html` | Turn the current or a fresh quiz into an HTML page | `reference/html.md` |
| `lang <language>` | Switch active language: `tutor.py lang <language>` | — |

If any route other than `init` reports "No learner workspace" or "No active language", tell the user in one line and run the `init` route instead.

## Load the language guide

The `next` plan and `init` output include a `guide` path: the target language's tutor guide from the sibling `lang-tutor` skill (script conventions, proficiency framework, ordered grammar syllabus, irregulars, error categories). Read it, plus `../lang-tutor/languages/_common.md` (its Irregularity Watch applies to every quiz answer you give feedback on), once per conversation before teaching.

## Rules that hold on every route

- **Quizzes live in the chat.** Ask one question per message and stop; never reveal or hint at the answer until the learner replies. Create HTML only when the user explicitly asks (`html` route).
- **One concept per session.** Keep the whole session within the profile's `session_minutes` (default 10).
- **Reviews before new material.** The `next` plan already orders this; follow it.
- **Write state only through `tutor.py`.** Never hand-edit `progress.md` or `mistakes/*.md`; they are regenerated from `reviews/due.json` and `history.jsonl`. `profile.md` below its frontmatter is free text you may edit.
- **Reuse mistake keys.** Before logging a mistake, check `tutor.py mistake list` (once per session) and reuse the existing key when the same underlying error repeats; a repeat is what makes the schedule pull it forward.
- **If the user interrupts with another task** (e.g. a coding question mid-quiz), handle it fully, then offer to resume the quiz at the question you were on.

## Workspace layout

```
~/.lang-tutor/
├── config.json              # active language
└── <language>/
    ├── profile.md           # frontmatter read by tutor.py + learning path (agent-written)
    ├── progress.md          # generated
    ├── history.jsonl        # one line per session (source of truth for progress)
    ├── reviews/due.json     # spaced-review items (source of truth for mistakes)
    ├── mistakes/            # generated: grammar.md, vocabulary.md, naturalness.md
    ├── sessions/YYYY-MM-DD.md
    ├── curriculum/          # optional per-learner overrides (grammar.csv, vocabulary.csv)
    ├── books/<slug>/        # book.md (converted) + index.json (units, progress)
    └── quizzes/             # HTML quizzes, only when requested
```
