"""Validate uploads and turn them into page images.

We never trust the Content-Type header or the file name. The file kind is decided from the first
bytes, and the file is then opened for real to check its size and page count.
"""

import io
from collections.abc import Iterator

import pypdfium2 as pdfium
from PIL import Image, ImageOps

from newsscan.config import Settings

# A4 at 300 dpi is about 2480 x 3508 pixels, which OCR handles well. Never render beyond this.
_PDF_TARGET_DPI = 300
_PDF_MAX_SIDE_PX = 5000


class UploadRejected(ValueError):
    """The upload cannot be processed. The message is safe to show to the user."""


class UnsupportedFileType(UploadRejected):
    """The file is not one of the accepted image or PDF types."""


def sniff_kind(data: bytes) -> str:
    """Return "pdf" or "image" from the file's leading bytes, or raise UploadRejected."""
    if data.startswith(b"%PDF-"):
        return "pdf"
    is_png = data.startswith(b"\x89PNG\r\n\x1a\n")
    is_jpeg = data.startswith(b"\xff\xd8\xff")
    is_tiff = data[:4] in (b"II*\x00", b"MM\x00*")
    is_webp = data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    if is_png or is_jpeg or is_tiff or is_webp:
        return "image"
    raise UnsupportedFileType("Unsupported file type. Upload a PNG, JPEG, TIFF or WebP image, or a PDF.")


def _check_pixels(width: int, height: int, settings: Settings) -> None:
    if width * height > settings.max_image_pixels:
        raise UploadRejected("The image is too large. Reduce its resolution and try again.")


def validate_upload(data: bytes, settings: Settings) -> str:
    """Cheap checks done in the API before anything is stored or queued. Returns the kind."""
    kind = sniff_kind(data)
    try:
        if kind == "pdf":
            pdf = pdfium.PdfDocument(data)
            try:
                if len(pdf) == 0:
                    raise UploadRejected("The PDF has no pages.")
                if len(pdf) > settings.max_pages:
                    raise UploadRejected(f"The PDF has too many pages. The limit is {settings.max_pages}.")
            finally:
                pdf.close()
        else:
            with Image.open(io.BytesIO(data)) as img:
                _check_pixels(img.width, img.height, settings)
                if getattr(img, "n_frames", 1) > settings.max_pages:
                    raise UploadRejected(f"The image has too many pages. The limit is {settings.max_pages}.")
    except UploadRejected:
        raise
    except Exception as exc:  # corrupt or hostile file
        raise UploadRejected("The file could not be read. It may be damaged.") from exc
    return kind


def load_pages(data: bytes, kind: str, settings: Settings) -> Iterator[Image.Image]:
    """Yield each page as an upright RGB or greyscale image. Pages are produced one at a time."""
    if kind == "pdf":
        pdf = pdfium.PdfDocument(data)
        try:
            for index in range(min(len(pdf), settings.max_pages)):
                page = pdf[index]
                width, height = page.get_size()
                scale = min(_PDF_TARGET_DPI / 72, _PDF_MAX_SIDE_PX / max(width, height))
                yield page.render(scale=scale).to_pil().convert("RGB")
        finally:
            pdf.close()
        return

    with Image.open(io.BytesIO(data)) as img:
        frames = getattr(img, "n_frames", 1)
        for index in range(min(frames, settings.max_pages)):
            img.seek(index)
            _check_pixels(img.width, img.height, settings)
            # Phones store rotation in EXIF metadata. Apply it so the text is upright for OCR.
            yield ImageOps.exif_transpose(img).convert("RGB")
