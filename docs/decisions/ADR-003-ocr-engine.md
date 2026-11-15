# ADR-003: Which OCR engine, and how to read columns

- **Status:** **Proposed** for the engine: Tesseract is Claude's default and the owner hasn't decided it.
  **Accepted** for one step: the owner chose to add page straightening first (2026-11-16).
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

## First numbers on pictures of real newspapers (2026-11-16)

Five pictures, from `app/scripts/ocr_eval.py`. The correct text was **written by Claude from the pictures**, not
typed by the owner and not checked by anyone yet, so it can contain mistakes. The pictures are stock images and
web screenshots, mostly under 740 px wide, **not real scans**. The score is on the text the app stores.

| Picture | Wrong characters | Words present | Words in the right order |
|---|---|---|---|
| Egypt screenshot (one paragraph) | 0.7% | 98% | 98% |
| Two news-site screenshots (a headline each) | 15% | 72 to 77% | 72 to 77% |
| Prohibition page (multi-column) | 64% | 88% | **59%** |
| Halloween page (multi-column) | 58% | **60%** | 44% |

What it shows: single blocks of text read well. On multi-column pages the words are mostly found but come out in
the wrong order, and on the Halloween page many words are missing. Not scored: three pictures with low OCR
confidence (Titanic, Erie, Batman) and two that name private people (left out on purpose).

## Page straightening (the owner chose this step)

Added in `ingest/preprocess.py`. It measures how tilted the page is (up to 8 degrees) and turns it upright, but
only when the tilt is 0.5 degrees or more, so straight pages are never touched. It adds about 0.5 to 1 second
per page.

**Finding before building it:** the Prohibition and Halloween pages measure about 0 degrees, so straightening
can't fix their wrong order. Their cause is something else (probably headlines across columns, photos inside
columns, uneven columns). That is still open.

**Tested by tilting those pages on purpose** (same pictures, same typed texts, words in the right order):

| Page | Tilt | Off | On |
|---|---|---|---|
| Prohibition | 3 degrees | 35% | 48% |
| Prohibition | 5 degrees | 19% | 47% |
| Halloween | 5 degrees | 21% | 32% |
| Egypt paragraph | 3 degrees | 92% | 97% |

It helps a lot on tilted pages, but doesn't fully recover the straight page's score (59% on Prohibition). Tilting
by software is cleaner than a real photo, which also has curl, shadow and perspective. **Not tested on a real
tilted photo.**

## Why straight multi-column pages scrambled, and two fixes (Claude's choices)

The owner asked to fix the bigger problem. Two causes were found by measuring, not guessing.

1. **The column rule made good pages worse.** It looks for empty strips that run the full height of the page. On
   a page with a photo, an advert or columns that change width, those strips cut the text in the wrong places.
   On the Prohibition page, plain Tesseract got 77% of words in order and the rule only 59%.
   **Fix:** the rule now acts only when Tesseract has actually run neighbouring columns together (at least 30%
   of long lines cross a gutter). Measured: 1% on Prohibition (rule stays out), 47% on the Erie page, 90% on the
   synthetic page the rule was built for. **That 30% line was picked from three real pages and one synthetic
   page. It is a guess that fits them.**
2. **Small pictures lost many words.** Body text in a 740 px picture is tiny. Small pictures are now enlarged to
   3000 px before reading (was 1500). Cost: slower, for example 8 s to 23 s for the Erie page (limit is 60 s).

| Picture | Words in order, before | after | Words found, before | after |
|---|---|---|---|---|
| Prohibition | 59% | 65% | 88% | 92% |
| Halloween | 44% | 68% | 60% | 85% |
| Two headline screenshots | 72 to 77% | 76 to 78% | same | same |
| Egypt paragraph | 98% | 98% | 98% | 98% |
| Average of 5 | 70% | 77% | 79% | 86% |

Mixed result on Prohibition: with the gate alone it reached 77% in order, but enlarging the picture changed how
Tesseract split the page and order fell to 65% while more words were found. Its wrong-character rate also rose
(43% to 79%), because misplaced text counts as wrong characters. **Tuned on two pages, so it may not carry over to
other pages.** The typed texts are still Claude's own reading and unchecked. Real tilted photos are still untested.

## Recommendation (the owner accepts or changes it)

1. Keep Tesseract for now.
2. Build the **OCR evaluation** (milestone M2): 10 to 20 of the owner's real scans, each with a hand-typed copy of
   the text. Score the number of wrong characters and whether paragraphs come out in the right order.
3. Add **straightening** (deskewing). Done, see above. Next: find out why straight multi-column pages still come out in the wrong order.
4. Choose between staying, a layout model or a cloud engine **using those numbers**, then update this ADR.

## Decision

_Waiting for the owner._

## What this means

Until this is decided, multi-column pages may come out scrambled, and the checks built on that text mean less. The
OCR confidence score does **not** catch this: a scrambled page can still have high word confidence.
