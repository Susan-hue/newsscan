"""Score the OCR against texts you typed yourself.

Put each picture and its correct text side by side in one folder, with the same name:

    test_assests/Prohibition Party.jpeg
    test_assests/Prohibition Party.txt      <- what the page really says, in reading order

Run from the app/ folder:

    python scripts/ocr_eval.py test_assests

Pictures with no .txt file are skipped. For each one it prints:
  char errors   share of characters that are wrong (0% is perfect). Lower is better.
  word errors   share of words that are wrong. Lower is better.
  order         how many of the reference words also appear in the OCR text, even if out of place,
                next to how many appear in the right place. A big gap means the columns got mixed up.

Whitespace is ignored (line breaks do not count as errors). Upper and lower case do count.
"""

import sys
from pathlib import Path

from newsscan.config import get_settings
from newsscan.ingest import loader, ocr
from newsscan.ingest.preprocess import prepare_for_ocr

PICTURES = {".png", ".jpg", ".jpeg", ".pdf"}


def edit_distance(a: list, b: list) -> int:
    """Fewest single-item changes (insert, delete, swap) to turn a into b."""
    previous = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        current = [i]
        for j, y in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (x != y)))
        previous = current
    return previous[-1]


def error_rate(reference: list, found: list) -> float:
    if not reference:
        return 0.0 if not found else 1.0
    return edit_distance(reference, found) / len(reference)


def word_overlap(reference: list[str], found: list[str]) -> float:
    """Share of reference words that appear anywhere in the OCR text (order ignored)."""
    if not reference:
        return 1.0
    remaining: dict[str, int] = {}
    for word in found:
        remaining[word] = remaining.get(word, 0) + 1
    hits = 0
    for word in reference:
        if remaining.get(word, 0) > 0:
            remaining[word] -= 1
            hits += 1
    return hits / len(reference)


def in_order_share(reference: list[str], found: list[str]) -> float:
    """Share of reference words that are also in the OCR text in the same order (longest common run
    of words, not necessarily next to each other)."""
    if not reference:
        return 1.0
    previous = [0] * (len(found) + 1)
    for x in reference:
        current = [0]
        for j, y in enumerate(found, 1):
            current.append(previous[j - 1] + 1 if x == y else max(previous[j], current[j - 1]))
        previous = current
    return previous[-1] / len(reference)


def score(reference_text: str, ocr_text: str) -> dict[str, float]:
    ref_words, found_words = reference_text.split(), ocr_text.split()
    return {
        "char_errors": error_rate(list("".join(ref_words)), list("".join(found_words))),
        "word_errors": error_rate(ref_words, found_words),
        "words_present": word_overlap(ref_words, found_words),
        "words_in_order": in_order_share(ref_words, found_words),
    }


def read_page_text(path: Path) -> str:
    settings = get_settings()
    data = path.read_bytes()
    pages = loader.load_pages(data, loader.validate_upload(data, settings), settings)
    engine = ocr.get_ocr_engine()
    return "\n\n".join(engine.recognize(prepare_for_ocr(page)).text for page in pages)


def main(folder: Path) -> None:
    rows = []
    for picture in sorted(p for p in folder.iterdir() if p.suffix.lower() in PICTURES):
        reference = picture.with_suffix(".txt")
        if not reference.exists():
            print(f"skipped (no {reference.name}): {picture.name}")
            continue
        result = score(reference.read_text(), read_page_text(picture))
        rows.append((picture.name, result))
    if not rows:
        print("Nothing to score. Add a .txt file next to a picture.")
        return
    print(f"\n{'picture':36} {'char err':>9} {'word err':>9} {'present':>8} {'in order':>9}")
    for name, r in rows:
        print(
            f"{name[:36]:36} {r['char_errors']:>8.1%} {r['word_errors']:>9.1%} "
            f"{r['words_present']:>8.1%} {r['words_in_order']:>9.1%}"
        )
    mean = {k: sum(r[k] for _, r in rows) / len(rows) for k in rows[0][1]}
    print(
        f"{'average of ' + str(len(rows)):36} {mean['char_errors']:>8.1%} {mean['word_errors']:>9.1%} "
        f"{mean['words_present']:>8.1%} {mean['words_in_order']:>9.1%}"
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python scripts/ocr_eval.py <folder with pictures and .txt files>")
    main(Path(sys.argv[1]))
