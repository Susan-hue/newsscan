"""Clean up raw OCR text so later stages see ordinary paragraphs."""

import hashlib
import re
import unicodedata

_HYPHEN_BREAK = re.compile(r"(?<=[a-z])-\n(?=[a-z])")
_SINGLE_NEWLINE = re.compile(r"(?<!\n)\n(?!\n)")
_SPACES = re.compile(r"[ \t]+")
_BLANK_RUNS = re.compile(r"\n{3,}")


def normalise_text(raw: str) -> str:
    # NFKC turns ligatures such as "ﬁ" into "fi" and removes odd width variants.
    text = unicodedata.normalize("NFKC", raw).replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(line.strip() for line in text.split("\n"))
    # Newspaper columns break words across lines with a hyphen. Re-join "gov-\nernment".
    text = _HYPHEN_BREAK.sub("", text)
    # Hard-wrapped lines inside a paragraph become one line; blank lines still separate paragraphs.
    text = _SINGLE_NEWLINE.sub(" ", text)
    text = _SPACES.sub(" ", text)
    text = _BLANK_RUNS.sub("\n\n", text)
    return text.strip()


def text_fingerprint(text: str) -> str:
    """Stable hash of the text, ignoring case and spacing, to spot the same paper scanned twice."""
    canonical = " ".join(text.lower().split())
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
