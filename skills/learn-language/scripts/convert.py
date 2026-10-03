"""Convert learning material to Markdown and split it into study units.

Standard library only, so it runs on any Python 3.9+ an agent can reach.
Markdown, text, HTML, DOCX, and EPUB are handled in-process. PDF needs a text
extractor; pdf_to_md tries, in order, an importable library, a CLI on PATH,
and finally an ephemeral `uv` environment, so an agent can always prepare one
itself (`uv` or `pip install pymupdf4llm`) without the user doing anything.
"""
from __future__ import annotations

import posixpath
import re
import shutil
import subprocess
import sys
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote


class ConversionError(Exception):
    pass


# --- HTML -> Markdown ---------------------------------------------------------

class _HTMLToMD(HTMLParser):
    BLOCK = {"p", "div", "section", "article", "blockquote", "header", "footer",
             "figure", "figcaption", "aside", "nav", "main", "dd", "dt", "hr"}
    SKIP = {"script", "style", "head", "title", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[tuple[str, str]] = []  # (text, kind)
        self.buf: list[str] = []
        self.skip = 0
        self.lists: list[list] = []  # [tag, counter]
        self.heading = 0
        self.prefix = ""
        self.kind = "p"
        self.pre = False
        self.table: list[list[str]] | None = None
        self.row: list[str] | None = None
        self.cell: list[str] | None = None

    def _sink(self) -> list[str]:
        return self.cell if self.cell is not None else self.buf

    def _flush(self) -> None:
        text = "".join(self.buf)
        self.buf = []
        if self.pre:
            text = text.strip("\n")
            if text.strip():
                self.blocks.append(("```\n" + text + "\n```", "p"))
            return
        lines = [re.sub(r"[ \t\r\f\v]+", " ", ln).strip() for ln in text.split("\n")]
        text = "\n".join(ln for ln in lines if ln)
        text = re.sub(r"\*\*\s*\*\*", "", text).strip()  # empty bold from styled whitespace
        if not text:
            self.prefix, self.kind = "", "p"
            return
        if self.heading:
            text = "#" * self.heading + " " + text.replace("\n", " ")
        elif self.prefix:
            text = self.prefix + text.replace("\n", " ")
        self.blocks.append((text, self.kind))
        self.prefix, self.kind = "", "p"

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
            return
        if self.skip:
            return
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._flush()
            self.heading = int(tag[1])
        elif tag in self.BLOCK:
            self._flush()
        elif tag == "br":
            self._sink().append("\n")
        elif tag in ("ul", "ol"):
            self._flush()
            self.lists.append([tag, 0])
        elif tag == "li":
            self._flush()
            depth = max(len(self.lists), 1)
            marker = "- "
            if self.lists and self.lists[-1][0] == "ol":
                self.lists[-1][1] += 1
                marker = f"{self.lists[-1][1]}. "
            self.prefix = "  " * (depth - 1) + marker
            self.kind = "li"
        elif tag in ("strong", "b"):
            self._sink().append("**")
        elif tag in ("em", "i"):
            self._sink().append("*")
        elif tag == "pre":
            self._flush()
            self.pre = True
        elif tag == "table":
            self._flush()
            self.table = []
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(self.skip - 1, 0)
            return
        if self.skip:
            return
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._flush()
            self.heading = 0
        elif tag in self.BLOCK or tag == "li":
            self._flush()
        elif tag in ("ul", "ol"):
            self._flush()
            if self.lists:
                self.lists.pop()
        elif tag in ("strong", "b"):
            self._sink().append("**")
        elif tag in ("em", "i"):
            self._sink().append("*")
        elif tag == "pre":
            self._flush()
            self.pre = False
        elif tag in ("td", "th") and self.cell is not None and self.row is not None:
            self.row.append(re.sub(r"\s+", " ", "".join(self.cell)).strip().replace("|", "\\|"))
            self.cell = None
        elif tag == "tr" and self.row is not None and self.table is not None:
            if any(self.row):
                self.table.append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            self.blocks.append((_md_table(self.table), "p"))
            self.table = None

    def handle_data(self, data):
        if not self.skip:
            self._sink().append(data)

    def result(self) -> str:
        self._flush()
        out: list[str] = []
        prev = None
        for text, kind in self.blocks:
            if not text:
                continue
            if out:
                out.append("\n" if kind == "li" and prev == "li" else "\n\n")
            out.append(text)
            prev = kind
        return "".join(out)


def _md_table(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    lines = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * width]
    lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(lines)


def html_to_md(html_text: str) -> str:
    parser = _HTMLToMD()
    parser.feed(html_text)
    parser.close()
    return parser.result()


# --- DOCX ---------------------------------------------------------------------

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _docx_heading_styles(z: zipfile.ZipFile) -> dict[str, int]:
    """Map styleId -> heading level, using style names ("heading 2", "Title")."""
    levels: dict[str, int] = {}
    try:
        root = ET.fromstring(z.read("word/styles.xml"))
    except KeyError:
        return levels
    for style in root.iter(_W + "style"):
        sid = style.get(_W + "styleId") or ""
        name_el = style.find(_W + "name")
        name = (name_el.get(_W + "val") if name_el is not None else sid).lower()
        m = re.match(r"heading\s*(\d)", name)
        if m:
            levels[sid] = int(m.group(1))
        elif name in ("title",):
            levels[sid] = 1
    return levels


def _docx_text(el) -> str:
    parts = []
    for node in el.iter():
        if node.tag == _W + "t" and node.text:
            parts.append(node.text)
        elif node.tag == _W + "tab":
            parts.append("\t")
        elif node.tag in (_W + "br", _W + "cr"):
            parts.append("\n")
    return "".join(parts)


def docx_to_md(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        heading_styles = _docx_heading_styles(z)
        root = ET.fromstring(z.read("word/document.xml"))
    body = root.find(_W + "body")
    if body is None:
        return ""
    blocks: list[tuple[str, str]] = []
    for el in body:
        if el.tag == _W + "p":
            text = _docx_text(el).strip()
            if not text:
                continue
            ppr = el.find(_W + "pPr")
            level = 0
            is_list = False
            if ppr is not None:
                style = ppr.find(_W + "pStyle")
                if style is not None:
                    level = heading_styles.get(style.get(_W + "val") or "", 0)
                outline = ppr.find(_W + "outlineLvl")
                if not level and outline is not None:
                    level = int(outline.get(_W + "val") or 0) + 1
                is_list = ppr.find(_W + "numPr") is not None
            if level:
                blocks.append(("#" * min(level, 6) + " " + " ".join(text.split()), "p"))
            elif is_list:
                blocks.append(("- " + text.replace("\n", " "), "li"))
            else:
                blocks.append((text, "p"))
        elif el.tag == _W + "tbl":
            rows = []
            for tr in el.iter(_W + "tr"):
                cells = [" ".join(_docx_text(tc).split()).replace("|", "\\|") for tc in tr.findall(_W + "tc")]
                if any(cells):
                    rows.append(cells)
            if rows:
                blocks.append((_md_table(rows), "p"))
    out: list[str] = []
    prev = None
    for text, kind in blocks:
        if out:
            out.append("\n" if kind == "li" and prev == "li" else "\n\n")
        out.append(text)
        prev = kind
    return "".join(out)


# --- EPUB ---------------------------------------------------------------------

def epub_to_md(path: Path) -> str:
    opf_ns = "{http://www.idpf.org/2007/opf}"
    with zipfile.ZipFile(path) as z:
        container = ET.fromstring(z.read("META-INF/container.xml"))
        rootfile = next(
            (el.get("full-path") for el in container.iter() if el.tag.endswith("rootfile")), None
        )
        if not rootfile:
            raise ConversionError("EPUB has no rootfile in META-INF/container.xml")
        opf = ET.fromstring(z.read(rootfile))
        manifest = {item.get("id"): item.get("href") for item in opf.iter(opf_ns + "item")}
        base = posixpath.dirname(rootfile)
        names = set(z.namelist())
        parts = []
        for ref in opf.iter(opf_ns + "itemref"):
            href = manifest.get(ref.get("idref"))
            if not href:
                continue
            full = posixpath.normpath(posixpath.join(base, unquote(href.split("#")[0])))
            if full not in names:
                continue
            md = html_to_md(z.read(full).decode("utf-8", "replace"))
            if md.strip():
                parts.append(md)
    return "\n\n".join(parts)


# --- PDF ----------------------------------------------------------------------

_PYMUPDF_SNIPPET = (
    "import sys, pymupdf4llm\n"
    "chunks = pymupdf4llm.to_markdown(sys.argv[1], page_chunks=True)\n"
    "sys.stdout.write('\\n\\n'.join('<!-- page %d -->\\n\\n%s' % (i + 1, c['text']) for i, c in enumerate(chunks)))\n"
)

PDF_INSTALL_HINT = (
    "No PDF text extractor available. Any one of these fixes it:\n"
    "  - install uv (https://docs.astral.sh/uv/) — the converter then fetches pymupdf4llm on demand\n"
    "  - python3 -m pip install --user pymupdf4llm   (best: keeps headings)\n"
    "  - python3 -m pip install --user pypdf\n"
    "  - brew install poppler   (provides pdftotext)"
)


def _pages_to_md(pages: list[str]) -> str:
    return "\n\n".join(f"<!-- page {i + 1} -->\n\n{p.strip()}" for i, p in enumerate(pages))


def _run(cmd: list[str]) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    if proc.returncode != 0:
        raise ConversionError(f"{cmd[0]} failed: {proc.stderr.strip()[-400:]}")
    return proc.stdout


def pdf_to_md(path: Path) -> tuple[str, str]:
    attempts: list[str] = []
    try:
        import pymupdf4llm  # type: ignore

        chunks = pymupdf4llm.to_markdown(str(path), page_chunks=True)
        return _pages_to_md([c["text"] for c in chunks]), "pymupdf4llm"
    except ImportError:
        pass
    try:
        import pypdf  # type: ignore

        reader = pypdf.PdfReader(str(path))
        return _pages_to_md([page.extract_text() or "" for page in reader.pages]), "pypdf"
    except ImportError:
        pass
    if shutil.which("pdftotext"):
        try:
            text = _run(["pdftotext", "-enc", "UTF-8", str(path), "-"])
            return _pages_to_md(text.split("\f")), "pdftotext"
        except ConversionError as e:
            attempts.append(str(e))
    if shutil.which("markitdown"):
        try:
            return _run(["markitdown", str(path)]), "markitdown"
        except ConversionError as e:
            attempts.append(str(e))
    if shutil.which("uv"):
        try:
            text = _run(["uv", "run", "--no-project", "--quiet", "--with", "pymupdf4llm",
                         "python", "-c", _PYMUPDF_SNIPPET, str(path)])
            return text, "pymupdf4llm (uv)"
        except ConversionError as e:
            attempts.append(str(e))
    detail = ("\nAttempts:\n  " + "\n  ".join(attempts)) if attempts else ""
    raise ConversionError(PDF_INSTALL_HINT + detail)


# --- dispatch -----------------------------------------------------------------

def _fallback_tools(path: Path) -> tuple[str, str]:
    """Formats with no in-process reader (.doc, .odt, .rtf, .pptx, ...)."""
    if shutil.which("markitdown"):
        return _run(["markitdown", str(path)]), "markitdown"
    if shutil.which("pandoc"):
        return _run(["pandoc", str(path), "-t", "gfm", "--wrap=none"]), "pandoc"
    if sys.platform == "darwin" and shutil.which("textutil"):
        return html_to_md(_run(["textutil", "-convert", "html", "-stdout", str(path)])), "textutil"
    raise ConversionError(
        f"No converter for {path.suffix} files. Install markitdown (`uv tool install markitdown`) "
        "or pandoc, or export the file to PDF/DOCX/EPUB first."
    )


def to_markdown(path) -> tuple[str, str]:
    """Return (markdown, method) for a learning-material file."""
    path = Path(path).expanduser()
    if not path.is_file():
        raise ConversionError(f"File not found: {path}")
    ext = path.suffix.lower()
    if ext in (".md", ".markdown", ".txt", ".text"):
        md, method = path.read_text(encoding="utf-8", errors="replace"), "copy"
    elif ext in (".html", ".htm", ".xhtml"):
        md, method = html_to_md(path.read_text(encoding="utf-8", errors="replace")), "html"
    elif ext == ".docx":
        md, method = docx_to_md(path), "docx"
    elif ext == ".epub":
        md, method = epub_to_md(path), "epub"
    elif ext == ".pdf":
        md, method = pdf_to_md(path)
    else:
        md, method = _fallback_tools(path)
    md = clean_markdown(md)
    letters = len(re.sub(r"\s|<!-- page \d+ -->", "", md))
    if letters < 200:
        hints = {
            ".pdf": " It looks scanned — OCR it first (e.g. `ocrmypdf in.pdf out.pdf`) and retry.",
            ".epub": " It looks like an image-only EPUB (page scans). Convert it to PDF "
                     "(calibre: `ebook-convert in.epub out.pdf`), OCR that (`ocrmypdf out.pdf ocr.pdf`), and import the OCR'd PDF.",
        }
        hint = hints.get(ext, "")
        raise ConversionError(f"Extracted almost no text from {path.name} ({letters} chars).{hint}")
    return md, method


def clean_markdown(md: str) -> str:
    md = md.replace("\r\n", "\n").replace("\r", "\n").replace("­", "")
    md = "\n".join(line.rstrip() for line in md.split("\n"))
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip() + "\n"


# --- unit indexing ------------------------------------------------------------

_UNIT_WORDS = (
    r"unit|chapter|lesson|module|part|section|topic|week|day|"
    r"bài|chương|phần|tuần|lektion|kapitel|einheit|leçon|chapitre|unité|"
    r"unidad|lección|capítulo|lezione|capitolo|unità|lição|урок|глава|раздел|"
    r"hoofdstuk|les|rozdział|lekcja|ders|bölüm|ünite|kapitola|lekce"
)
UNIT_RE = re.compile(
    rf"^\s*(?:(?:{_UNIT_WORDS})\s*(?:\d+|[IVXLC]+(?![a-z]))"
    r"|第\s*[0-9一二三四五六七八九十百]+\s*[課课章单元回]"
    r"|제?\s*\d+\s*(?:과|단원|장)(?!\w))",
    re.IGNORECASE,
)
_EX_WORDS = (
    r"exercises?|practice|activity|task|drill|quiz|test yourself|check yourself|"
    r"bài tập|luyện tập|thực hành|übung(?:en)?|aufgabe|exercices?|ejercicios?|práctica|"
    r"esercizi[oa]?|exercícios?|упражнени[ея]|zadanie|ćwiczenie|alıştırma|oefening|"
    r"練習|练习|연습|문제"
)
EXERCISE_RE = re.compile(
    rf"^\s*(?:#+\s*|\*\*|\d+[.)]\s*)?(?:{_EX_WORDS})(?![a-zà-ỹ])|^\s*(?:#+\s*)?ex\.\s*\d",
    re.IGNORECASE,
)
# Workbook-style numbered task instructions: "**1 Complete these sentences ...**",
# or unit.exercise numbering: "1.3 Write questions." / "###### **12.2 Put the verb ...**".
NUMBERED_TASK_RE = re.compile(
    r"^\s*(?:#+\s*)?(?:\*\*\s*\d{1,2}\s+[A-Z][a-z]|(?:\*\*)?\s*\d{1,3}\.\d{1,2}\s+(?:\*\*\s*)?[A-Z][a-z])"
)
_ANSWERS_RE = re.compile(
    r"answer key|answers|key to\b|solutions|đáp án|lời giải|lösungen|"
    r"corrigés?|soluciones|soluzioni|respostas|ответы|解答|答案|정답",
    re.IGNORECASE,
)
_FRONT_RE = re.compile(
    r"^(?:table of )?contents$|^preface|^foreword|^introduction$|^acknowledg|^copyright|"
    r"^index$|^appendix|^additional exercises|^study guide|^bibliography|^about (?:the|this) (?:author|\w*book|course)|^mục lục|^lời (?:nói đầu|giới thiệu)|"
    r"^inhalt|^sommaire|^índice|^目次|^目录|^차례",
    re.IGNORECASE,
)

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*#*\s*$")


def _clean_title(title: str) -> str:
    return re.sub(r"[*_`]+", "", title).strip()[:120]


def _headings(lines: list[str]) -> list[tuple[int, int, str]]:
    """(line_index, level, title) for markdown headings outside code fences."""
    out = []
    fence = False
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            fence = not fence
            continue
        if fence:
            continue
        m = _HEADING_RE.match(line)
        if m:
            out.append((i, len(m.group(1)), _clean_title(m.group(2))))
    return out


def _dedupe(heads: list[tuple[int, int, str]]) -> list[tuple[int, int, str]]:
    """Drop a heading that repeats the previous same-level title (running page headers)."""
    out: list[tuple[int, int, str]] = []
    last: dict[int, str] = {}
    for h in heads:
        if last.get(h[1], "").lower() != h[2].lower():
            out.append(h)
        last[h[1]] = h[2]
        for deeper in [lv for lv in last if lv > h[1]]:
            del last[deeper]
    return out


_UNIT_NUM_RE = re.compile(rf"^(?:{_UNIT_WORDS})\s*(\d+)", re.IGNORECASE)
_END_MATTER_RE = re.compile(
    r"^(?:appendix\s*\d+|additional exercises|study guide|key to (?:the )?(?:exercises|additional exercises|study guide)|"
    r"answer key|answers|index)\b",
    re.IGNORECASE,
)


def _numbered_sequence(lines: list[str]) -> tuple[list[tuple[int, str]], int]:
    """Unit starts for books whose "Unit N" line repeats as a running header on every
    page of the unit (two-page-spread workbooks): first line of each number, in order,
    then the end matter (appendices, answer keys, index). Returns (splits, unit_count)."""
    seq: list[tuple[int, str]] = []
    last = 0
    for i, line in enumerate(lines):
        text = _clean_title(line.lstrip("#").strip())
        if len(text) > 120 or len(re.findall(rf"(?:{_UNIT_WORDS})\s*\d", text, re.IGNORECASE)) > 1:
            continue  # contents lines list several units
        m = _UNIT_NUM_RE.match(text)
        if m and last < int(m.group(1)) <= last + 3:
            last = int(m.group(1))
            if text == m.group(0):  # bare running header: borrow the heading that follows
                nxt = next((l for l in lines[i + 1:i + 5] if l.strip() and not l.lstrip().startswith("<!--")), "")
                if nxt.lstrip().startswith("#") and not EXERCISE_RE.match(_clean_title(nxt.lstrip("#").strip())):
                    text = f"{text} {_clean_title(nxt.lstrip('#').strip())}"
            seq.append((i, text))
    units = len(seq)
    if units < 3:
        return seq, units
    # Still-bare titles: take the unit's name from the contents pages ("12 for and since ...").
    first = seq[0][0]
    names: dict[int, str] = {}
    for line in lines[:first]:
        parts = re.split(r"(?:^|(?<=\s))(\d{1,3})\s+(?=[^\d\s])", _clean_title(line).lstrip("-• ").strip())
        for n, title in zip(parts[1::2], parts[2::2]):
            title = re.sub(r"\s+", " ", title).strip()
            if re.search(r"[^\W\d_]", title) and len(title) <= 90:
                names.setdefault(int(n), title)  # units are listed before appendices
    for k, (i, text) in enumerate(seq):
        m = _UNIT_NUM_RE.match(text)
        if m and text == m.group(0) and names.get(int(m.group(1))):
            seq[k] = (i, f"{text} {names[int(m.group(1))]}")
    seen: set[str] = set()
    for i in range(seq[-1][0] + 1, len(lines)):
        text = _clean_title(lines[i].lstrip("#").strip())
        m = _END_MATTER_RE.match(text) if len(text) <= 80 else None
        key = re.sub(r"\s+", " ", m.group(0).lower()) if m else ""
        if m and key not in seen:  # running headers repeat "Appendix 1" on every page
            seen.add(key)
            seq.append((i, text))
    return seq, units


def _pick_split(lines: list[str]) -> tuple[list[tuple[int, str]], str]:
    split, strategy = _pick_heading_split(lines)
    seq, units = _numbered_sequence(lines)
    lessons = sum(1 for _, title in split if classify_unit(title) == "lesson")
    # A heading split on unit names is already good; only replace it when the running
    # headers find far more units. Any other heading split loses to more units.
    span = (seq[units - 1][0] - seq[0][0]) / max(len(lines), 1) if units >= 3 else 0
    # The units must run through the book (not "Part 1/2/3" inside one chapter).
    if span >= 0.4 and (units > 1.5 * lessons if "unit names" in strategy else units >= lessons):
        return seq, "numbered unit names (first line of each unit number)"
    return split, strategy


def _pick_heading_split(lines: list[str]) -> tuple[list[tuple[int, str]], str]:
    heads = _dedupe(_headings(lines))
    # Unit-named headings ("Unit 3", "Lesson 4") win when they dominate their level
    # with distinct titles and outnumber any shallower structural level (units are
    # more numerous than their containers). Sub-parts ("Part 1/2/3") fail one of these.
    shallower_max = 0
    for level in sorted({h[1] for h in heads}):
        at = [h for h in heads if h[1] == level]
        named = [h for h in at if UNIT_RE.match(h[2])]
        distinct = {re.sub(r"\W+", " ", h[2].lower()).strip() for h in named}
        if (len(named) >= 2 and len(distinct) == len(named) and len(named) >= 0.4 * len(at)
                and len(named) > shallower_max):
            return [(h[0], h[2]) for h in at], f"headings (level {level}, unit names)"
        if len(at) >= 3:
            shallower_max = max(shallower_max, len(at))
    for level in range(1, 7):
        at = [h for h in heads if h[1] == level]
        if 3 <= len(at) <= 400:
            return [(h[0], h[2]) for h in at], f"headings (level {level})"
    pseudo = [(i, _clean_title(line)) for i, line in enumerate(lines)
              if len(line.strip()) <= 80 and UNIT_RE.match(_clean_title(line))]
    if len(pseudo) >= 2:
        return pseudo, "unit-name lines"
    step = 200
    return [(i, f"Part {i // step + 1}") for i in range(0, len(lines), step)], f"fixed {step}-line chunks"


def classify_unit(title: str) -> str:
    if _ANSWERS_RE.search(title):
        return "answers"
    if _FRONT_RE.search(title.strip()):
        return "front"
    return "lesson"


def unit_exercises(lines: list[str], start: int, end: int) -> list[dict]:
    """Exercise markers inside a unit; start/end are 1-indexed inclusive."""
    rng = range(start - 1, min(end, len(lines)))
    # Numbered tasks ("1.3 Write questions") are the exercises when present; a bare
    # "Exercises" header above them is not one more.
    hits = [i for i in rng if NUMBERED_TASK_RE.match(lines[i])] or [i for i in rng if EXERCISE_RE.match(lines[i])]
    return [{"n": n + 1, "line": i + 1, "label": _clean_title(lines[i].lstrip("#").strip())[:80]}
            for n, i in enumerate(hits)]


def index_units(md: str) -> tuple[list[dict], str]:
    """Split markdown into study units. Returns (units, strategy)."""
    lines = md.split("\n")
    splits, strategy = _pick_split(lines)
    units = []
    preamble = [l for l in lines[: splits[0][0]] if l.strip() and not l.strip().startswith("<!--")] if splits else []
    if preamble:
        splits = [(0, "Front matter")] + splits
    for n, (start, title) in enumerate(splits):
        end = splits[n + 1][0] if n + 1 < len(splits) else len(lines)
        kind = "front" if title == "Front matter" else classify_unit(title)
        units.append({
            "id": f"u{len(units) + 1:02d}",
            "title": title,
            "kind": kind,
            "start": start + 1,
            "end": end,
            # A lesson with no marked exercise still has one block of practice.
            "exercises": max(len(unit_exercises(lines, start + 1, end)), 1) if kind == "lesson" else 0,
            "status": "todo" if kind == "lesson" else "skip",
            "exercise_progress": {},
        })
    return units, strategy


def slugify(text: str, fallback: str = "book") -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")[:60].strip("-")
    return slug or fallback


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: convert.py FILE  (prints Markdown to stdout)")
    try:
        text, used = to_markdown(sys.argv[1])
    except ConversionError as err:
        sys.exit(f"error: {err}")
    sys.stdout.write(text)
    print(f"[converted with {used}]", file=sys.stderr)
