import pytest

from src.stt.preprocessor import SwedishPreprocessor


@pytest.fixture
def preprocessor():
    return SwedishPreprocessor()


def test_removes_hesitations(preprocessor):
    assert preprocessor.clean("Emh, hur många konton finns det?") == "Hur många konton finns det?"
    assert preprocessor.clean("Öh kan du visa mina leads?") == "kan du visa mina leads?"


def test_removes_fillers(preprocessor):
    assert preprocessor.clean("Hur många, liksom, affärsmöjligheter har jag?") == \
        "Hur många, affärsmöjligheter har jag?"


def test_collapses_repetitions(preprocessor):
    assert preprocessor.clean("Kan du kan du visa mina kontakter?") == \
        "Kan du visa mina kontakter?"


def test_cleans_full_example(preprocessor):
    raw = "Emh, hur många... öppna affärsmöjligheter, liksom, har jag?"
    cleaned = preprocessor.clean(raw)
    assert "emh" not in cleaned.lower()
    assert "liksom" not in cleaned.lower()
    assert "affärsmöjligheter" in cleaned


def test_empty_string(preprocessor):
    assert preprocessor.clean("") == ""


def test_clean_text_unchanged(preprocessor):
    text = "Hur många öppna affärsmöjligheter har jag?"
    assert preprocessor.clean(text) == text
