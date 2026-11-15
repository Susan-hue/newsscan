"""Reading order: column splitting, headline handling and the safe fallbacks."""

from newsscan.ingest.layout import Word, reading_order
from newsscan.ingest.ocr import _assemble

LINE_H = 20
PITCH = 30


def _line(words: list[str], *, left: int, top: int, height: int = LINE_H, block=1, par=1, line=1):
    out, x = [], left
    for text in words:
        width = 12 * len(text)
        out.append(Word(text, x, top, width, height, 90.0, block, par, line))
        x += width + 10
    return out


def _column(prefix: str, *, left: int, lines: int = 12, top: int = 100, block: int = 1) -> list[Word]:
    words: list[Word] = []
    for n in range(lines):
        words += _line(
            [f"{prefix}{n}a", f"{prefix}{n}b", f"{prefix}{n}c"],
            left=left,
            top=top + n * PITCH,
            block=block,
            line=n + 1,
        )
    return words


def _flat(paragraphs: list[list[str]]) -> list[str]:
    return [line for par in paragraphs for line in par]


def test_empty_input():
    assert reading_order([]) == []


def test_two_columns_are_read_one_after_the_other():
    left = _column("L", left=50)
    right = _column("R", left=400)
    # Tesseract-style joined lines would interleave; the word boxes are still in the right place.
    interleaved = [w for pair in zip(left, right, strict=True) for w in pair]

    lines = _flat(reading_order(interleaved))

    assert lines[:12] == [f"L{n}a L{n}b L{n}c" for n in range(12)]
    assert lines[12:] == [f"R{n}a R{n}b R{n}c" for n in range(12)]


def test_headline_above_columns_is_read_first():
    headline = _line(["BIG", "NEWS", "TODAY"], left=50, top=20, height=48, block=9)
    words = headline + _column("L", left=50) + _column("R", left=400)

    lines = _flat(reading_order(words))

    assert lines[0] == "BIG NEWS TODAY"
    assert lines[1] == "L0a L0b L0c"
    assert lines[-1] == "R11a R11b R11c"


def test_three_columns():
    words = _column("A", left=40) + _column("B", left=300) + _column("C", left=560)
    lines = _flat(reading_order(words))
    assert [ln[0] for ln in lines[::12]] == ["A", "B", "C"]


def test_single_column_keeps_tesseract_order_and_paragraphs():
    words = (
        _line(["First", "paragraph", "line", "one"], left=50, top=100, par=1, line=1)
        + _line(["still", "first", "paragraph", "here"], left=50, top=130, par=1, line=2)
        + _line(["Second", "paragraph", "starts", "now"], left=50, top=190, par=2, line=1)
    )
    # Pad so the page has enough words to be considered for layout analysis at all.
    words += _line(["filler"] * 10, left=50, top=250, par=3, line=1)

    paragraphs = reading_order(words)

    assert paragraphs[0] == ["First paragraph line one", "still first paragraph here"]
    assert paragraphs[1] == ["Second paragraph starts now"]


def test_tiny_sliver_is_not_treated_as_a_column():
    # A lone word far to the right (a page number, say) must not become a second "column".
    words = _column("L", left=50, lines=12) + _line(["7"], left=700, top=100, block=2)
    lines = _flat(reading_order(words))
    assert lines[0] == "L0a L0b L0c"
    assert "7" in lines


def test_too_little_text_falls_back_to_tesseract_order():
    words = _line(["Short", "note"], left=50, top=50) + _line(["tail"], left=400, top=50, block=2)
    assert _flat(reading_order(words)) == ["Short note", "tail"]


def test_assemble_uses_reading_order_and_confidence():
    words = _column("L", left=50) + _column("R", left=400)
    data = {
        "text": [w.text for w in words] + ["", "   "],
        "conf": [w.conf for w in words] + [-1, -1],
        "left": [w.left for w in words] + [0, 0],
        "top": [w.top for w in words] + [0, 0],
        "width": [w.width for w in words] + [0, 0],
        "height": [w.height for w in words] + [0, 0],
        "block_num": [w.block for w in words] + [0, 0],
        "par_num": [w.par for w in words] + [0, 0],
        "line_num": [w.line for w in words] + [0, 0],
    }

    result = _assemble(data, "tesseract")

    assert result.mean_confidence == 90.0
    assert result.engine == "tesseract"
    assert result.text.index("L11a") < result.text.index("R0a")


def test_columns_tesseract_already_kept_apart_keep_its_order():
    # Each column is its own block, as Tesseract gives them when it separated the columns correctly.
    left = _column("L", left=50, block=1)
    right = _column("R", left=400, block=2)
    # ...but its blocks are not in x order, so the result shows whose order was used.
    words = right + left

    lines = _flat(reading_order(words))

    assert lines[:12] == [f"R{n}a R{n}b R{n}c" for n in range(12)]
    assert lines[12:] == [f"L{n}a L{n}b L{n}c" for n in range(12)]
