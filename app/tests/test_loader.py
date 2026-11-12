import io

import pytest
from PIL import Image

from newsscan.config import Settings
from newsscan.ingest.loader import (
    UnsupportedFileType,
    UploadRejected,
    load_pages,
    sniff_kind,
    validate_upload,
)
from tests.conftest import make_image, make_pdf


def settings(**overrides) -> Settings:
    return Settings(**overrides)


def test_sniff_accepts_png_jpeg_and_pdf():
    assert sniff_kind(make_image(fmt="PNG")) == "image"
    assert sniff_kind(make_image(fmt="JPEG")) == "image"
    assert sniff_kind(make_pdf()) == "pdf"


def test_sniff_rejects_other_files_even_with_a_friendly_name():
    with pytest.raises(UnsupportedFileType):
        sniff_kind(b"<html><script>alert(1)</script></html>")
    with pytest.raises(UnsupportedFileType):
        sniff_kind(b"MZ\x90\x00 executable bytes")


def test_validate_rejects_a_damaged_image():
    with pytest.raises(UploadRejected, match="could not be read"):
        validate_upload(b"\x89PNG\r\n\x1a\n" + b"garbage" * 20, settings())


def test_validate_rejects_images_with_too_many_pixels():
    with pytest.raises(UploadRejected, match="too large"):
        validate_upload(make_image(size=(400, 400)), settings(max_image_pixels=1000))


def test_validate_rejects_pdfs_with_too_many_pages():
    with pytest.raises(UploadRejected, match="too many pages"):
        validate_upload(make_pdf(pages=3), settings(max_pages=2))


def test_validate_accepts_a_normal_pdf_and_image():
    assert validate_upload(make_pdf(pages=2), settings()) == "pdf"
    assert validate_upload(make_image(), settings()) == "image"


def test_load_pages_renders_each_pdf_page():
    pages = list(load_pages(make_pdf(pages=2), "pdf", settings()))
    assert len(pages) == 2
    assert all(page.width > 0 and page.height > 0 for page in pages)


def test_load_pages_applies_exif_rotation_from_phone_photos():
    image = Image.new("RGB", (300, 100), "white")
    exif = Image.Exif()
    exif[0x0112] = 6  # "rotate 90 degrees clockwise to display"
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif)

    (page,) = list(load_pages(buffer.getvalue(), "image", settings()))
    assert page.size == (100, 300)
