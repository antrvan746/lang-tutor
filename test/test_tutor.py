"""Unit tests for the learn-language CLI (tutor.py) and converter (convert.py).

Deterministic and offline — no model calls. Run:
    python3 -m unittest discover -s test -p 'test_*.py'
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "skills" / "learn-language" / "scripts"))

import convert  # noqa: E402
import tutor  # noqa: E402


class CLI:
    """Runs tutor.main against a throwaway home, on a controllable date."""

    def __init__(self, home: Path):
        self.home = home

    def __call__(self, *argv, date="2026-10-01", expect=0):
        os.environ["LANG_TUTOR_TODAY"] = date
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = tutor.main(["--home", str(self.home), *argv])
        if code != expect:
            raise AssertionError(f"exit {code} != {expect}: {err.getvalue()}")
        text = out.getvalue()
        try:
            return json.loads(text)
        except ValueError:
            return text


class TutorTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        self.cli = CLI(self.home)

    def tearDown(self):
        os.environ.pop("LANG_TUTOR_TODAY", None)
        self.tmp.cleanup()

    def init_english(self, **kw):
        args = ["--lang", "English", "init", "--native", "vietnamese", "--level", kw.get("level", "B2"),
                "--target", "C1", "--focus-tags", "eng,meetings"]
        return self.cli(*args)


class InitTests(TutorTestCase):
    def test_init_creates_workspace_and_sets_active(self):
        out = self.init_english()
        self.assertEqual(out["status"], "created")
        root = self.home / "english"
        for rel in ("profile.md", "progress.md", "reviews/due.json", "mistakes/grammar.md"):
            self.assertTrue((root / rel).exists(), rel)
        self.assertEqual(json.loads((self.home / "config.json").read_text())["active"], "english")
        self.assertTrue(out["guide"].endswith("lang-tutor/languages/english.md"))
        prof = self.cli("profile", "show")["profile"]
        self.assertEqual((prof["level"], prof["target"], prof["native"]), ("B2", "C1", "vietnamese"))

    def test_init_twice_does_not_overwrite(self):
        self.init_english()
        self.cli("profile", "set", "level", "C1")
        out = self.init_english()
        self.assertEqual(out["status"], "exists")
        self.assertEqual(self.cli("profile", "show")["profile"]["level"], "C1")

    def test_commands_without_workspace_fail_helpfully(self):
        os.environ["LANG_TUTOR_TODAY"] = "2026-10-01"
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = tutor.main(["--home", str(self.home), "next"])
        self.assertEqual(code, 1)
        self.assertIn("init", err.getvalue())

    def test_unknown_language_falls_back_to_generic_guide(self):
        out = self.cli("--lang", "swahili", "init", "--level", "A1")
        self.assertTrue(out["guide"].endswith("generic.md"))
        plan = self.cli("next")
        self.assertEqual(plan["mode"], "free")


class SpacedReviewTests(TutorTestCase):
    def add(self, key="present-perfect-since", date="2026-10-01"):
        return self.cli("mistake", "add", "--key", key, "--category", "grammar",
                        "--wrong", "I am working here since 2020", "--right", "I've been working here since 2020",
                        date=date)

    def item(self, key="present-perfect-since"):
        return json.loads((self.home / "english" / "reviews" / "due.json").read_text())["items"][key]

    def test_new_mistake_is_due_tomorrow(self):
        self.init_english()
        out = self.add()
        self.assertEqual((out["due"], out["repeated"]), ("2026-10-02", False))
        self.assertEqual(self.cli("due", date="2026-10-01"), [])
        self.assertEqual(len(self.cli("due", date="2026-10-02")), 1)

    def test_three_correct_reviews_master_then_retire(self):
        self.init_english()
        self.add()
        self.assertEqual(self.cli("review", "present-perfect-since", "correct", date="2026-10-02")["due"], "2026-10-05")
        self.assertEqual(self.cli("review", "present-perfect-since", "correct", date="2026-10-05")["due"], "2026-10-12")
        out = self.cli("review", "present-perfect-since", "correct", date="2026-10-12")
        self.assertEqual((out["status"], out["due"]), ("mastered", "2026-12-11"))
        out = self.cli("review", "present-perfect-since", "correct", date="2026-12-11")
        self.assertEqual((out["status"], out["due"]), ("retired", None))
        self.assertEqual(self.cli("due", date="2027-06-01"), [])

    def test_wrong_answer_resets_to_tomorrow(self):
        self.init_english()
        self.add()
        self.cli("review", "present-perfect-since", "correct", date="2026-10-02")
        out = self.cli("review", "present-perfect-since", "wrong", date="2026-10-05")
        self.assertEqual((out["box"], out["due"]), (1, "2026-10-06"))
        self.assertEqual(self.item()["lapses"], 1)

    def test_same_day_correct_does_not_double_advance(self):
        self.init_english()
        self.add()
        self.cli("review", "present-perfect-since", "correct", date="2026-10-02")
        out = self.cli("review", "present-perfect-since", "correct", date="2026-10-02")
        self.assertEqual((out["box"], out["due"]), (2, "2026-10-05"))

    def test_repeated_mistake_pulls_item_forward(self):
        self.init_english()
        self.add()
        for d in ("2026-10-02", "2026-10-05"):
            self.cli("review", "present-perfect-since", "correct", date=d)
        out = self.add(date="2026-10-07")
        self.assertTrue(out["repeated"])
        it = self.item()
        self.assertEqual((it["box"], it["streak"], it["due"], it["occurrences"]), (1, 0, "2026-10-08", 2))

    def test_mastered_item_relapses_on_wrong(self):
        self.init_english()
        self.add()
        for d in ("2026-10-02", "2026-10-05", "2026-10-12"):
            self.cli("review", "present-perfect-since", "correct", date=d)
        out = self.cli("review", "present-perfect-since", "wrong", date="2026-12-11")
        self.assertEqual((out["status"], out["due"]), ("learning", "2026-12-12"))

    def test_mistakes_markdown_is_rendered(self):
        self.init_english()
        self.add()
        md = (self.home / "english" / "mistakes" / "grammar.md").read_text()
        self.assertIn("## present-perfect-since", md)
        self.assertIn("I've been working here since 2020", md)

    def test_unknown_review_key_errors(self):
        self.init_english()
        self.cli("review", "nope", "correct", expect=1)


class PlanTests(TutorTestCase):
    def test_reviews_come_first_when_three_are_due(self):
        self.init_english()
        for k in ("a-one", "b-two", "c-three"):
            self.cli("mistake", "add", "--key", k, "--category", "vocabulary", "--right", "x")
        plan = self.cli("next", date="2026-10-02")
        self.assertEqual(plan["mode"], "review")
        self.assertEqual(len(plan["reviews"]), 3)
        self.assertEqual(self.cli("next", "--new", date="2026-10-02")["mode"], "new+review")

    def test_new_topic_at_level_and_focus(self):
        self.init_english()
        plan = self.cli("next")
        self.assertEqual(plan["mode"], "new")
        self.assertEqual(plan["new"]["level"], "B2")
        self.assertEqual(plan["new"]["band"], "core")
        self.assertTrue({"eng", "meetings"} & set(plan["new"]["tags"].split(";")))

    def test_covered_topics_are_not_repeated_and_kinds_alternate(self):
        self.init_english()
        seen, kinds = set(), []
        for n in range(8):
            new = self.cli("next")["new"]
            self.assertNotIn(new["id"], seen)
            seen.add(new["id"])
            kinds.append(new["kind"])
            self.cli("session", "--kind", new["kind"], "--topic-id", new["id"], "--level", new["level"], "--score", "3/4")
        self.assertEqual(kinds[:4], ["grammar", "vocabulary", "grammar", "vocabulary"])

    def test_bands_include_review_and_stretch(self):
        self.init_english()
        bands = []
        for _ in range(10):
            new = self.cli("next")["new"]
            bands.append((new["band"], new["level"]))
            self.cli("session", "--kind", new["kind"], "--topic-id", new["id"], "--level", new["level"], "--score", "4/4")
        self.assertIn(("review", "B1"), bands)
        self.assertIn(("stretch", "C1"), bands)
        self.assertGreaterEqual(sum(1 for b in bands if b[0] == "core"), 6)

    def test_session_log_updates_progress_and_streak(self):
        self.init_english()
        self.cli("session", "--kind", "grammar", "--topic", "Second conditional", "--level", "B2", "--score", "3/4", date="2026-10-01")
        out = self.cli("session", "--kind", "review", "--score", "2/2", date="2026-10-02")
        self.assertEqual(out["streak_days"], 2)
        progress = (self.home / "english" / "progress.md").read_text()
        self.assertIn("Second conditional", progress)
        self.assertIn("83%", progress)  # 5/6
        self.assertTrue((self.home / "english" / "sessions" / "2026-10-02.md").exists())


BOOK_MD = """# English Grammar in Use (sample)

## Contents

Unit 1 ... Unit 3

## Unit 1 Present continuous

I am doing something = I'm in the middle of doing it.

### Exercise 1.1

1. Please be quiet. I ___ (work).

### Exercise 1.2

1. Look! It ___ (snow).

## Unit 2 Present simple

We use the present simple for things in general.

### Exercise 2.1

1. Water ___ (boil) at 100 degrees.

## Unit 3 Present perfect

### Exercise 3.1

1. I ___ (lose) my key.

## Answer key

1.1 1 'm working
""" + "\nFiller line to pass the minimum text check.\n" * 10


class BookTests(TutorTestCase):
    def write(self, name, text):
        p = Path(self.tmp.name) / name
        p.write_text(text, encoding="utf-8")
        return p

    def test_index_units_finds_units_kinds_and_exercises(self):
        units, strategy = convert.index_units(convert.clean_markdown(BOOK_MD))
        self.assertIn("unit names", strategy)
        by_title = {u["title"]: u for u in units}
        self.assertEqual(by_title["Unit 1 Present continuous"]["exercises"], 2)
        self.assertEqual(by_title["Contents"]["kind"], "front")
        self.assertEqual(by_title["Answer key"]["kind"], "answers")
        self.assertEqual([u["title"] for u in units if u["kind"] == "lesson"],
                         ["Unit 1 Present continuous", "Unit 2 Present simple", "Unit 3 Present perfect"])

    def test_book_flow_tracks_exercises_and_units(self):
        self.init_english()
        out = self.cli("book", "add", str(self.write("egu.md", BOOK_MD)), "--title", "English Grammar in Use")
        self.assertEqual((out["slug"], out["lessons"]), ("english-grammar-in-use", 3))
        plan = self.cli("next")
        self.assertEqual(plan["mode"], "book")
        unit = plan["new"]["unit"]
        self.assertEqual(unit["title"], "Unit 1 Present continuous")
        self.assertEqual([e["label"] for e in plan["new"]["exercises"]], ["Exercise 1.1", "Exercise 1.2"])
        shown = self.cli("book", "show", "--unit", unit["id"])
        self.assertIn("I'm in the middle of doing it", shown)
        self.cli("session", "--kind", "book", "--book", "english-grammar-in-use", "--unit", unit["id"], "--exercise", "1", "--score", "1/1")
        self.assertEqual(self.cli("book", "next")["unit"]["status"], "in-progress")
        self.cli("session", "--kind", "book", "--book", "english-grammar-in-use", "--unit", unit["id"], "--exercise", "2", "--score", "1/1")
        self.assertEqual(self.cli("book", "next")["unit"]["title"], "Unit 2 Present simple")
        self.assertIn("1/3", (self.home / "english" / "progress.md").read_text())

    def test_paused_book_returns_to_curriculum(self):
        self.init_english()
        self.cli("book", "add", str(self.write("egu.md", BOOK_MD)))
        self.cli("book", "set", "--slug", "egu", "--status", "paused")
        self.assertEqual(self.cli("next")["mode"], "new")

    def test_duplicate_import_needs_force(self):
        self.init_english()
        path = str(self.write("egu.md", BOOK_MD))
        self.cli("book", "add", path)
        self.cli("book", "add", path, expect=1)
        self.cli("book", "add", path, "--force")


class ConvertTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_html_to_md(self):
        md = convert.html_to_md(
            "<html><head><style>x{}</style></head><body><h2>Unit 4</h2><p>Some <b>bold</b> text.</p>"
            "<ul><li>one</li><li>two</li></ul><table><tr><th>a</th><th>b</th></tr><tr><td>1</td><td>2</td></tr></table></body></html>"
        )
        self.assertIn("## Unit 4", md)
        self.assertIn("Some **bold** text.", md)
        self.assertIn("- one\n- two", md)
        self.assertIn("| a | b |", md)
        self.assertNotIn("x{}", md)

    def test_docx(self):
        w = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
        doc = (f'<w:document {w}><w:body>'
               '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Unit 1 Greetings</w:t></w:r></w:p>'
               '<w:p><w:r><w:t>Hello there. </w:t></w:r><w:r><w:t>How are you?</w:t></w:r></w:p>'
               '<w:p><w:pPr><w:numPr/></w:pPr><w:r><w:t>first item</w:t></w:r></w:p>'
               '<w:tbl><w:tr><w:tc><w:p><w:r><w:t>en</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>vi</w:t></w:r></w:p></w:tc></w:tr></w:tbl>'
               '</w:body></w:document>')
        styles = (f'<w:styles {w}><w:style w:styleId="Heading1"><w:name w:val="heading 1"/></w:style></w:styles>')
        path = self.dir / "a.docx"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("word/document.xml", doc)
            z.writestr("word/styles.xml", styles)
        md = convert.docx_to_md(path)
        self.assertIn("# Unit 1 Greetings", md)
        self.assertIn("Hello there. How are you?", md)
        self.assertIn("- first item", md)
        self.assertIn("| en | vi |", md)

    def test_epub_follows_spine_order(self):
        path = self.dir / "b.epub"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("mimetype", "application/epub+zip")
            z.writestr("META-INF/container.xml",
                       '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
                       '<rootfile full-path="OEBPS/content.opf"/></rootfiles></container>')
            z.writestr("OEBPS/content.opf",
                       '<package xmlns="http://www.idpf.org/2007/opf"><manifest>'
                       '<item id="c2" href="ch%202.xhtml"/><item id="c1" href="ch1.xhtml"/></manifest>'
                       '<spine><itemref idref="c1"/><itemref idref="c2"/></spine></package>')
            z.writestr("OEBPS/ch1.xhtml", "<html><body><h1>Lesson 1</h1><p>First.</p></body></html>")
            z.writestr("OEBPS/ch 2.xhtml", "<html><body><h1>Lesson 2</h1><p>Second.</p></body></html>")
        md = convert.epub_to_md(path)
        self.assertLess(md.index("Lesson 1"), md.index("Lesson 2"))

    def test_too_little_text_is_rejected(self):
        p = self.dir / "empty.md"
        p.write_text("# hi\n")
        with self.assertRaises(convert.ConversionError):
            convert.to_markdown(p)

    def test_unit_regex_multilingual(self):
        for title in ("Unit 1A", "Lesson IV", "Bài 3: Gia đình", "Lektion 12", "第3課", "제 2 과", "Урок 5"):
            self.assertTrue(convert.UNIT_RE.match(title), title)
        for title in ("Units of measure", "Particles", "Lessons learned"):
            self.assertFalse(convert.UNIT_RE.match(title), title)

    def test_exercise_regex(self):
        for line in ("### Exercise 2.1", "Bài tập 3", "**Practice**", "Übung 4", "練習問題", "Ex. 5"):
            self.assertTrue(convert.EXERCISE_RE.match(line), line)
        self.assertFalse(convert.EXERCISE_RE.match("Exercisebook notes"))

    def test_fixed_chunks_when_no_structure(self):
        units, strategy = convert.index_units("\n".join(f"line {i}" for i in range(450)))
        self.assertTrue(strategy.startswith("fixed"))
        self.assertEqual(len(units), 3)


class HtmlTests(TutorTestCase):
    def test_html_quiz_is_self_contained(self):
        self.init_english()
        quiz = Path(self.tmp.name) / "q.json"
        quiz.write_text(json.dumps({"title": "Test </script> quiz", "questions": [
            {"type": "fill", "prompt": "We ___ here.", "answer": "work"}]}))
        out = self.cli("html", "--quiz", str(quiz))
        html = Path(out["out"]).read_text()
        self.assertNotIn("__QUIZ_JSON__", html)
        self.assertIn("We ___ here.", html)
        self.assertEqual(html.count("</script>"), 1)


if __name__ == "__main__":
    unittest.main()
