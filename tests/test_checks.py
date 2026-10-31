"""Unit tests for the individual check functions and the scoring logic."""

import pytest

from evals.checks import (
    CheckResult,
    Score,
    check_format,
    check_json_keys,
    check_list_items,
    check_max_words,
    check_must_contain,
    check_must_not_contain,
    contains_phrase,
    score_results,
    word_count,
)


def test_word_count():
    assert word_count("one two  three\nfour") == 4
    assert word_count("") == 0


def test_max_words_boundary():
    assert check_max_words("a b c", 3).passed
    assert not check_max_words("a b c d", 3).passed


def test_contains_phrase_is_case_insensitive_and_whole_word():
    assert contains_phrase("The GUARANTEE is void", "guarantee")
    assert not contains_phrase("Smithfield Foods", "Smith")
    assert contains_phrase("demand of $45,000 today", "$45,000")


def test_must_contain_reports_missing():
    result = check_must_contain("Filed on March 3", ["March 3", "2026"])
    assert not result.passed
    assert "2026" in result.detail


def test_must_not_contain():
    assert check_must_not_contain("all clear", ["guarantee"]).passed
    assert not check_must_not_contain("we guarantee it", ["guarantee"]).passed


@pytest.mark.parametrize(
    "text, fmt, expected",
    [
        ("- a\n- b", "bullets", True),
        ("- a\nb", "bullets", False),
        ("1. a\n2) b", "numbered", True),
        ("One sentence here.", "single_sentence", True),
        ("Two. Sentences.", "single_sentence", False),
        ('{"a": 1}', "json", True),
        ("[1, 2]", "json", False),
        ("not json", "json", False),
    ],
)
def test_format(text, fmt, expected):
    assert check_format(text, fmt).passed is expected


def test_unknown_format_raises():
    with pytest.raises(ValueError):
        check_format("x", "yaml")


def test_json_keys():
    assert check_json_keys('{"plaintiff": "A", "defendant": "B"}', ["plaintiff", "defendant"]).passed
    assert not check_json_keys('{"plaintiff": "A"}', ["plaintiff", "defendant"]).passed
    assert not check_json_keys("nope", ["plaintiff"]).passed


def test_list_items():
    assert check_list_items("1. a\n2. b\n3. c", 3).passed
    assert not check_list_items("- a\n- b", 3).passed


def _r(rule, passed):
    return CheckResult(rule, passed)


def test_score_all_pass():
    assert score_results([_r("a", True), _r("b", True)], []) is Score.PASS


def test_score_critical_failure_is_fail():
    assert score_results([_r("a", True), _r("b", False)], ["b"]) is Score.FAIL


def test_score_noncritical_failure_is_partial():
    assert score_results([_r("a", True), _r("b", False)], []) is Score.PARTIAL


def test_score_mostly_failing_is_fail():
    results = [_r("a", True), _r("b", False), _r("c", False)]
    assert score_results(results, []) is Score.FAIL
