"""Image clean-up that helps OCR on photographed or scanned paper."""

from PIL import Image, ImageOps

# Tesseract works best when text is roughly 30 pixels tall, which is about 300 dpi for body text.
_MIN_SIDE_PX = 1500
_MAX_SIDE_PX = 4500


def prepare_for_ocr(image: Image.Image) -> Image.Image:
    grey = ImageOps.grayscale(image)
    grey = ImageOps.autocontrast(grey, cutoff=1)  # stretch the contrast of faded or dim photos

    longest = max(grey.size)
    if longest < _MIN_SIDE_PX:
        factor = _MIN_SIDE_PX / longest
    elif longest > _MAX_SIDE_PX:
        factor = _MAX_SIDE_PX / longest
    else:
        return grey
    new_size = (max(1, round(grey.width * factor)), max(1, round(grey.height * factor)))
    return grey.resize(new_size, Image.Resampling.LANCZOS)
