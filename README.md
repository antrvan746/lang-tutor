# lang-tutor — Learn English (or Any Language) While You Code (Claude Code Plugin)

**Turn every Claude Code session into a language lesson.**

lang-tutor is a free, open-source Claude Code plugin/skill that helps you learn English while you code — along with Chinese, Japanese, Spanish, French, German, Korean, and more. It's built for the huge number of developers worldwide who already code in Claude Code every day and are also learning English as a second language: instead of a separate app or class, lang-tutor gives you real-time English grammar corrections, idiomatic suggestions, and vocabulary breakdowns on every message, without interrupting your coding flow.

If you've been searching for a way to practice English for programmers and developers, an English learning tool that doesn't require a separate app, or a Claude Code skill/plugin for learning English (or any other language) on the job, this is it.

## What it does

Learning English as a second language? Write in English and get instant, native-speaker-level corrections:

```
You: "I want to make a commit of the changes"

> 🗣️ Language Feedback
> 💡 A native speaker might say: "I want to commit the changes"
> Close! "commit" already implies the changes — no need for "a commit of"
```

Write in your target language (Portuguese in this example) and get instant feedback:

```
You: "Eu quero fazer um commit das mudancas"

> 🗣️ Language Feedback
> 💡 A native speaker might say: "Eu quero commitar as alteracoes"
> Natural and idiomatic — keep it up!
```

Write in your native language and get translations with vocabulary breakdowns:

```
You: "Show me the git log"

> 🗣️ Translation & Breakdown
> Translation: Mostra o historico do git.
>
> Key Vocabulary:
> - mostrar — to show · command form: "mostra"
> - historico — history/log · used for any kind of record
```

Then Claude Code handles your actual request as usual. The language feedback is an addition, never a replacement.

## Features

- **Automatic language detection** — no need to toggle modes. Write in either language and get the right feedback
- **Three proficiency levels** — beginner, intermediate, and advanced, each with calibrated feedback depth
- **Aligned to real proficiency frameworks** — levels map to the standard your language actually uses (HSK, JLPT, TOPIK, CEFR/DELE/DELF/Goethe, ТРКИ, ulpan levels, BIPA…), each with an ordered grammar syllabus drawn from how the language is really taught
- **Irregulars never slip past** — every guide sorts its irregular forms into three tiers (class irregular, locally irregular, fully irregular), because a learner who meets an irregular unflagged will generalize the wrong pattern
- **Preference persistence** — your language, level, and native language are saved across sessions
- **Works with any language** — dedicated guides for the most popular languages, plus a generic guide for everything else. If Claude speaks it, you can learn it
- **Micro-sessions with spaced review** — `/learn-language` gives you a 5-10 minute lesson and a one-question-at-a-time quiz whenever you want one, and brings your own mistakes back until you get them right on three separate days
- **Learn from your textbook** — import a PDF, DOCX, EPUB, or Markdown course book and study it unit by unit, with its exercises and answer key, and progress tracked per exercise
- **Works beyond Claude Code** — the same skills and learner files work in Codex and any agent that reads `AGENTS.md`
- **Non-intrusive** — feedback appears in a compact block before the normal response. Your coding workflow stays intact

## Study mode: `/learn-language`

The feedback above happens while you work. `/learn-language` adds deliberate practice: a 5-10 minute micro-session you can start any time, built on spaced review of your own mistakes.

```
/learn-language init        # once: level, goals, focus areas, learning path (+ optional placement quiz)
/learn-language             # a session: review what's due, or one new grammar point / vocabulary theme
/learn-language review      # reviews only
/learn-language book add ~/Books/english-grammar-in-use.pdf
/learn-language book        # continue the book: next unit, next exercise
/learn-language status      # progress, accuracy by level, weakest items, book progress
/learn-language html        # only when you want it: the quiz as a standalone web page
```

A session is a micro-lesson (≤120 words), then 3-5 quiz questions asked **one at a time in the chat**: sentence correction, fill in the blank, choose the most natural option, rewrite to sound native. The answer is never revealed before you reply. Every mistake goes into a spaced-review loop:

```
you make a mistake (in a quiz, a book exercise, or while coding with /lang-tutor)
  → logged to reviews/due.json, due tomorrow
  → comes back in a quiz → wrong again → back to the start, due tomorrow
  → right on 3 separate days (1 → 3 → 7 day gaps) → mastered
  → one check after 60 days → retired
```

New material follows a CEFR curriculum tagged by context (software engineering, meetings, technical discussion, workplace writing, casual conversation): mostly your level, with a lower-level review every 4th session and a stretch topic every 5th. Other languages use their guide's grammar syllabus, or a curriculum CSV you drop into your workspace.

**Books and course files.** `book add` converts PDF, DOCX, EPUB, HTML, Markdown, or text to Markdown (`books/<slug>/book.md`, so you can check it), splits it into units, finds the exercises and the answer key, and then drives your sessions: one unit's lesson, one exercise block per session, graded against the book's key, with progress per unit and per exercise. DOCX, EPUB, and HTML convert with the Python standard library; for PDF the converter uses whatever is available (`pymupdf4llm`, `pypdf`, `pdftotext`, `markitdown`) and otherwise fetches `pymupdf4llm` into a throwaway environment with `uv`, so the agent can set up the tooling itself. Scanned PDFs need OCR first (`ocrmypdf`).

**Everything is plain files** in `~/.lang-tutor/<language>/` (or `$LANG_TUTOR_HOME`, or a coach folder; see below):

```
profile.md          level, target, focus, learning path
progress.md         generated: sessions, streak, accuracy by level, weakest items, books
history.jsonl       one line per session
reviews/due.json    the spaced-review schedule
mistakes/           generated: grammar.md, vocabulary.md, naturalness.md
sessions/           one log per day
books/<slug>/       book.md + index.json (units, exercises, progress)
curriculum/         optional overrides (e.g. CEFR-J grammar.csv / vocabulary.csv)
```

The bookkeeping is done by a small standard-library Python CLI (`skills/learn-language/scripts/tutor.py`), not by the model, so the review schedule behaves the same in every session and every agent. When a workspace exists, `/lang-tutor` also logs the errors it corrects while you code, so what you write every day feeds your reviews. Tip for Claude Code: allow `Bash(python3:*)` (or the script's full path) in your permissions so logging doesn't prompt.

## Why learn English (or any language) with Claude Code?

Most language learning apps ask you to carve out separate time — a Duolingo streak, a flashcard deck, an app you have to remember to open. That's especially hard when you're a developer already writing English-language commit messages, code comments, and prompts all day. lang-tutor works differently: it rides along on time you're already spending in Claude Code. Every commit message, every question you ask, every plan you write becomes an opportunity to practice English or any other language you're learning — with zero extra time cost.

This makes lang-tutor especially useful for non-native English speakers in tech, since English is already the working language of code, documentation, and most Claude Code sessions. You get corrected and coached in the exact English you actually use at work.

## Supported languages

English is fully supported as a dedicated target language — set it as your target and lang-tutor gives you real-time English corrections, idiom and phrasal-verb suggestions, and article/preposition coaching tuned for ESL learners of any native-language background. It's one of 25 languages with a dedicated tutor guide, each with language-specific error categories, deep-dives, and pitfall coverage:

Each guide is aligned to the proficiency framework its learners actually encounter, so "beginner" and "advanced" map to concrete, published milestones rather than vague labels:

| Language | Framework | Guide highlights |
|---|---|---|
| English | CEFR A1–C2 | Articles, prepositions, present perfect vs. simple past, phrasal verbs, ESL error patterns |
| Chinese (Mandarin) | HSK 1–6 | Character/radical breakdowns, compound words, pinyin, measure words, 了 usage, tone sandhi, 多音字 |
| Japanese | JLPT N5–N1 | Kanji breakdowns, politeness registers, particles, counters, godan/ichidan classing, keigo suppletion |
| Korean | TOPIK 1–6 | Sino-Korean root families, speech levels, particles, two number systems, ㅂ/ㄷ/ㅅ/르 irregular classes |
| Spanish | CEFR / DELE | ser/estar, preterite vs. imperfect, subjunctive triggers, false friends, stem-changing verbs |
| French | CEFR / DELF–DALF | Gender agreement, passé composé vs. imparfait, tu/vous register, ablaut classes, homophone endings |
| Italian | CEFR / CILS–CELI | essere/avere auxiliaries, preposition contractions, congiuntivo, the -isc- class, ci and ne |
| Portuguese | CAPLE / CELPE-Bras | Brazilian/European variants, contractions, ser/estar/ficar, future subjunctive, personal infinitive |
| German | CEFR / Goethe | Case system, word order, separable verbs, compound-noun breakdowns, ablaut classes, plural forms |
| Dutch | CEFR / NT2 | de/het, verb-second vs. verb-final order, separable verbs, false friends, the 't kofschip rule |
| Russian | ТРКИ / TORFL | Case system, verbal aspect pairs, root families, mobile stress, genitive plural |
| Arabic | ACTFL / CEFR\* | Root-and-pattern tables, iḍāfa, non-human plural rule, MSA vs. dialects, weak roots, broken plurals |
| Hindi | CEFR / ACTFL\* | Ergative ने, gender agreement, postpositions, Sanskrit/Persian register layers, irregular perfectives |
| Turkish | CEFR / TÖMER | Vowel harmony, suffix-stack decomposition, var/yok, evidential -miş, consonant softening |
| Vietnamese | Bậc 1–6 (MOET) | Tones, classifiers, kinship pronouns, compound words, Sino-Vietnamese doublets |
| Polish | CEFR | 7-case system, aspect pairs, virile/non-virile plurals, palatalization, numeral agreement |
| Thai | CU-TFL / CEFR | Tone breakdowns and tone *rules*, classifiers, topic-comment structure, register tiers |
| Indonesian | BIPA 1–7 | Affix families (me-/di-/ber-/-kan), nasal assimilation, reduplication, voice choice |
| Hebrew | Ulpan א–ו | Binyanim verb patterns, root-and-pattern tables, construct state, weak-root families |
| Greek | CEFR / Ελληνομάθεια | 4-case declension, three genders, verb aspect stems, aorist formation, Greek-to-English cognates |
| Ukrainian | CEFR / УМІ | 7-case system including the active vocative, aspect pairs, the о/е → і alternation |
| Swedish | CEFR / SFI, Tisus | en/ett gender, definite suffixes, strict V2 word order, the four verb classes, plural declensions |
| Persian (Farsi) | AZFA / CEFR | Ezafe chains, compound/light verbs, SOV order, را object marker, unguessable present stems |
| Filipino (Tagalog) | CEFR / ACTFL\* | Actor/object-focus trigger system, ang/ng/sa particles, aspect via infix and reduplication, Taglish |
| Bengali | CEFR / ACTFL\* | Three-tier honorific register (তুই/তুমি/আপনি), classifiers, no grammatical gender, stem-vowel classes |

\* Arabic, Hindi, Filipino, and Bengali have no single dominant proficiency framework for foreign learners. Their guides say so explicitly and list the competing standards rather than implying a single ladder exists.

Any other language (Swahili, Finnish, Zulu, ...) works through the generic guide, which provides the same feedback modes without language-specific tailoring.

## How it works

The skill is split for token efficiency. A slim `SKILL.md` handles your language status (target language, native language, level) and routing, then loads two files on demand from `skills/lang-tutor/languages/`:

- **`_common.md`** — the shared spine: the two feedback modes and their block formats, the universal deep-dive types, the baseline level tables, and the Irregularity Watch that runs on every response
- **`<your-language>.md`** — the language guide: script conventions, proficiency-framework alignment, an ordered grammar syllabus, the irregulars worth prioritizing, language-specific deep-dives, and pitfalls

`_common.md` defines the structure; the language guide supplies the substance and wins wherever both speak to the same thing. Splitting them this way keeps each language file focused on what is actually specific to that language rather than repeating the same boilerplate 25 times.

Your status is stored in Claude's auto-memory, so it persists across sessions and plugin updates. An optional `UserPromptSubmit` hook re-injects a one-line reminder on each message so tutor mode can't drift out of attention in long sessions; it costs ~60 tokens per message while active and emits nothing in sessions where lang-tutor was never activated.

`learn-language` follows the same pattern: a slim `SKILL.md` routes `init`, sessions, books, and HTML to a reference file in `skills/learn-language/reference/`, which is loaded only for that route. It reuses the `lang-tutor` language guides for each language's framework, syllabus, and irregulars, so the two skills teach consistently.

## Install

### Via Plugin Marketplace

```bash
/plugin marketplace add hamsamilton/lang-tutor
/plugin install lang-tutor@hamsamilton-lang-tutor
```

The plugin namespaces its skills: `/lang-tutor:lang-tutor` and `/lang-tutor:learn-language`.

### Direct install (Claude Code, Codex, other agents)

Clone the repo anywhere and run the installer. It symlinks both skills (`lang-tutor` and `learn-language`) for every agent it finds, so `git pull` updates them all:

```bash
git clone https://github.com/hamsamilton/lang-tutor ~/lang-tutor
~/lang-tutor/install.sh            # or: install.sh claude | install.sh codex
```

- **Claude Code**: `~/.claude/skills/`. Use `/learn-language` and `/lang-tutor`.
- **Codex** (and other tools that read the Agent Skills format): `~/.agents/skills/`. Use `$learn-language`, or ask for a lesson in plain words. Codex's sandbox can't write outside the working directory, so either use a coach folder (below) or add `~/.lang-tutor` to `writable_roots` under `[sandbox_workspace_write]` in `~/.codex/config.toml`.
- **Any agent that reads `AGENTS.md`** (Cursor, Gemini CLI, aider, ...): make a coach folder and run the agent inside it.

```bash
~/lang-tutor/install.sh coach ~/english-coach
cd ~/english-coach && codex     # or claude, cursor, ... then: "learn-language init"
```

A coach folder holds an `AGENTS.md` (plus a `CLAUDE.md` link) pointing at the skills, and the learner files themselves, so it can live in git and travel between machines and agents. `./install.sh uninstall` removes the links and leaves your learner data alone.

The skills need `python3` (3.9+) for `learn-language`; `lang-tutor` alone needs nothing.

## Usage

```bash
# Learning English, native language Spanish
/lang-tutor English Spanish Beginner

# Start with explicit settings for another language
/lang-tutor Portuguese English Advanced

# Or just the language (defaults to English native, auto-detects level)
/lang-tutor Japanese

# After first use, just activate — it remembers your preferences
/lang-tutor

# Deliberate practice (see "Study mode" above)
/learn-language init
/learn-language
```

## Proficiency levels

| | Beginner | Intermediate | Advanced |
|---|---|---|---|
| Corrections | All errors with full explanations | Grammar precision focus | Subtle nuance only |
| Translations | Provided liberally | Only uncommon words | Rarely, specialized terms |
| Feedback language | Mix of target + native | Mostly target language | Entirely in target language |
| Focus | Core grammar, vocabulary building | Idioms, common patterns | Register, formality, style |
| Framework band | e.g. HSK 1–2, JLPT N5–N4, CEFR A1–A2 | HSK 3–4, JLPT N3–N2, CEFR B1–B2 | HSK 5–6, JLPT N1, CEFR C1–C2 |

Each guide adds a grammar-focus row on top of these, listing the specific structures that belong at each band — so at HSK 1–2 you're working on 是/有/在 and measure words, while HSK 3–4 moves you to 了 vs. 过 and the 把 construction.

## Examples

### Translation & Breakdown (Chinese, Beginner)
Write in English and get a full translation with vocabulary and grammar concepts tailored to your level.

![Chinese beginner — Translation & Breakdown mode](LangTutorScreenshots/chinese-beginner-translation.png)

### Language Feedback (Portuguese, Beginner)
Write in your target language and get detailed grammar corrections with explanations.

![Portuguese beginner — Language Feedback mode](LangTutorScreenshots/portuguese-beginner-feedback.png)

### Coding Workflow Integration (Chinese, Advanced)
Language feedback appears alongside your normal coding tasks — it never gets in the way.

![Chinese advanced — feedback alongside coding](LangTutorScreenshots/chinese-advanced-coding.png)

### Advanced Nuance (Italian, Advanced)
At higher levels, feedback focuses on register, word choice, and subtle distinctions.

![Italian advanced — nuanced concept spotlight](LangTutorScreenshots/italian-advanced-nuance.png)

## FAQ

**Can I really learn a language just by using Claude Code?**
lang-tutor won't replace focused study, but it adds consistent, low-effort exposure — corrections and vocabulary in context, every session, with no extra app to open. It's best paired with other study, not a full substitute for it.

**Does this slow down or interrupt my coding workflow?**
No. Language feedback appears as a compact block before Claude's normal response. Claude Code still handles your actual request as usual.

**Can I use lang-tutor to learn English as a second language?**
Yes — set English as your target language (`/lang-tutor English <your native language>`) and lang-tutor corrects your English in real time as you write commit messages, ask questions, and describe tasks in Claude Code, at whatever proficiency level you set.

**What languages does lang-tutor support?**
25 languages with dedicated tutor guides: English, Chinese, Japanese, Korean, Spanish, French, Italian, Portuguese, German, Dutch, Russian, Arabic, Hindi, Turkish, Vietnamese, Polish, Thai, Indonesian, Hebrew, Greek, Ukrainian, Swedish, Persian (Farsi), Filipino (Tagalog), and Bengali — plus a generic guide that works for any other language Claude speaks.

**Is lang-tutor free?**
Yes, it's free and open source under the MIT license. Install it as a Claude Code plugin or clone it directly from GitHub.

**Does lang-tutor give me quizzes or track my progress?**
Yes — `/learn-language` runs short quiz sessions with spaced review of your own mistakes, follows a CEFR curriculum or a textbook you import (PDF, DOCX, EPUB, Markdown), and tracks your progress in plain files you can read and keep in git.

**Does it work with Codex or other coding agents?**
Yes. The skills use the open Agent Skills format and all state lives in plain files driven by a standard-library Python CLI. `install.sh` sets up Claude Code and Codex, and `install.sh coach DIR` creates an `AGENTS.md` folder that any agent can use.

**Do I need to know the language already?**
No. lang-tutor supports beginner, intermediate, and advanced proficiency levels, with feedback depth calibrated to each.

## License

MIT
