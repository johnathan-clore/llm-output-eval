"""Evaluation tests over every case in data/cases.json.

Three layers:
1. Grader accuracy: the automated score must match the human label for each case.
   This proves the checks themselves are correct.
2. Output quality: one test per case that passes only if the AI output meets
   every rule. Known-bad outputs are marked xfail(strict=True), so they show up
   as expected failures, and the suite alerts you if one unexpectedly starts passing.
3. Regression guard: the overall quality rate must stay at or above a threshold.
"""

from pathlib import Path

import pytest

from evals.checks import Score, evaluate_case, load_cases, quality_rate

CASES = load_cases(Path(__file__).resolve().parent.parent / "data" / "cases.json")

# Raise this as the model or prompts improve; a drop below it fails CI.
QUALITY_THRESHOLD = 0.65


def _failure_summary(evaluation) -> str:
    return "; ".join(f"{r.rule}: {r.detail}" for r in evaluation.failures())


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_grader_matches_human_label(case):
    evaluation = evaluate_case(case)
    assert evaluation.score.value == case["expected_score"], (
        f"grader said {evaluation.score.value}, human label is "
        f"{case['expected_score']} ({_failure_summary(evaluation) or 'no failures'})"
    )


def _quality_params():
    for case in CASES:
        marks = []
        if case["expected_score"] != "PASS":
            reason = f"known {case['expected_score']}: {case.get('note', '')}"
            marks.append(pytest.mark.xfail(strict=True, reason=reason))
        yield pytest.param(case, id=case["id"], marks=marks)


@pytest.mark.parametrize("case", list(_quality_params()))
def test_output_meets_all_rules(case):
    evaluation = evaluate_case(case)
    assert evaluation.score is Score.PASS, _failure_summary(evaluation)


def test_regression_quality_rate_above_threshold():
    evaluations = [evaluate_case(c) for c in CASES]
    rate = quality_rate(evaluations)
    assert rate >= QUALITY_THRESHOLD, (
        f"quality rate {rate:.0%} fell below threshold {QUALITY_THRESHOLD:.0%}"
    )


def test_every_case_is_well_formed():
    ids = [c["id"] for c in CASES]
    assert len(ids) == len(set(ids)), "duplicate case ids"
    for case in CASES:
        assert {"id", "input", "output", "rules", "expected_score"} <= case.keys(), case.get("id")
        assert case["expected_score"] in {s.value for s in Score}, case["id"]
