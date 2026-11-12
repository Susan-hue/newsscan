"""Build a credibility report from signals.

The report never gives a bare "fake" or "real" verdict. It gives a band, the signals behind it,
and the limits of the analysis. Only signals of kind "evidence" with status "ok" may move the
band away from "insufficient_evidence". In milestone 1 none exist, so every scan lands there.
This is intentional: the system says what it has not checked instead of guessing.
"""

from dataclasses import dataclass

from newsscan.analysis.signals import LOW_OCR_CONFIDENCE, MIN_USEFUL_CHARS, Signal

BAND_INSUFFICIENT = "insufficient_evidence"
# Fact-check matches exist, but we cannot tell a true match from a keyword overlap, so the band is a
# neutral "go and read them" state, never reliable or weak (owner's choice, ADR-005).
BAND_RELATED = "related_fact_checks"
# Reserved for later milestones: "reliable_signals", "mixed", "weak_signals".


@dataclass(frozen=True)
class ReportData:
    band: str
    summary: str
    signals: list[dict]
    limitations: list[str]


def build_report(signals: list[Signal], char_count: int, mean_confidence: float | None) -> ReportData:
    band = BAND_INSUFFICIENT
    evidence_ok = [s for s in signals if s.kind == "evidence" and s.status == "ok"]

    limitations = [
        "Style signals are weak cues shown for transparency. They say nothing about whether "
        "the claims are true.",
        "OCR can misread words, numbers and names, and can mix up the order of columns.",
    ]
    if any(s.name == "claim_checks" and s.status == "ok" for s in evidence_ok):
        limitations.append(
            "Claims were picked out by an AI model and can miss or misread statements. Fact-check "
            "matches come from a keyword search and can be about a different claim."
        )
    if mean_confidence is not None and mean_confidence < LOW_OCR_CONFIDENCE:
        limitations.insert(0, "Text recognition confidence is low, so everything below is unreliable.")

    if char_count < MIN_USEFUL_CHARS:
        summary = (
            "Very little text was recognised, so there is nothing meaningful to assess. "
            "Try a sharper, well lit scan of the full page."
        )
    elif any(s.value for s in evidence_ok):
        band = BAND_RELATED
        summary = (
            "Published fact-checks that may relate to claims on this page were found. They are listed "
            "below. Check whether each one is about the same claim. This is not a verdict on the page."
        )
    elif evidence_ok:
        summary = (
            "Claims on this page were checked against published fact-checks and none matched. "
            "This is not a verdict: most claims have never been fact-checked."
        )
    else:
        summary = (
            "The paper was read and registered. No evidence-based checks have run, "
            "so this scan has no credibility verdict."
        )

    return ReportData(
        band=band,
        summary=summary,
        signals=[s.to_dict() for s in signals],
        limitations=limitations,
    )
