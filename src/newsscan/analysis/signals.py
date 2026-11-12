"""Signals computed from a registered document.

Every signal has a kind:
  quality    says how far the other signals can be trusted (for example, OCR confidence)
  heuristic  a crude style cue. Shown for transparency. It is NOT evidence of truth or falsehood.
  evidence   based on external evidence, such as fact-check lookups. Only these can move the band.

Milestone 1 ships quality signals and a few heuristics. Evidence signals are declared as
"not_run" so the report states plainly what has not been checked.
"""

import re
from dataclasses import asdict, dataclass, field

from newsscan.analysis.factcheck import FactCheck

_WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")

# A tiny, deliberately obvious list. Replace with a measured approach in a later milestone.
_SENSATIONAL = (
    "you won't believe",
    "shocking",
    "miracle cure",
    "doctors hate",
    "they don't want you to know",
    "what happens next",
    "share before it's deleted",
)

LOW_OCR_CONFIDENCE = 60.0
MIN_USEFUL_CHARS = 200


@dataclass(frozen=True)
class Signal:
    name: str
    kind: str  # "quality" | "heuristic" | "evidence"
    status: str  # "ok" | "not_run"
    value: float | None
    detail: str
    items: list[dict] = field(default_factory=list)  # structured details, e.g. fact-check matches

    def to_dict(self) -> dict:
        return asdict(self)


def ocr_quality(mean_confidence: float | None) -> Signal:
    if mean_confidence is None:
        return Signal("ocr_quality", "quality", "not_run", None, "The OCR engine gave no confidence.")
    if mean_confidence < LOW_OCR_CONFIDENCE:
        detail = "Low confidence. The recognised text probably contains many errors."
    else:
        detail = "Reasonable confidence. Spot-check names and numbers before relying on them."
    return Signal("ocr_quality", "quality", "ok", mean_confidence, detail)


def caps_word_ratio(text: str) -> Signal:
    words = [w for w in _WORD.findall(text) if len(w) >= 3]
    if not words:
        return Signal("caps_word_ratio", "heuristic", "not_run", None, "No words to measure.")
    ratio = sum(1 for w in words if w.isupper()) / len(words)
    return Signal(
        "caps_word_ratio",
        "heuristic",
        "ok",
        round(ratio, 3),
        "Share of words in ALL CAPS. Printed headlines are often capitalised, so this is weak.",
    )


def exclamation_density(text: str) -> Signal:
    if not text:
        return Signal("exclamation_density", "heuristic", "not_run", None, "No text to measure.")
    per_thousand = text.count("!") / len(text) * 1000
    return Signal(
        "exclamation_density",
        "heuristic",
        "ok",
        round(per_thousand, 2),
        "Exclamation marks per 1000 characters. A style cue only.",
    )


def sensational_phrases(text: str) -> Signal:
    lowered = text.lower().replace("’", "'")
    hits = sum(lowered.count(phrase) for phrase in _SENSATIONAL)
    return Signal(
        "sensational_phrases",
        "heuristic",
        "ok",
        float(hits),
        "Count of stock clickbait phrases. Many honest articles use none and many false ones too.",
    )


def plausibility_cue_not_run(detail: str) -> Signal:
    return Signal("plausibility_cue", "heuristic", "not_run", None, detail)


def plausibility_cue(level: str, reasons: list[str]) -> Signal:
    """The AI's satire/implausibility cue. A heuristic: shown for transparency, never moves the band."""
    if level == "possible" and reasons:
        return Signal(
            "plausibility_cue",
            "heuristic",
            "ok",
            1.0,
            "An AI model noticed signs this page may be satire or implausible. It can be wrong, and "
            "this says nothing about whether any claim is true or false.",
            [{"reason": reason} for reason in reasons],
        )
    return Signal(
        "plausibility_cue",
        "heuristic",
        "ok",
        0.0,
        "An AI model saw no obvious satire markers. That does not mean the page is true.",
    )


def claim_checks() -> Signal:
    """The default: claim checking is off (no keys configured), so say so plainly."""
    return claim_checks_not_run(
        "Claim checking is switched off. It needs the Groq and Fact Check keys (ADR-005)."
    )


def claim_checks_not_run(detail: str) -> Signal:
    return Signal("claim_checks", "evidence", "not_run", None, detail)


def claim_checks_from_lookups(
    claims: list[str], found: dict[str, list[FactCheck]], failures: int = 0
) -> Signal:
    """Turn lookup results into the claim_checks signal.

    Matches are fuzzy (the search is by keywords), so we list each one next to the page claim that
    found it and the claim the fact-checker recorded. The reader judges whether they are the same.
    We never turn a rating into true/false: ratings are the publisher's own free text.
    """
    if not claims:
        return claim_checks_not_run("No checkable claims were found on this page.")
    if failures >= len(claims):
        return claim_checks_not_run("The fact-check lookup failed for every claim, so nothing was checked.")
    items = [
        {
            "claim": claim,
            "matched_claim": match.claim,
            "publisher": match.publisher,
            "rating": match.rating,
            "title": match.title,
            "url": match.url,
        }
        for claim in claims
        for match in found.get(claim, [])
    ]
    if items:
        detail = (
            f"Found {len(items)} published fact-check(s) that may relate to claims on this page. "
            "Matches are keyword-based: read each one and decide whether it is about the same claim."
        )
    else:
        detail = (
            f"Checked {len(claims)} claim(s) against published fact-checks and found none. "
            "That does not mean the claims are true: most claims have never been fact-checked."
        )
    if failures:
        detail += f" {failures} of {len(claims)} lookups failed."
    return Signal("claim_checks", "evidence", "ok", float(len(items)), detail, items)


def source_signals() -> Signal:
    return Signal(
        "source_signals",
        "evidence",
        "not_run",
        None,
        "A scanned paper has no web domain. Publication detection is planned for a later milestone.",
    )


def compute_signals(
    text: str,
    mean_confidence: float | None,
    claim_check: Signal | None = None,
    plausibility: Signal | None = None,
) -> list[Signal]:
    return [
        ocr_quality(mean_confidence),
        caps_word_ratio(text),
        exclamation_density(text),
        sensational_phrases(text),
        plausibility
        or plausibility_cue_not_run(
            "The AI plausibility cue is switched off. It needs the Groq key (ADR-006)."
        ),
        source_signals(),
        claim_check or claim_checks(),
    ]
