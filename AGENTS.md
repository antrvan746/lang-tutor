# lang-tutor

Two agent skills in the open Agent Skills format (`skills/<name>/SKILL.md`), shipped as a Claude Code plugin and installable into any agent with `install.sh`.

- `skills/lang-tutor/` — always-on feedback while the user works. `SKILL.md` routes; `languages/_common.md` is the shared spine; `languages/<lang>.md` holds per-language substance (framework, syllabus, irregulars, pitfalls).
- `skills/learn-language/` — micro-sessions, onboarding, spaced review, books. `SKILL.md` routes to `reference/*.md`; `scripts/tutor.py` owns all learner state; `scripts/convert.py` converts and splits books; `curriculum/<lang>/*.csv` holds topic lists; `assets/quiz.html` is the opt-in HTML quiz template.

**To use the skills from this checkout without installing**, read `skills/learn-language/SKILL.md` (lessons, quizzes, `init`, books) or `skills/lang-tutor/SKILL.md` (tutor mode) and follow it.

## Conventions

- `tutor.py` and `convert.py` stay standard-library only and Python 3.9 compatible (macOS system Python). Optional tools (`uv`, `pymupdf4llm`, `pandoc`, `markitdown`) are tried at runtime, never imported at module level.
- Learner state changes only through `tutor.py`; generated files (`progress.md`, `mistakes/*.md`) are never the source of truth.
- Skill text is instructions for an agent: imperative, specific, no rationale the agent doesn't need. Load-on-demand reference files keep `SKILL.md` small.
- Never create per-language guides on the fly; unlisted languages use `languages/generic.md`.

## Tests

```sh
python3 -m unittest discover -s test -p 'test_*.py'   # offline, deterministic: SRS, planning, books, converters
./test/run-skill-tests.sh [routing alias fallback modes memory session]   # headless Claude runs (costs tokens)
```

Run the unit tests after any change to `scripts/`; run the matching headless test after changing a `SKILL.md` or reference file.
