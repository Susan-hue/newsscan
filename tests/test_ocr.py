import io
import shutil

import pytest
from PIL import Image

from newsscan.ingest.ocr import TesseractEngine, _assemble
from newsscan.ingest.preprocess import prepare_for_ocr
from tests.conftest import make_image


def word_table(rows):
    """rows: (text, block, par, line, conf). Positions are made up: 100 px per word, 30 px per line."""
    keys = ["text", "block_num", "par_num", "line_num", "conf"]
    table = {key: [row[i] for row in rows] for i, key in enumerate(keys)}
    table["left"] = [100 * i for i in range(len(rows))]
    table["top"] = [30 * row[3] for row in rows]
    table["width"] = [90] * len(rows)
    table["height"] = [20] * len(rows)
    return table


def test_assemble_rebuilds_lines_and_paragraphs():
    data = word_table(
        [
            ("", 0, 0, 0, -1),  # structural row with no text
            ("The", 1, 1, 1, 95),
            ("council", 1, 1, 1, 90),
            ("met", 1, 1, 2, 80),
            ("Second", 1, 2, 1, 70),
            ("paragraph", 1, 2, 1, 60),
        ]
    )
    result = _assemble(data, "tesseract")
    assert result.text == "The council\nmet\n\nSecond paragraph"
    assert result.mean_confidence == 79.0


def test_assemble_with_no_words_gives_empty_text_and_no_confidence():
    result = _assemble(word_table([("", 0, 0, 0, -1)]), "tesseract")
    assert result.text == ""
    assert result.mean_confidence is None


def test_prepare_for_ocr_scales_small_images_up_and_big_ones_down():
    small = prepare_for_ocr(Image.new("RGB", (500, 300), "white"))
    assert max(small.size) == 1500 and small.mode == "L"
    big = prepare_for_ocr(Image.new("RGB", (9000, 3000), "white"))
    assert max(big.size) == 4500


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract is not installed")
def test_tesseract_reads_a_rendered_sentence():
    png = make_image("The council approved the budget", size=(1800, 200))
    page = Image.open(io.BytesIO(png))
    result = TesseractEngine().recognize(prepare_for_ocr(page))
    assert "budget" in result.text.lower()
    assert result.mean_confidence is not None and result.mean_confidence > 60
