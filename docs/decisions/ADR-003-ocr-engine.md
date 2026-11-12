# ADR-003: Which OCR engine, and how to read columns

- **Status:** **Proposed.** The code uses Tesseract by default. That was Claude's default. **The owner hasn't decided yet.**
- **Date:** 2026-11-11

## The problem

Which tool should read the text from scanned newspaper pages?

## Options

| Option | Good | Bad |
|---|---|---|
| **Tesseract (local) plus my own column-reading step** (current default) | Free, works offline, small, easy to run in Docker, nothing leaves the machine | Newspaper layouts are its weak spot; results depend a lot on scan quality; the column step is my own rule of thumb |
| A layout-aware ML OCR (for example PaddleOCR or docTR) | Better on complex layouts | Big install, much more RAM, slow on CPU; competes with the monitoring stack for memory |
| Cloud OCR (for example AWS Textract) | Strong on documents and tables, no local computing | Costs money per page, needs credentials and internet, pages leave the machine. Good for production, not for a local-first project |

The OCR sits behind a small interface (`OCREngine` in `ingest/ocr.py`), so changing engine means changing one file.

## What was measured

Every test used a **made-up** two-column newspaper page from a script. **No real scans yet.**

- Plain Tesseract, in any page mode (1, 3 or 4), mixed the two columns line by line and lost some words.
- With my column-reading step (`ingest/layout.py`: find the empty strip between columns, read one column at a time,
  headline first):

| Version of the made-up page | Mean confidence | Left column read before right |
|---|---|---|
| clean | 95.7 | yes |
| tilted 1.5 degrees | 95.7 | yes |
| tilted 3 degrees | 94.6 | **no** (falls back to the mixed-up order) |
| added noise and blur | 95.9 | yes |
| half the resolution | 95.9 | yes |

What this means: my rule works when a clean empty strip separates the columns. A real photo of a newspaper has
tilt, curl, shadows, ads, pictures, captions and uneven columns. **I have no evidence about real pages yet.**
Failing at 3 degrees shows how fragile the rule is.

When it finds no clear strip it falls back to Tesseract's own order, so it shouldn't make plain cases worse.
That is only checked on made-up pages.

## Recommendation (the owner accepts or changes it)

1. Keep Tesseract for now.
2. Build the **OCR evaluation** (milestone M2): 10 to 20 of the owner's real scans, each with a hand-typed copy of
   the text. Score the number of wrong characters and whether paragraphs come out in the right order.
3. Add **straightening** (deskewing) if tilt turns out to be the usual problem.
4. Choose between staying, a layout model or a cloud engine **using those numbers**, then update this ADR.

## Decision

_Waiting for the owner._

## What this means

Until this is decided, multi-column pages may come out scrambled, and the checks built on that text mean less. The
OCR confidence score does **not** catch this: a scrambled page can still have high word confidence.
