"""Reading order for OCR words, including pages that have several text columns.

Why this exists: on a tightly set newspaper page Tesseract often joins the lines of neighbouring
columns into one long line, so plain top-to-bottom reading scrambles the sentences. The word boxes
are still accurate, so we look for the empty vertical strip between columns (the gutter) and read
one column at a time, left to right. Large text that is not part of a column (a headline) is read
first when it sits above the columns.

The rule is deliberately conservative. If no clear gutter is found, the split would leave a tiny
sliver of a column, or Tesseract already kept the columns apart, we use the order Tesseract gave us.
It was built on synthetic pages and checked on a few pictures of real ones.
See docs/decisions/ADR-003-ocr-engine.md.
"""

from dataclasses import dataclass
from statistics import median

_MIN_WORDS_FOR_LAYOUT = 40  # too little text to infer a layout from
_HEADLINE_FACTOR = 1.6  # words taller than this many median heights are headline text
_MIN_COLUMN_SHARE = 0.10  # every column must hold at least this share of the body words
_MIN_WORD_CONFIDENCE = 30  # ignore OCR noise when looking for gutters
_LINE_TOLERANCE = 0.6  # words whose centres are within this many median heights share a line
_PARAGRAPH_GAP = 1.6  # a gap this many line pitches wide starts a new paragraph
_MERGED_LINE_SHARE = 0.30  # at least this share of lines must run across a gutter for the rule to act


@dataclass(frozen=True)
class Word:
    text: str
    left: int
    top: int
    width: int
    height: int
    conf: float
    block: int
    par: int
    line: int

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def cx(self) -> float:
        return self.left + self.width / 2

    @property
    def cy(self) -> float:
        return self.top + self.height / 2


def reading_order(words: list[Word]) -> list[list[str]]:
    """Return paragraphs, each a list of lines, in reading order."""
    if not words:
        return []
    med_h = median(w.height for w in words)
    body = [w for w in words if w.height <= _HEADLINE_FACTOR * med_h]
    spanning = [w for w in words if w.height > _HEADLINE_FACTOR * med_h]

    gutters = _find_gutters(body, med_h)
    if not gutters or not _columns_were_merged(words, gutters):
        return _tesseract_order(words)

    columns: list[list[Word]] = [[] for _ in range(len(gutters) + 1)]
    for word in body:
        columns[sum(1 for g in gutters if word.cx > g)].append(word)
    if any(len(col) < _MIN_COLUMN_SHARE * len(body) for col in columns):
        return _tesseract_order(words)

    body_top = min(w.top for w in body)
    above = [w for w in spanning if w.cy < body_top]
    elsewhere = [w for w in spanning if w.cy >= body_top]

    paragraphs: list[list[str]] = []
    for group in (above, *columns, elsewhere):
        paragraphs.extend(_paragraphs(group, med_h))
    return paragraphs


def _columns_were_merged(words: list[Word], gutters: list[int]) -> bool:
    """True when Tesseract ran neighbouring columns together into the same lines.

    Only then is its order wrong in the way this module fixes. If it already kept the columns apart, its
    own order is better than a single set of gutters applied to the whole page: on a page with a photo,
    a boxed advert or columns that change width, one set of gutters cuts the text in the wrong places
    (59% of words in order, against 77% for Tesseract alone, on a real multi-column page).
    """
    lines: dict[tuple[int, int, int], list[Word]] = {}
    for word in words:
        lines.setdefault((word.block, word.par, word.line), []).append(word)
    long_lines = [line for line in lines.values() if len(line) >= 4]
    if not long_lines:
        return False
    crossing = sum(
        1
        for line in long_lines
        if any(any(w.right < g for w in line) and any(w.left > g for w in line) for g in gutters)
    )
    return crossing / len(long_lines) >= _MERGED_LINE_SHARE


def _find_gutters(body: list[Word], med_h: float) -> list[int]:
    """x positions in the middle of each empty vertical strip between columns."""
    reliable = [w for w in body if w.conf >= _MIN_WORD_CONFIDENCE]
    if len(reliable) < _MIN_WORDS_FOR_LAYOUT:
        return []
    x0 = min(w.left for w in reliable)
    x1 = max(w.right for w in reliable)
    coverage = [0] * (x1 - x0 + 1)
    for w in reliable:
        for x in range(w.left - x0, w.right - x0 + 1):
            coverage[x] += 1

    tolerance = max(2, round(0.01 * len(reliable)))  # a few stray marks may sit in a gutter
    min_gap = max(12, round(0.8 * med_h))
    gutters: list[int] = []
    start: int | None = None
    for x, count in enumerate(coverage):
        if count <= tolerance:
            if start is None:
                start = x
        else:
            if start is not None and start > 0 and x - start >= min_gap:
                gutters.append(x0 + (start + x - 1) // 2)
            start = None
    return gutters


def _tesseract_order(words: list[Word]) -> list[list[str]]:
    """Keep Tesseract's own grouping: block, paragraph and line numbers."""
    paragraphs: list[list[str]] = []
    lines: list[str] = []
    current: list[str] = []
    par_key = line_key = None
    for word in words:
        new_par = (word.block, word.par)
        new_line = (word.block, word.par, word.line)
        if new_par != par_key:
            if current:
                lines.append(" ".join(current))
                current = []
            if lines:
                paragraphs.append(lines)
                lines = []
            par_key, line_key = new_par, None
        if new_line != line_key:
            if current:
                lines.append(" ".join(current))
                current = []
            line_key = new_line
        current.append(word.text)
    if current:
        lines.append(" ".join(current))
    if lines:
        paragraphs.append(lines)
    return paragraphs


def _paragraphs(words: list[Word], med_h: float) -> list[list[str]]:
    """Rebuild lines and paragraphs for one group of words from their positions."""
    if not words:
        return []
    rows: list[list[Word]] = []
    for word in sorted(words, key=lambda w: w.cy):
        if rows and abs(word.cy - _mean_cy(rows[-1])) <= _LINE_TOLERANCE * med_h:
            rows[-1].append(word)
        else:
            rows.append([word])
    centres = [_mean_cy(row) for row in rows]
    texts = [" ".join(w.text for w in sorted(row, key=lambda w: w.left)) for row in rows]

    gaps = [b - a for a, b in zip(centres, centres[1:], strict=False)]
    pitch = median(gaps) if gaps else med_h * 1.4
    paragraphs: list[list[str]] = [[texts[0]]]
    for gap, text in zip(gaps, texts[1:], strict=True):
        if gap > _PARAGRAPH_GAP * pitch:
            paragraphs.append([])
        paragraphs[-1].append(text)
    return paragraphs


def _mean_cy(row: list[Word]) -> float:
    return sum(w.cy for w in row) / len(row)
