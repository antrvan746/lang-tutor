#!/usr/bin/env python3
"""Learner-workspace CLI for the learn-language skill.

Owns every piece of state that must stay consistent across sessions and across
agents (Claude Code, Codex, ...): the spaced-review schedule, the session
history, book progress, and the generated progress.md / mistakes/*.md views.
The agent does the teaching; this script does the bookkeeping, so the review
loop behaves identically no matter which agent runs it.

Standard library only (Python 3.9+). Run `tutor.py -h` for commands.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
SKILLS_ROOT = SKILL_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

import convert  # noqa: E402

# Leitner boxes: days until the next review after a correct answer in box N.
INTERVALS = [1, 3, 7, 14, 30]
# Consecutive correct reviews (on different days) that retire an item to "mastered".
MASTERY_STREAK = 3
# A mastered item comes back once after this long; correct then retires it for good.
MAINTENANCE_DAYS = 60
CATEGORIES = ("grammar", "vocabulary", "naturalness")
ALIASES = {
    "mandarin": "chinese", "中文": "chinese", "farsi": "persian", "tagalog": "filipino",
    "castilian": "spanish", "brazilian portuguese": "portuguese", "tiếng anh": "english",
    "tieng anh": "english", "deutsch": "german", "français": "french", "francais": "french",
    "español": "spanish", "espanol": "spanish", "日本語": "japanese", "한국어": "korean",
}


class TutorError(Exception):
    pass


# --- basics -------------------------------------------------------------------

def today() -> dt.date:
    override = os.environ.get("LANG_TUTOR_TODAY")
    return dt.date.fromisoformat(override) if override else dt.date.today()


def iso(d: dt.date) -> str:
    return d.isoformat()


HOME_MARKER = ".lang-tutor-home"


def home_dir(args) -> Path:
    """--home, then $LANG_TUTOR_HOME, then a coach folder (marker file) above cwd, then ~/.lang-tutor."""
    raw = getattr(args, "home", None) or os.environ.get("LANG_TUTOR_HOME")
    if raw:
        return Path(raw).expanduser()
    cwd = Path.cwd()
    for d in (cwd, *cwd.parents):
        if (d / HOME_MARKER).is_file():
            return d
    return Path("~/.lang-tutor").expanduser()


def norm_lang(name: str) -> str:
    key = name.strip().lower()
    return ALIASES.get(key, key).replace(" ", "-")


def read_json(path: Path, default):
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    tmp.replace(path)


def emit(data) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def parse_score(score: str | None) -> tuple[int | None, int | None]:
    if not score:
        return None, None
    m = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*", score)
    if not m:
        raise TutorError(f"score must look like 3/5, got {score!r}")
    return int(m.group(1)), int(m.group(2))


def guide_path(lang: str) -> Path:
    guides = SKILLS_ROOT / "lang-tutor" / "languages"
    path = guides / f"{lang}.md"
    return path if path.exists() else guides / "generic.md"


# --- workspace ----------------------------------------------------------------

class Workspace:
    def __init__(self, home: Path, lang: str):
        self.home = home
        self.lang = lang
        self.root = home / lang

    # paths
    @property
    def profile_path(self) -> Path:
        return self.root / "profile.md"

    @property
    def due_path(self) -> Path:
        return self.root / "reviews" / "due.json"

    @property
    def history_path(self) -> Path:
        return self.root / "history.jsonl"

    @property
    def books_dir(self) -> Path:
        return self.root / "books"

    def exists(self) -> bool:
        return self.profile_path.exists()

    def require(self) -> None:
        if not self.exists():
            raise TutorError(
                f"No learner workspace for '{self.lang}' at {self.root}. Run onboarding first: "
                f"`tutor.py init --lang {self.lang} ...` (the /learn-language init flow)."
            )

    # profile
    def profile(self) -> dict:
        if not self.profile_path.exists():
            return {}
        text = self.profile_path.read_text(encoding="utf-8")
        m = re.match(r"---\n(.*?)\n---", text, re.S)
        data = {}
        if m:
            for line in m.group(1).splitlines():
                if ":" in line and not line.lstrip().startswith("#"):
                    k, v = line.split(":", 1)
                    data[k.strip()] = v.strip()
        return data

    def set_profile(self, key: str, value: str) -> None:
        text = self.profile_path.read_text(encoding="utf-8")
        m = re.match(r"---\n(.*?)\n---", text, re.S)
        if not m:
            raise TutorError("profile.md has no frontmatter block")
        lines = m.group(1).splitlines()
        for i, line in enumerate(lines):
            if line.split(":", 1)[0].strip() == key:
                lines[i] = f"{key}: {value}"
                break
        else:
            lines.append(f"{key}: {value}")
        self.profile_path.write_text("---\n" + "\n".join(lines) + "\n---" + text[m.end():], encoding="utf-8")

    # reviews
    def items(self) -> dict:
        return read_json(self.due_path, {"items": {}})["items"]

    def save_items(self, items: dict) -> None:
        write_json(self.due_path, {"updated": iso(today()), "items": items})

    # history
    def history(self) -> list[dict]:
        if not self.history_path.exists():
            return []
        out = []
        for line in self.history_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(json.loads(line))
        return out

    def append_history(self, entry: dict) -> None:
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        with self.history_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # books
    def books(self) -> list[dict]:
        out = []
        if self.books_dir.exists():
            for idx in sorted(self.books_dir.glob("*/index.json")):
                out.append(read_json(idx, {}))
        return out

    def book(self, slug: str | None) -> dict:
        books = self.books()
        if slug:
            for b in books:
                if b["slug"] == slug:
                    return b
            raise TutorError(f"No book '{slug}'. Known: {', '.join(b['slug'] for b in books) or 'none'}")
        active = [b for b in books if b.get("status") == "active"]
        if not active:
            raise TutorError("No active book. Add one with `tutor.py book add FILE`.")
        if len(active) > 1:
            raise TutorError("Several active books — pass --slug (one of: "
                             + ", ".join(b["slug"] for b in active) + ").")
        return active[0]

    def save_book(self, book: dict) -> None:
        write_json(self.books_dir / book["slug"] / "index.json", book)


def config_path(home: Path) -> Path:
    return home / "config.json"


def resolve_ws(args, require: bool = True) -> Workspace:
    home = home_dir(args)
    lang = getattr(args, "lang", None)
    if lang:
        lang = norm_lang(lang)
    else:
        lang = read_json(config_path(home), {}).get("active")
    if not lang:
        raise TutorError(
            f"No active language in {home}. Run onboarding first (`/learn-language init`, "
            "which calls `tutor.py init --lang <language> ...`)."
        )
    ws = Workspace(home, lang)
    if require:
        ws.require()
    return ws


# --- curriculum ---------------------------------------------------------------

def curriculum(ws: Workspace) -> dict[str, list[dict]]:
    """Grammar and vocabulary items, user overrides first, then the bundled set."""
    out: dict[str, list[dict]] = {}
    for kind in ("grammar", "vocabulary"):
        for base in (ws.root / "curriculum", SKILL_DIR / "curriculum" / ws.lang):
            path = base / f"{kind}.csv"
            if path.exists():
                with path.open(encoding="utf-8") as f:
                    rows = [r for r in csv.DictReader(line for line in f if not line.startswith("#"))]
                for r in rows:
                    r["kind"] = kind
                    r["source"] = str(path)
                out[kind] = rows
                break
    return out


def level_order(items: list[dict]) -> list[str]:
    seen: list[str] = []
    for it in items:
        lvl = (it.get("level") or "").strip()
        if lvl and lvl not in seen:
            seen.append(lvl)
    return seen


def split_tags(value: str) -> set[str]:
    return {t.strip().lower() for t in re.split(r"[;,]", value or "") if t.strip()}


def pick_new_topic(ws: Workspace, profile: dict, history: list[dict]) -> dict | None:
    cur = curriculum(ws)
    if not cur:
        return None
    lessons = [h for h in history if h.get("kind") in ("grammar", "vocabulary")]
    n = len(lessons)
    kinds = [k for k in ("grammar", "vocabulary") if cur.get(k)]
    kind = kinds[n % len(kinds)]
    items = cur[kind]
    order = level_order(items)
    level = profile.get("level", "")
    band = "core"
    if level in order:
        i = order.index(level)
        target = profile.get("target", "")
        stretch = target if target in order and order.index(target) > i else (order[i + 1] if i + 1 < len(order) else level)
        below = order[i - 1] if i > 0 else level
        if n % 5 == 4:
            band, chosen = "stretch", stretch
        elif n % 4 == 3:
            band, chosen = "review", below
        else:
            chosen = level
        bands = [chosen] + [lv for lv in (level, below, stretch) if lv != chosen]
    else:
        bands = order
    covered = {h.get("topic_id") for h in history if h.get("topic_id")}
    focus = split_tags(profile.get("focus_tags", ""))
    for lvl in bands:
        pool = [it for it in items if it.get("level") == lvl and it.get("id") not in covered]
        if pool:
            pool.sort(key=lambda it: 0 if split_tags(it.get("tags", "")) & focus else 1)
            pick = dict(pool[0])
            pick["band"] = band if lvl == bands[0] else "fallback"
            return pick
    # Everything covered: revisit the topic with the lowest score.
    scored = [h for h in lessons if h.get("total")]
    if scored:
        worst = min(scored, key=lambda h: (h["correct"] / h["total"], h["date"]))
        for it in items:
            if it.get("id") == worst.get("topic_id"):
                pick = dict(it)
                pick["band"] = "revisit"
                return pick
    return None


# --- spaced review ------------------------------------------------------------

def due_items(items: dict, on: dt.date) -> list[dict]:
    due = [it for it in items.values()
           if it["status"] in ("learning", "mastered") and it["due"] <= iso(on)]
    due.sort(key=lambda it: (it["due"], -it.get("lapses", 0), -it.get("occurrences", 1)))
    return due


def add_mistake(items: dict, key: str, category: str, wrong: str, right: str,
                note: str, source: str, topic: str | None) -> tuple[dict, bool]:
    """Create a review item, or count a repeat of an existing one. Returns (item, repeated)."""
    t = today()
    tomorrow = iso(t + dt.timedelta(days=1))
    example = {"date": iso(t), "wrong": wrong, "right": right, "source": source}
    item = items.get(key)
    if item is None:
        item = {
            "key": key, "category": category, "topic": topic or "", "wrong": wrong,
            "right": right, "note": note, "box": 1, "streak": 0, "due": tomorrow,
            "status": "learning", "occurrences": 1, "lapses": 0, "reviews": 0,
            "created": iso(t), "last_seen": iso(t), "last_reviewed": None,
            "examples": [example],
        }
        items[key] = item
        return item, False
    item["occurrences"] = item.get("occurrences", 1) + 1
    if item.get("last_seen") != iso(t) or item["status"] != "learning" or item["box"] != 1:
        item["lapses"] = item.get("lapses", 0) + 1
    item.update(box=1, streak=0, due=tomorrow, status="learning", last_seen=iso(t),
                wrong=wrong, right=right)
    if note:
        item["note"] = note
    if topic:
        item["topic"] = topic
    item["examples"] = (item.get("examples", []) + [example])[-5:]
    return item, True


def record_review(item: dict, correct: bool) -> str:
    """Apply one review answer. Returns a short description of what changed."""
    t = today()
    same_day = item.get("last_reviewed") == iso(t)
    item["reviews"] = item.get("reviews", 0) + 1
    item["last_reviewed"] = iso(t)
    if not correct:
        if item["status"] in ("mastered", "retired"):
            item["status"] = "learning"
        item["lapses"] = item.get("lapses", 0) + 1
        item.update(box=1, streak=0, due=iso(t + dt.timedelta(days=1)))
        return "wrong: back to box 1, due tomorrow"
    if same_day:
        return "correct, but already reviewed today: schedule unchanged"
    if item["status"] == "mastered":
        item["status"] = "retired"
        item["due"] = None
        return "correct at maintenance check: retired"
    item["streak"] = item.get("streak", 0) + 1
    if item["streak"] >= MASTERY_STREAK:
        item["status"] = "mastered"
        item["due"] = iso(t + dt.timedelta(days=MAINTENANCE_DAYS))
        return f"mastered: one maintenance check in {MAINTENANCE_DAYS} days"
    item["box"] = min(item.get("box", 1) + 1, len(INTERVALS))
    days = INTERVALS[item["box"] - 1]
    item["due"] = iso(t + dt.timedelta(days=days))
    return f"correct: box {item['box']}, next review in {days} days"


# --- rendering ----------------------------------------------------------------

def day_streak(history: list[dict], on: dt.date) -> int:
    days = {h["date"] for h in history}
    streak = 0
    cursor = on if iso(on) in days else on - dt.timedelta(days=1)
    while iso(cursor) in days:
        streak += 1
        cursor -= dt.timedelta(days=1)
    return streak


def render(ws: Workspace) -> None:
    items = ws.items()
    history = ws.history()
    t = today()
    by_cat: dict[str, list[dict]] = {c: [] for c in CATEGORIES}
    for it in items.values():
        by_cat.setdefault(it["category"], []).append(it)
    (ws.root / "mistakes").mkdir(parents=True, exist_ok=True)
    for cat, its in by_cat.items():
        its.sort(key=lambda it: (it["status"] == "retired", -it.get("occurrences", 1), it["key"]))
        lines = [f"# {cat.capitalize()} mistakes", "",
                 "<!-- Generated by tutor.py from reviews/due.json. Edit the JSON, not this file. -->", ""]
        if not its:
            lines.append("_Nothing logged yet._")
        for it in its:
            due = it["due"] or "—"
            lines += [
                f"## {it['key']}",
                f"- **Status:** {it['status']} · box {it['box']} · streak {it['streak']}/{MASTERY_STREAK} · next review {due}",
                f"- **Seen:** {it.get('occurrences', 1)}× · lapses {it.get('lapses', 0)} · first {it['created']}",
                f"- ✗ {it['wrong']}",
                f"- ✓ {it['right']}",
            ]
            if it.get("note"):
                lines.append(f"- {it['note']}")
            lines.append("")
        (ws.root / "mistakes" / f"{cat}.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    p = ws.profile()
    counts = {s: sum(1 for it in items.values() if it["status"] == s) for s in ("learning", "mastered", "retired")}
    due_now = len(due_items(items, t))
    scored = [h for h in history if h.get("total")]
    acc = (sum(h["correct"] for h in scored) / sum(h["total"] for h in scored)) if scored else None
    lines = [
        f"# Progress — {ws.lang.capitalize()}", "",
        "<!-- Generated by tutor.py. Edit profile.md / reviews/due.json / history.jsonl, not this file. -->", "",
        f"- **Level:** {p.get('level', '?')} → target {p.get('target', '?')} ({p.get('framework', '')})",
        f"- **Sessions:** {len(history)} · current streak {day_streak(history, t)} day(s) · last {history[-1]['date'] if history else '—'}",
        f"- **Quiz accuracy:** {f'{acc:.0%}' if acc is not None else '—'} over {sum(h['total'] for h in scored)} questions",
        f"- **Review items:** {counts['learning']} learning · {counts['mastered']} mastered · {counts['retired']} retired · {due_now} due today",
        "",
    ]
    levels: dict[str, list[int]] = {}
    for h in scored:
        if h.get("level"):
            agg = levels.setdefault(h["level"], [0, 0])
            agg[0] += h["correct"]
            agg[1] += h["total"]
    if levels:
        lines += ["## Accuracy by level", "", "| Level | Correct | Accuracy |", "|---|---|---|"]
        lines += [f"| {lv} | {c}/{n} | {c / n:.0%} |" for lv, (c, n) in levels.items()]
        lines.append("")
    weak = sorted((it for it in items.values() if it["status"] == "learning"),
                  key=lambda it: (-it.get("lapses", 0), -it.get("occurrences", 1)))[:5]
    if weak:
        lines += ["## Weakest items", ""]
        lines += [f"- `{it['key']}` ({it['category']}) — {it.get('occurrences', 1)}× seen, {it.get('lapses', 0)} lapses: ✓ {it['right']}" for it in weak]
        lines.append("")
    books = ws.books()
    if books:
        lines += ["## Books", "", "| Book | Status | Lessons done | Next |", "|---|---|---|---|"]
        for b in books:
            lessons = [u for u in b["units"] if u["kind"] == "lesson"]
            done = sum(1 for u in lessons if u["status"] == "done")
            nxt = next((u for u in lessons if u["status"] != "done"), None)
            lines.append(f"| {b['title']} (`{b['slug']}`) | {b.get('status')} | {done}/{len(lessons)} | {nxt['id'] + ' ' + nxt['title'] if nxt else '—'} |")
        lines.append("")
    if history:
        lines += ["## Recent sessions", "", "| Date | Kind | Topic | Level | Score |", "|---|---|---|---|---|"]
        for h in history[-15:][::-1]:
            score = f"{h['correct']}/{h['total']}" if h.get("total") else "—"
            lines.append(f"| {h['date']} | {h['kind']} | {h.get('topic', '')} | {h.get('level', '')} | {score} |")
        lines.append("")
    (ws.root / "progress.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


# --- commands -----------------------------------------------------------------

PROFILE_TEMPLATE = """---
language: {language}
native: {native}
framework: {framework}
level: {level}
target: {target}
focus_tags: {focus_tags}
explain_in: {explain_in}
session_minutes: {session_minutes}
quiz_size: {quiz_size}
created: {created}
---

# Learner profile — {title}

<!-- The frontmatter above is read by tutor.py; keep it as `key: value` lines.
     Everything below is for the tutor agent and for you. Edit freely. -->

## Goals
{goals}

## Focus areas
{focus}

## Learning path
_To be written during onboarding._

## Notes
"""


def cmd_init(args) -> None:
    home = home_dir(args)
    lang = norm_lang(args.lang)
    ws = Workspace(home, lang)
    if ws.exists() and not args.force:
        emit({"status": "exists", "workspace": str(ws.root), "profile": ws.profile(),
              "hint": "Profile already exists. Update fields with `tutor.py profile set KEY VALUE`, or pass --force to recreate the profile (history and reviews are kept)."})
        return
    for sub in ("mistakes", "reviews", "sessions", "books", "curriculum", "quizzes"):
        (ws.root / sub).mkdir(parents=True, exist_ok=True)
    ws.profile_path.write_text(PROFILE_TEMPLATE.format(
        language=lang, native=args.native, framework=args.framework, level=args.level,
        target=args.target or args.level, focus_tags=args.focus_tags, explain_in=args.explain_in,
        session_minutes=args.session_minutes, quiz_size=args.quiz_size, created=iso(today()),
        title=lang.capitalize(), goals=args.goals or "_Not set._", focus=args.focus or "_Not set._",
    ), encoding="utf-8")
    if not ws.due_path.exists():
        ws.save_items({})
    cfg = read_json(config_path(home), {})
    cfg["active"] = lang
    write_json(config_path(home), cfg)
    render(ws)
    cur = curriculum(ws)
    emit({"status": "created", "workspace": str(ws.root), "profile": str(ws.profile_path),
          "guide": str(guide_path(lang)),
          "curriculum": {k: len(v) for k, v in cur.items()} or "none bundled — use the language guide's Grammar Syllabus"})


def cmd_lang(args) -> None:
    home = home_dir(args)
    cfg = read_json(config_path(home), {})
    known = sorted(p.parent.name for p in home.glob("*/profile.md"))
    if args.name:
        lang = norm_lang(args.name)
        if lang not in known:
            raise TutorError(f"No workspace for '{lang}'. Known: {', '.join(known) or 'none'}. Run init first.")
        cfg["active"] = lang
        write_json(config_path(home), cfg)
    emit({"active": cfg.get("active"), "languages": known, "home": str(home)})


def cmd_profile(args) -> None:
    ws = resolve_ws(args)
    if args.action == "set":
        ws.set_profile(args.key, args.value)
        render(ws)
    emit({"profile": ws.profile(), "path": str(ws.profile_path)})


def cmd_status(args) -> None:
    ws = resolve_ws(args)
    render(ws)
    if args.json:
        items = ws.items()
        history = ws.history()
        emit({
            "language": ws.lang, "workspace": str(ws.root), "profile": ws.profile(),
            "sessions": len(history), "streak_days": day_streak(history, today()),
            "due_today": len(due_items(items, today())),
            "items": {s: sum(1 for it in items.values() if it["status"] == s) for s in ("learning", "mastered", "retired")},
            "books": [{"slug": b["slug"], "title": b["title"], "status": b.get("status")} for b in ws.books()],
        })
    else:
        print((ws.root / "progress.md").read_text(encoding="utf-8"))


def cmd_next(args) -> None:
    ws = resolve_ws(args)
    profile = ws.profile()
    items = ws.items()
    history = ws.history()
    t = today()
    quiz_size = int(profile.get("quiz_size") or 4)
    due = due_items(items, t)
    reviews = due[:quiz_size]
    plan: dict = {
        "date": iso(t), "language": ws.lang, "workspace": str(ws.root), "profile": profile,
        "guide": str(guide_path(ws.lang)), "quiz_size": quiz_size,
        "due_total": len(due), "reviews": reviews, "new": None,
    }
    if len(due) >= 3 and not args.new:
        plan["mode"] = "review"
        plan["why"] = f"{len(due)} items due — review before new material."
    else:
        book = next_book(ws, history)
        unit = next((u for u in book["units"] if u["kind"] == "lesson" and u["status"] != "done"), None) if book else None
        if unit:
            lines = (ws.books_dir / book["slug"] / "book.md").read_text(encoding="utf-8").split("\n")
            plan["mode"] = "book"
            plan["new"] = {
                "kind": "book", "book": book["slug"], "title": book["title"], "unit": unit,
                "path": str(ws.books_dir / book["slug"] / "book.md"),
                "exercises": convert.unit_exercises(lines, unit["start"], unit["end"]),
                "answer_units": [u["id"] for u in book["units"] if u["kind"] == "answers"],
            }
            plan["why"] = f"Active book '{book['title']}': continue with {unit['id']} {unit['title']}."
        else:
            topic = pick_new_topic(ws, profile, history)
            plan["mode"] = "new" if topic else "free"
            plan["new"] = topic
            plan["why"] = ("Next uncovered curriculum topic." if topic else
                           "No curriculum file for this language — pick a topic from the guide's Grammar Syllabus.")
        if reviews:
            plan["mode"] += "+review"
    emit(plan)


def next_book(ws: Workspace, history: list[dict]) -> dict | None:
    """Active books with lessons left take turns: the one studied least recently goes next."""
    def last_studied(book: dict) -> int:
        return max((n for n, h in enumerate(history) if h.get("book") == book["slug"]), default=-1)

    candidates = [b for b in ws.books() if b.get("status") == "active"
                  and any(u["kind"] == "lesson" and u["status"] != "done" for u in b["units"])]
    if not candidates:
        return None
    return min(candidates, key=lambda b: (last_studied(b), b.get("created", "")))


def rotation_book(ws: Workspace, slug: str | None) -> dict:
    """The named book, or the one whose turn it is."""
    if slug:
        return ws.book(slug)
    return next_book(ws, ws.history()) or ws.book(None)


def cmd_due(args) -> None:
    ws = resolve_ws(args)
    emit(due_items(ws.items(), today())[: args.limit])


def cmd_mistake(args) -> None:
    ws = resolve_ws(args)
    items = ws.items()
    if args.action == "add":
        if args.category not in CATEGORIES:
            raise TutorError(f"category must be one of {', '.join(CATEGORIES)}")
        key = convert.slugify(args.key, fallback="item")
        item, repeated = add_mistake(items, key, args.category, args.wrong, args.right,
                                     args.note or "", args.source, args.topic)
        ws.save_items(items)
        render(ws)
        emit({"key": key, "repeated": repeated, "occurrences": item["occurrences"], "due": item["due"]})
    else:
        rows = [{"key": it["key"], "category": it["category"], "status": it["status"],
                 "occurrences": it.get("occurrences", 1), "right": it["right"]}
                for it in items.values() if not args.category or it["category"] == args.category]
        emit(sorted(rows, key=lambda r: (r["category"], r["key"])))


def cmd_review(args) -> None:
    ws = resolve_ws(args)
    items = ws.items()
    key = convert.slugify(args.key, fallback="item")
    if key not in items:
        raise TutorError(f"No review item '{key}'. See `tutor.py mistake list`.")
    result = record_review(items[key], args.result == "correct")
    ws.save_items(items)
    render(ws)
    it = items[key]
    emit({"key": key, "result": result, "status": it["status"], "box": it["box"], "due": it["due"]})


def cmd_session(args) -> None:
    ws = resolve_ws(args)
    correct, total = parse_score(args.score)
    entry = {"date": iso(today()), "kind": args.kind, "topic": args.topic or "",
             "topic_id": args.topic_id or "", "level": args.level or "",
             "correct": correct, "total": total, "notes": args.notes or ""}
    if args.book:
        entry.update(book=args.book, unit=args.unit or "", exercise=args.exercise or "")
    ws.append_history(entry)
    if args.book and args.unit:
        book = ws.book(args.book)
        mark_unit(book, args.unit, args.exercise, args.score, None)
        ws.save_book(book)
    log = ws.root / "sessions" / f"{entry['date']}.md"
    log.parent.mkdir(parents=True, exist_ok=True)
    new_file = not log.exists()
    with log.open("a", encoding="utf-8") as f:
        if new_file:
            f.write(f"# Sessions — {entry['date']}\n")
        f.write(f"\n## {args.kind}: {entry['topic'] or entry['topic_id'] or '—'}\n")
        if args.score:
            f.write(f"- Score: {args.score}\n")
        if args.book:
            f.write(f"- Book: {args.book} {args.unit or ''} {('exercise ' + args.exercise) if args.exercise else ''}\n")
        if args.notes:
            f.write(f"- Notes: {args.notes}\n")
    render(ws)
    history = ws.history()
    emit({"logged": entry, "sessions": len(history), "streak_days": day_streak(history, today()),
          "due_tomorrow": len(due_items(ws.items(), today() + dt.timedelta(days=1)))})


def mark_unit(book: dict, unit_id: str, exercise: str | None, score: str | None, status: str | None) -> dict:
    unit = next((u for u in book["units"] if u["id"] == unit_id), None)
    if unit is None:
        raise TutorError(f"No unit '{unit_id}' in {book['slug']}")
    t = iso(today())
    if exercise:
        unit["exercise_progress"][str(exercise)] = {"date": t, "score": score}
        if unit["status"] == "todo":
            unit["status"] = "in-progress"
        if unit["exercises"] and len(unit["exercise_progress"]) >= unit["exercises"] and not status:
            status = "done"
    if status:
        unit["status"] = status
    elif unit["status"] == "todo":
        unit["status"] = "in-progress"
    unit.setdefault("started", t)
    if unit["status"] == "done":
        unit["completed"] = t
    book["touched"] = t
    return unit


def cmd_book(args) -> None:
    ws = resolve_ws(args)
    if args.action == "add":
        md, method = convert.to_markdown(args.path)
        src = Path(args.path).expanduser().resolve()
        title = args.title or src.stem
        slug = args.slug or convert.slugify(title)
        if (ws.books_dir / slug).exists() and not args.force:
            raise TutorError(f"Book '{slug}' already exists. Pass --slug NAME or --force to re-import (progress is reset).")
        units, strategy = convert.index_units(md)
        (ws.books_dir / slug).mkdir(parents=True, exist_ok=True)
        (ws.books_dir / slug / "book.md").write_text(md, encoding="utf-8")
        for b in ws.books():
            if b.get("status") == "active" and b["slug"] != slug and not args.keep_active:
                b["status"] = "paused"
                ws.save_book(b)
        book = {"slug": slug, "title": title, "source": str(src), "converted_with": method,
                "split_strategy": strategy, "created": iso(today()), "touched": iso(today()),
                "status": "active", "lines": md.count("\n") + 1, "units": units}
        ws.save_book(book)
        render(ws)
        lessons = [u for u in units if u["kind"] == "lesson"]
        warnings = []
        if len(lessons) < 3:
            warnings.append("Few units detected — open book.md, check its structure, and fix index.json units (start/end lines) by hand if needed.")
        if not any(u["exercises"] for u in lessons):
            warnings.append("No exercise markers detected — the tutor will build exercises from each unit's content.")
        emit({"slug": slug, "path": str(ws.books_dir / slug / "book.md"), "converted_with": method,
              "split_strategy": strategy, "units": len(units), "lessons": len(lessons),
              "exercises": sum(u["exercises"] for u in units),
              "answer_units": [u["id"] for u in units if u["kind"] == "answers"],
              "first_units": [f"{u['id']} [{u['kind']}] {u['title']}" for u in units[:12]],
              "warnings": warnings})
    elif args.action == "list":
        emit([{"slug": b["slug"], "title": b["title"], "status": b.get("status"),
               "lessons_done": sum(1 for u in b["units"] if u["kind"] == "lesson" and u["status"] == "done"),
               "lessons": sum(1 for u in b["units"] if u["kind"] == "lesson")} for b in ws.books()])
    elif args.action == "units":
        book = ws.book(args.slug)
        emit([{k: u[k] for k in ("id", "title", "kind", "status", "exercises", "start", "end")} for u in book["units"]])
    elif args.action == "show":
        book = rotation_book(ws, args.slug)
        lines = (ws.books_dir / book["slug"] / "book.md").read_text(encoding="utf-8").split("\n")
        unit = next((u for u in book["units"] if u["id"] == args.unit), None) if args.unit else \
            next((u for u in book["units"] if u["kind"] == "lesson" and u["status"] != "done"), None)
        if unit is None:
            raise TutorError("Unit not found (or every lesson is done).")
        start = unit["start"] + args.offset
        stop = min(unit["end"], start + args.limit - 1)
        print(f"<!-- {book['slug']} {unit['id']} \"{unit['title']}\" lines {start}-{stop} of {unit['start']}-{unit['end']} -->")
        print("\n".join(lines[start - 1:stop]))
        if stop < unit["end"]:
            print(f"<!-- truncated: continue with --offset {args.offset + args.limit} -->")
    elif args.action == "next":
        book = rotation_book(ws, args.slug)
        unit = next((u for u in book["units"] if u["kind"] == "lesson" and u["status"] != "done"), None)
        lines = (ws.books_dir / book["slug"] / "book.md").read_text(encoding="utf-8").split("\n")
        emit({"book": book["slug"], "title": book["title"], "path": str(ws.books_dir / book["slug"] / "book.md"),
              "unit": unit,
              "exercises": convert.unit_exercises(lines, unit["start"], unit["end"]) if unit else [],
              "answer_units": [u["id"] for u in book["units"] if u["kind"] == "answers"],
              "done": unit is None})
    elif args.action == "mark":
        book = ws.book(args.slug)
        unit = mark_unit(book, args.unit, args.exercise, args.score, args.status)
        ws.save_book(book)
        render(ws)
        emit(unit)
    elif args.action == "set":
        book = ws.book(args.slug)
        if args.status == "active":
            for b in ws.books():
                if b.get("status") == "active" and b["slug"] != book["slug"]:
                    b["status"] = "paused"
                    ws.save_book(b)
        book["status"] = args.status
        book["touched"] = iso(today())
        ws.save_book(book)
        render(ws)
        emit({"slug": book["slug"], "status": book["status"]})


def cmd_convert(args) -> None:
    md, method = convert.to_markdown(args.path)
    if args.out:
        Path(args.out).expanduser().write_text(md, encoding="utf-8")
        emit({"out": args.out, "converted_with": method, "lines": md.count("\n") + 1})
    else:
        sys.stdout.write(md)


def cmd_curriculum(args) -> None:
    ws = resolve_ws(args, require=False)
    cur = curriculum(ws)
    if args.action == "tags":
        tags: dict[str, int] = {}
        for rows in cur.values():
            for r in rows:
                for tag in split_tags(r.get("tags", "")):
                    tags[tag] = tags.get(tag, 0) + 1
        emit({"tags": dict(sorted(tags.items(), key=lambda kv: -kv[1])),
              "levels": level_order(cur.get("grammar", []) or cur.get("vocabulary", []))})
    else:
        rows = [r for kind, rs in cur.items() if not args.kind or kind == args.kind for r in rs
                if not args.level or r.get("level") == args.level]
        emit([{k: r.get(k, "") for k in ("id", "kind", "level", "topic", "tags")} for r in rows])


def cmd_html(args) -> None:
    ws = resolve_ws(args)
    quiz = read_json(Path(args.quiz).expanduser(), None)
    if not quiz or not quiz.get("questions"):
        raise TutorError("Quiz JSON needs a non-empty 'questions' list (see reference/html.md).")
    template = (SKILL_DIR / "assets" / "quiz.html").read_text(encoding="utf-8")
    payload = json.dumps(quiz, ensure_ascii=False).replace("</", "<\\/")
    title = quiz.get("title") or f"{ws.lang.capitalize()} quiz"
    html_text = template.replace("__QUIZ_TITLE__", title.replace("<", "&lt;")).replace("__QUIZ_JSON__", payload)
    out = Path(args.out).expanduser() if args.out else \
        ws.root / "quizzes" / f"{iso(today())}-{convert.slugify(title, 'quiz')}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_text, encoding="utf-8")
    emit({"out": str(out), "questions": len(quiz["questions"])})


# --- argument parsing ---------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tutor.py", description=__doc__.split("\n\n")[0])
    p.add_argument("--home", help="workspace root (default $LANG_TUTOR_HOME or ~/.lang-tutor)")
    p.add_argument("--lang", help="target language (default: the active one)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="create a learner workspace and profile")
    s.add_argument("--native", default="english")
    s.add_argument("--framework", default="CEFR")
    s.add_argument("--level", required=True, help="current level, e.g. B1, HSK3, N4")
    s.add_argument("--target", help="target level, e.g. C1")
    s.add_argument("--focus-tags", default="", help="comma list matching curriculum tags")
    s.add_argument("--focus", default="", help="free-text focus areas for profile.md")
    s.add_argument("--goals", default="", help="free-text goals for profile.md")
    s.add_argument("--explain-in", default="target", help="target | native | mixed")
    s.add_argument("--session-minutes", type=int, default=10)
    s.add_argument("--quiz-size", type=int, default=4)
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_init)

    s = sub.add_parser("lang", help="show or switch the active language")
    s.add_argument("name", nargs="?")
    s.set_defaults(fn=cmd_lang)

    s = sub.add_parser("profile", help="show or edit profile frontmatter")
    s.add_argument("action", choices=["show", "set"])
    s.add_argument("key", nargs="?")
    s.add_argument("value", nargs="?")
    s.set_defaults(fn=cmd_profile)

    s = sub.add_parser("status", help="regenerate and print progress.md")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_status)

    s = sub.add_parser("next", help="plan the next micro-session (JSON)")
    s.add_argument("--new", action="store_true", help="introduce new material even if many reviews are due")
    s.set_defaults(fn=cmd_next)

    s = sub.add_parser("due", help="list review items due today")
    s.add_argument("--limit", type=int, default=20)
    s.set_defaults(fn=cmd_due)

    s = sub.add_parser("mistake", help="log a mistake or list logged ones")
    s.add_argument("action", choices=["add", "list"])
    s.add_argument("--key", help="stable slug, reused when the same mistake repeats")
    s.add_argument("--category", choices=CATEGORIES)
    s.add_argument("--wrong", default="")
    s.add_argument("--right", default="")
    s.add_argument("--note", default="")
    s.add_argument("--topic", help="curriculum topic id or name")
    s.add_argument("--source", default="quiz", help="quiz | chat | book")
    s.set_defaults(fn=cmd_mistake)

    s = sub.add_parser("review", help="record the answer to a review item")
    s.add_argument("key")
    s.add_argument("result", choices=["correct", "wrong"])
    s.set_defaults(fn=cmd_review)

    s = sub.add_parser("session", help="log a finished session")
    s.add_argument("--kind", required=True, choices=["grammar", "vocabulary", "review", "book", "free"])
    s.add_argument("--topic")
    s.add_argument("--topic-id")
    s.add_argument("--level")
    s.add_argument("--score", help="e.g. 3/4")
    s.add_argument("--notes")
    s.add_argument("--book")
    s.add_argument("--unit")
    s.add_argument("--exercise")
    s.set_defaults(fn=cmd_session)

    s = sub.add_parser("book", help="import and track textbooks")
    s.add_argument("action", choices=["add", "list", "units", "show", "next", "mark", "set"])
    s.add_argument("path", nargs="?", help="file to import (add)")
    s.add_argument("--slug")
    s.add_argument("--title")
    s.add_argument("--unit")
    s.add_argument("--exercise")
    s.add_argument("--score")
    s.add_argument("--status", choices=["todo", "in-progress", "done", "skip", "active", "paused"])
    s.add_argument("--offset", type=int, default=0)
    s.add_argument("--limit", type=int, default=300)
    s.add_argument("--force", action="store_true")
    s.add_argument("--keep-active", action="store_true", help="don't pause other active books")
    s.set_defaults(fn=cmd_book)

    s = sub.add_parser("convert", help="convert a file to Markdown")
    s.add_argument("path")
    s.add_argument("--out")
    s.set_defaults(fn=cmd_convert)

    s = sub.add_parser("curriculum", help="inspect curriculum topics and tags")
    s.add_argument("action", choices=["list", "tags"])
    s.add_argument("--kind", choices=["grammar", "vocabulary"])
    s.add_argument("--level")
    s.set_defaults(fn=cmd_curriculum)

    s = sub.add_parser("html", help="render a quiz JSON file as a standalone HTML page")
    s.add_argument("--quiz", required=True)
    s.add_argument("--out")
    s.set_defaults(fn=cmd_html)

    # Accept --home/--lang after the command too (`tutor.py init --lang english`);
    # SUPPRESS keeps a missing subcommand flag from clobbering the global one.
    for sp in sub.choices.values():
        sp.add_argument("--home", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
        sp.add_argument("--lang", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "book" and args.action == "add" and not args.path:
        print("error: book add needs a file path", file=sys.stderr)
        return 2
    if args.cmd == "book" and args.action == "mark" and not args.unit:
        print("error: book mark needs --unit", file=sys.stderr)
        return 2
    if args.cmd == "mistake" and args.action == "add" and not (args.key and args.category and args.right):
        print("error: mistake add needs --key, --category and --right", file=sys.stderr)
        return 2
    if args.cmd == "profile" and args.action == "set" and not (args.key and args.value is not None):
        print("error: profile set needs KEY VALUE", file=sys.stderr)
        return 2
    try:
        args.fn(args)
    except (TutorError, convert.ConversionError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
