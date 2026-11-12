"""Fact-check lookup: find published fact-checks for a claim (ADR-005).

This is the only place evidence comes from. We report what a named fact-checker published and the
rating text they used. We do not interpret the rating or turn it into a score.
"""

from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse

import httpx

SEARCH_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
MAX_FIELD_CHARS = 300


@dataclass(frozen=True)
class FactCheck:
    claim: str  # the claim as the fact-checker recorded it
    publisher: str
    url: str  # always http(s)
    title: str
    rating: str  # the publisher's own words, e.g. "False" or "Mostly true"
    review_date: str


class FactCheckError(Exception):
    """The lookup failed. The message is safe to show: no keys, no claim text."""


class FactCheckLookup(Protocol):
    def search(self, claim: str, limit: int = 3) -> list[FactCheck]: ...


class FakeFactCheckLookup:
    """Returns fixed results per claim. For tests."""

    def __init__(self, results: dict[str, list[FactCheck]] | None = None) -> None:
        self.results = results or {}

    def search(self, claim: str, limit: int = 3) -> list[FactCheck]:
        return self.results.get(claim, [])[:limit]


def _text(value: object) -> str:
    return " ".join(value.split())[:MAX_FIELD_CHARS] if isinstance(value, str) else ""


def _safe_url(value: object) -> str:
    """Only http(s) links survive. A javascript: or data: URL from the network must never reach a page."""
    url = _text(value)
    return url if urlparse(url).scheme in ("http", "https") and urlparse(url).netloc else ""


def parse_fact_checks(payload: object, limit: int) -> list[FactCheck]:
    """Flatten Google's response into FactCheck items, skipping anything malformed."""
    found: list[FactCheck] = []
    claims = payload.get("claims") if isinstance(payload, dict) else None
    for claim in claims if isinstance(claims, list) else []:
        if not isinstance(claim, dict):
            continue
        reviews = claim.get("claimReview")
        for review in reviews if isinstance(reviews, list) else []:
            if not isinstance(review, dict):
                continue
            publisher = review.get("publisher")
            url = _safe_url(review.get("url"))
            rating = _text(review.get("textualRating"))
            if not (url and rating):  # a result we cannot link to or read is not usable evidence
                continue
            found.append(
                FactCheck(
                    claim=_text(claim.get("text")),
                    publisher=_text(publisher.get("name")) if isinstance(publisher, dict) else "",
                    url=url,
                    title=_text(review.get("title")),
                    rating=rating,
                    review_date=_text(review.get("reviewDate")),
                )
            )
            if len(found) >= limit:
                return found
    return found


class GoogleFactCheckLookup:
    """Calls the Google Fact Check Tools API.

    The key goes in a header, not the URL: httpx logs request URLs, and a key in a URL would leak
    into logs. Errors are fixed generic messages for the same reason.
    """

    def __init__(self, api_key: str, client: httpx.Client | None = None, timeout: float = 15.0) -> None:
        self._api_key = api_key
        self._client = client or httpx.Client(timeout=timeout)

    def search(self, claim: str, limit: int = 3) -> list[FactCheck]:
        try:
            response = self._client.get(
                SEARCH_URL,
                params={"query": claim[:MAX_FIELD_CHARS], "languageCode": "en", "pageSize": limit},
                headers={"X-Goog-Api-Key": self._api_key},
            )
        except httpx.HTTPError as exc:
            raise FactCheckError("The fact-check service could not be reached.") from exc
        if response.status_code == 429:
            raise FactCheckError("The fact-check service is rate limited. Try again later.")
        if response.status_code != 200:
            raise FactCheckError(f"The fact-check service returned status {response.status_code}.")
        try:
            payload = response.json()
        except ValueError as exc:
            raise FactCheckError("The fact-check service gave an unreadable reply.") from exc
        return parse_fact_checks(payload, limit)
