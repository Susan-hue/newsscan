from newsscan.aggregate.report import BAND_INSUFFICIENT, build_report
from newsscan.analysis.signals import (
    caps_word_ratio,
    compute_signals,
    exclamation_density,
    ocr_quality,
    sensational_phrases,
)

LONG_TEXT = "The council met on Tuesday and discussed the budget at length. " * 6


def test_caps_word_ratio_counts_all_caps_words():
    signal = caps_word_ratio("BREAKING news about the CITY council today")
    assert signal.status == "ok"
    assert signal.value == round(2 / 7, 3)


def test_caps_word_ratio_with_no_words_is_not_run():
    assert caps_word_ratio("1234 !!").status == "not_run"


def test_exclamation_density_per_thousand_characters():
    signal = exclamation_density("!" * 5 + "a" * 995)
    assert signal.value == 5.0


def test_sensational_phrases_are_counted_case_insensitively():
    assert sensational_phrases("SHOCKING! You won't believe this miracle cure").value == 3.0


def test_ocr_quality_flags_low_confidence():
    assert "Low confidence" in ocr_quality(40).detail
    assert ocr_quality(None).status == "not_run"


def test_compute_signals_declares_unrun_evidence_checks():
    signals = compute_signals(LONG_TEXT, 90)
    evidence = [s for s in signals if s.kind == "evidence"]
    assert {s.name for s in evidence} == {"claim_checks", "source_signals"}
    assert all(s.status == "not_run" for s in evidence)


def test_report_never_gives_a_verdict_without_evidence():
    # Even text packed with clickbait must not be called fake: style cues are not evidence.
    text = "SHOCKING!!! You won't believe this miracle cure! " * 10
    report = build_report(compute_signals(text, 95), len(text), 95)
    assert report.band == BAND_INSUFFICIENT
    assert "no credibility verdict" in report.summary


def test_report_warns_when_ocr_confidence_is_low():
    report = build_report(compute_signals(LONG_TEXT, 30), len(LONG_TEXT), 30)
    assert "confidence is low" in report.limitations[0]


def test_report_says_so_when_almost_no_text_was_read():
    report = build_report(compute_signals("Hi", 90), 2, 90)
    assert "Very little text" in report.summary


def test_report_band_rules_for_claim_checks():
    from newsscan.aggregate.report import BAND_RELATED
    from newsscan.analysis.factcheck import FactCheck
    from newsscan.analysis.signals import claim_checks_from_lookups

    match = FactCheck("c", "Pub", "https://a.example/x", "T", "False", "d")
    with_match = claim_checks_from_lookups(["claim"], {"claim": [match]})
    without = claim_checks_from_lookups(["claim"], {"claim": []})

    related = build_report(compute_signals(LONG_TEXT, 90, with_match), len(LONG_TEXT), 90)
    assert related.band == BAND_RELATED
    assert any("AI model" in item for item in related.limitations)

    nothing = build_report(compute_signals(LONG_TEXT, 90, without), len(LONG_TEXT), 90)
    assert nothing.band == BAND_INSUFFICIENT

    # A failed or empty lookup never moves the band, and there is never a bare verdict.
    for signal in (claim_checks_from_lookups([], {}), claim_checks_from_lookups(["c"], {}, failures=1)):
        assert signal.status == "not_run"
        assert (
            build_report(compute_signals(LONG_TEXT, 90, signal), len(LONG_TEXT), 90).band == BAND_INSUFFICIENT
        )
