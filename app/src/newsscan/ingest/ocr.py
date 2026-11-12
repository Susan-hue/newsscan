"""OCR behind a small interface, so the engine can be swapped without touching the pipeline.

The default engine is Tesseract (free, runs locally). A cloud engine such as AWS Textract could
be added as another class with the same recognize() method. See docs/decisions/ADR-003.
"""

from dataclasses import dataclass
from typing import Protocol

import pytesseract
from PIL import Image

from newsscan.config import get_settings
from newsscan.ingest.layout import Word, reading_order


class OCRFailed(RuntimeError):
    """The OCR engine could not read the page. The message is safe to show to the user."""


@dataclass(frozen=True)
class OCRResult:
    text: str
    mean_confidence: float | None  # 0 to 100, or None when the engine gives no confidence
    engine: str


class OCREngine(Protocol):
    name: str

    def recognize(self, image: Image.Image) -> OCRResult: ...


class TesseractEngine:
    name = "tesseract"

    def __init__(self, lang: str = "eng", timeout: int = 60, psm: int = 3) -> None:
        self.lang = lang
        self.timeout = timeout
        # psm 3 = fully automatic page segmentation. Column order is fixed up in layout.py.
        self.psm = psm

    def recognize(self, image: Image.Image) -> OCRResult:
        try:
            data = pytesseract.image_to_data(
                image,
                lang=self.lang,
                config=f"--psm {self.psm}",
                timeout=self.timeout,
                output_type=pytesseract.Output.DICT,
            )
        except RuntimeError as exc:  # pytesseract raises RuntimeError on timeout
            raise OCRFailed("Reading the page took too long. Try a smaller or clearer image.") from exc
        except pytesseract.TesseractError as exc:
            raise OCRFailed("The text reader failed on this page.") from exc
        return _assemble(data, self.name)


def _assemble(data: dict, engine: str) -> OCRResult:
    """Turn Tesseract's word table into text in reading order, plus the average confidence."""
    words: list[Word] = []
    confidences: list[float] = []
    for i, raw in enumerate(data["text"]):
        text = raw.strip()
        if not text:
            continue
        conf = float(data["conf"][i])
        words.append(
            Word(
                text=text,
                left=int(data["left"][i]),
                top=int(data["top"][i]),
                width=int(data["width"][i]),
                height=int(data["height"][i]),
                conf=conf,
                block=int(data["block_num"][i]),
                par=int(data["par_num"][i]),
                line=int(data["line_num"][i]),
            )
        )
        if conf >= 0:
            confidences.append(conf)

    paragraphs = reading_order(words)
    text = "\n\n".join("\n".join(lines) for lines in paragraphs)
    mean = round(sum(confidences) / len(confidences), 1) if confidences else None
    return OCRResult(text=text, mean_confidence=mean, engine=engine)


def get_ocr_engine() -> OCREngine:
    settings = get_settings()
    return TesseractEngine(lang=settings.ocr_lang, timeout=settings.ocr_timeout_seconds)
