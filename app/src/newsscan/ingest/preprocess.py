"""Image clean-up that helps OCR on photographed or scanned paper."""

from PIL import Image, ImageOps

# Tesseract needs big letters. Small pictures are enlarged to this size: slower, but it found far more words
# on 740 px pages (ADR-003).
_MIN_SIDE_PX = 3000
_MAX_SIDE_PX = 4500

# Straightening (ADR-003). Pages tilted less than this are left alone, so straight pages are never touched.
_MIN_TILT_DEGREES = 0.5
_MAX_TILT_DEGREES = 8.0
_TILT_SAMPLE_PX = 900  # the tilt is measured on a small copy, which is fast and good enough


def _row_sharpness(ink: Image.Image, angle: float) -> int:
    """How sharply the dark rows stand out once the page is turned by `angle`.

    On a straight page, text lines are separated by clean white gaps, so the row totals jump up and down.
    On a tilted page, the lines smear into each other and the totals are flat.
    """
    turned = ink.rotate(angle, resample=Image.Resampling.BILINEAR, fillcolor=0)
    rows = turned.resize((1, turned.height), Image.Resampling.BOX).tobytes()
    return sum((rows[i + 1] - rows[i]) ** 2 for i in range(len(rows) - 1))


def estimate_tilt(grey: Image.Image) -> float:
    """Degrees to turn the page (counter-clockwise is positive) to make its text lines horizontal."""
    sample = grey.copy()
    sample.thumbnail((_TILT_SAMPLE_PX, _TILT_SAMPLE_PX))
    low, high = sample.getextrema()
    if high - low < 40:  # a blank or flat picture has no lines to measure
        return 0.0
    cut = (low + high) // 2
    ink = sample.point(lambda v: 255 if v < cut else 0)

    def best(candidates: list[float]) -> float:
        return max(candidates, key=lambda a: _row_sharpness(ink, a))

    steps = int(_MAX_TILT_DEGREES / 0.5)
    rough = best([k * 0.5 for k in range(-steps, steps + 1)])
    return best([rough + k * 0.1 for k in range(-5, 6)])


def straighten(grey: Image.Image) -> Image.Image:
    """Turn a clearly tilted page upright. Pages that are nearly straight come back unchanged."""
    angle = estimate_tilt(grey)
    if abs(angle) < _MIN_TILT_DEGREES:
        return grey
    return grey.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=255)


def prepare_for_ocr(image: Image.Image) -> Image.Image:
    grey = ImageOps.grayscale(image)
    grey = ImageOps.autocontrast(grey, cutoff=1)  # stretch the contrast of faded or dim photos
    grey = straighten(grey)

    longest = max(grey.size)
    if longest < _MIN_SIDE_PX:
        factor = _MIN_SIDE_PX / longest
    elif longest > _MAX_SIDE_PX:
        factor = _MAX_SIDE_PX / longest
    else:
        return grey
    new_size = (max(1, round(grey.width * factor)), max(1, round(grey.height * factor)))
    return grey.resize(new_size, Image.Resampling.LANCZOS)
