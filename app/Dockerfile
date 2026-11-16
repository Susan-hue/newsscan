
FROM python:3.12-slim AS build
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /src
COPY pyproject.toml ./
COPY src ./src
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install . \
    && /opt/venv/bin/pip uninstall -y pip   # the running app has no use for a package installer

FROM python:3.12-slim AS runtime
# Install Debian's latest security fixes, and remove the base image's own pip and setuptools: the app doesn't
# need them, and old copies of them were the only Python findings in the vulnerability scan.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng \
    && /usr/local/bin/python -m pip uninstall -y pip setuptools wheel \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app \
    && mkdir -p /app /data/uploads \
    && chown -R app:app /app /data

COPY --from=build /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    NEWSSCAN_STORAGE_DIR=/data/uploads

WORKDIR /app
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app migrations ./migrations

USER app
EXPOSE 8000

CMD ["uvicorn", "newsscan.main:app", "--host", "0.0.0.0", "--port", "8000"]
