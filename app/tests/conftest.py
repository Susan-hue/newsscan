import io

import pytest
from PIL import Image, ImageDraw, ImageFont

from newsscan.config import get_settings
from newsscan.db import Base, get_engine, reset_engine
from newsscan.ingest import ocr
from newsscan.ingest.ocr import OCRResult
from newsscan.worker.celery_app import celery_app

SAMPLE_TEXT = (
    "The city council approved the new transit budget on Tuesday.\n\n"
    "Officials said the plan adds three bus routes and extends evening service across the "
    "northern districts, with construction expected to begin next spring."
)


class FakeEngine:
    """Stands in for Tesseract so most tests do not depend on OCR quality."""

    name = "fake"

    def __init__(self, text: str = SAMPLE_TEXT, confidence: float | None = 92.0) -> None:
        self.text = text
        self.confidence = confidence

    def recognize(self, image: Image.Image) -> OCRResult:
        return OCRResult(text=self.text, mean_confidence=self.confidence, engine=self.name)


def make_image(text: str = "Hello", size: tuple[int, int] = (1600, 500), fmt: str = "PNG") -> bytes:
    image = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(image)
    draw.text((40, 40), text, fill="black", font=ImageFont.load_default(size=48))
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


def make_pdf(pages: int = 1) -> bytes:
    frames = [Image.new("RGB", (800, 1000), "white") for _ in range(pages)]
    buffer = io.BytesIO()
    frames[0].save(buffer, format="PDF", save_all=True, append_images=frames[1:])
    return buffer.getvalue()


@pytest.fixture()
def app_env(tmp_path, monkeypatch):
    """Point the app at a throwaway SQLite database and upload folder, and run tasks inline."""
    monkeypatch.setenv("NEWSSCAN_DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("NEWSSCAN_STORAGE_DIR", str(tmp_path / "uploads"))
    get_settings.cache_clear()
    reset_engine()
    Base.metadata.create_all(get_engine())
    celery_app.conf.task_always_eager = True
    yield get_settings()
    celery_app.conf.task_always_eager = False
    reset_engine()
    get_settings.cache_clear()


@pytest.fixture()
def fake_ocr(monkeypatch):
    engine = FakeEngine()
    monkeypatch.setattr(ocr, "get_ocr_engine", lambda: engine)
    return engine


@pytest.fixture()
def client(app_env, fake_ocr):
    from fastapi.testclient import TestClient

    from newsscan.main import create_app
    from newsscan.ratelimit import AllowAllLimiter

    app = create_app()
    app.state.rate_limiter = AllowAllLimiter()  # no Redis in tests; rate-limit tests set their own
    with TestClient(app) as test_client:
        yield test_client
