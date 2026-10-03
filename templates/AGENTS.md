# Language coach

This folder is a language-learning workspace. The learner's state lives here, one subfolder per language (`profile.md`, `progress.md`, `mistakes/`, `reviews/due.json`, `sessions/`, `books/`). The `.lang-tutor-home` file marks it, so the tutor CLI finds it automatically when run from here.

## Skills

- **Micro-sessions, onboarding, books, reviews:** read `{{SKILLS_DIR}}/learn-language/SKILL.md` and follow it whenever the user asks for a lesson, a quiz, a review, `init`, `status`, or to study a book, or types `learn-language` / `/learn-language` with or without arguments.
- **Corrections while working (optional):** when the user asks for tutor mode, read `{{SKILLS_DIR}}/lang-tutor/SKILL.md` and follow it for the rest of the conversation.

The CLI both skills use:

```sh
python3 {{SKILLS_DIR}}/learn-language/scripts/tutor.py <command>
```

## Ground rules

- Quizzes stay in the chat, one question per message; never reveal an answer before the learner replies.
- Change learner state only through `tutor.py`. `progress.md` and `mistakes/*.md` are generated; don't edit them by hand.
- Create HTML only when the learner asks for it.
