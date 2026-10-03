# Books and course files

A book turns the micro-session into a guided path: lessons come from the book's units in order, quizzes come from the book's own exercises, and progress is tracked per unit and per exercise.

## Import: `book add <file>`

```sh
tutor.py book add "<path>" --title "<Book title>"
```

Accepts `.pdf`, `.docx`, `.epub`, `.md`, `.txt`, `.html`; `.doc`, `.odt`, `.rtf`, `.pptx` work when `markitdown`, `pandoc`, or macOS `textutil` is available. The file is converted to `books/<slug>/book.md` (open it to check the conversion) and split into units in `books/<slug>/index.json`. Importing a book makes it the active one and pauses any other.

**If conversion fails, fix it yourself; don't hand it back to the user:**
- PDF with "No PDF text extractor available": run `uv` if present (the converter uses it automatically), otherwise `python3 -m pip install --user pymupdf4llm` (or `pypdf`), then retry.
- "looks scanned": OCR it (`ocrmypdf in.pdf out.pdf`, installed via `brew install ocrmypdf` or `pipx install ocrmypdf`) and import the OCR'd file. Ask before installing system packages.
- Other formats without a converter: `uv tool install markitdown` (or `pipx install markitdown`), then retry.

`tutor.py convert <file> --out <file>.md` converts without importing, for when the user only wants Markdown.

## Check the split

Read the import summary: `split_strategy`, `lessons`, `exercises`, `answer_units`, `first_units`, `warnings`. Then show the learner a short table of contents (first ~12 units) and fix problems before studying:

- **Wrong granularity** (one unit per page, or the whole book in two units): run `tutor.py book units`, look at the headings in `book.md`, and edit `index.json` so each unit is one lesson. A unit is `{"id", "title", "kind", "start", "end", "exercises", "status", "exercise_progress"}` with 1-indexed inclusive line numbers into `book.md`.
- **Kinds**: `lesson` (studied in order), `answers` (an answer key — used to check answers, never taught), `front` (contents, preface, index — skipped). Fix misclassified units by editing `kind` and setting `status` to `todo` for lessons or `skip` for the rest.
- If the learner wants to start mid-book, mark earlier units done: `tutor.py book mark --unit u05 --status done` for each.

## Study: `book` (or the `book` mode of `next`)

1. `tutor.py book next` (or the `new` block of `next`) gives the unit, its line range, its detected exercises, and any answer-key units.
2. Read the unit: `tutor.py book show --unit <id>` (prints up to 300 lines; follow the `--offset` hint for longer units). Read only what this session needs.
3. **Micro-lesson** — the unit's core point in at most 120 words, in your own words, citing the book's examples.
4. **Quiz from the book** — take the next unfinished exercise (the lowest `n` not yet in the unit's `exercise_progress`), and ask 3-5 of its items one at a time, as written or lightly adapted to the quiz types in `session.md`. When an answer key exists, read the matching section of the `answers` unit and grade against it; where the book and natural modern usage disagree, accept both and say so. If the unit has no detected exercises, write questions from the unit's content and use `--exercise 1`, `2`, … for successive sessions.
5. Feedback and mistake logging exactly as in `session.md`, with `--source book`.
6. Close with `tutor.py session --kind book --book <slug> --unit <id> --exercise <n> --topic "<unit title>" --score x/y`. This records the exercise; the unit becomes `done` once every detected exercise has a score. Mark it done earlier if the learner has clearly mastered it: `tutor.py book mark --unit <id> --status done`.

One exercise block per session is the right pace; a unit typically spans several sessions. Due reviews still come first, as in every session.

## Several books

`tutor.py book list` shows all books. Switch with `tutor.py book set --slug <slug> --status active` (pauses the others); `--status paused` stops a book driving sessions, so `next` returns to the curriculum.
