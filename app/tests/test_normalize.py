from newsscan.extract.normalize import normalise_text, text_fingerprint


def test_rejoins_words_split_across_lines_by_a_hyphen():
    assert normalise_text("The gov-\nernment said") == "The government said"


def test_does_not_glue_a_hyphen_break_before_a_capital_letter():
    # "Anglo-\nSaxon" is ambiguous, so words are only joined when the next letter is lowercase.
    assert normalise_text("Anglo-\nSaxon") == "Anglo- Saxon"


def test_leaves_ordinary_hyphenated_words_alone():
    assert normalise_text("a well-known fact") == "a well-known fact"


def test_joins_hard_wrapped_lines_but_keeps_paragraphs():
    raw = "First line of a\nparagraph that wraps.\n\nSecond paragraph."
    assert normalise_text(raw) == "First line of a paragraph that wraps.\n\nSecond paragraph."


def test_turns_ligatures_into_plain_letters():
    assert normalise_text("ﬁnance and ﬂood") == "finance and flood"


def test_collapses_extra_spaces_and_blank_lines():
    assert normalise_text("a   b\n\n\n\n c ") == "a b\n\nc"


def test_empty_input_gives_empty_text():
    assert normalise_text("") == ""


def test_fingerprint_ignores_case_and_spacing():
    assert text_fingerprint("Budget  passed\nToday") == text_fingerprint("budget passed today")
    assert text_fingerprint("budget passed") != text_fingerprint("budget failed")
