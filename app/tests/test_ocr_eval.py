import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "ocr_eval", Path(__file__).parents[1] / "scripts" / "ocr_eval.py"
)
ocr_eval = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ocr_eval)


def test_identical_text_scores_perfect():
    r = ocr_eval.score("the cat sat", "the  cat\nsat")
    assert r == {"char_errors": 0, "word_errors": 0, "words_present": 1, "words_in_order": 1}


def test_one_wrong_letter_is_one_char_error():
    r = ocr_eval.score("cat sat", "cot sat")
    assert r["char_errors"] == 1 / 6
    assert r["word_errors"] == 1 / 2


def test_swapped_columns_keep_the_words_but_lose_the_order():
    reference = "one two three four five six"
    mixed = "four five six one two three"
    r = ocr_eval.score(reference, mixed)
    assert r["words_present"] == 1
    assert r["words_in_order"] == 0.5
    assert r["word_errors"] > 0.5 - 1e-9


def test_empty_ocr_is_all_wrong():
    r = ocr_eval.score("a b", "")
    assert r["char_errors"] == 1 and r["words_present"] == 0
