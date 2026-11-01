"""Rule-based checks for scoring LLM outputs as Pass / Partial / Fail.

Each case in data/cases.json has an AI output plus a set of rules. Every rule
maps to one check function below. The results of all checks are rolled up into
a single score:

    PASS     every rule passes
    FAIL     a critical rule fails, or fewer than half of the rules pass
    PARTIAL  anything in between (no critical failures, at least half pass)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable


class Score(str, Enum):
    PASS = "PASS"
    PARTIAL = "PARTIAL"
    FAIL = "FAIL"


@dataclass
class CheckResult:
    rule: str
    passed: bool
    detail: str = ""


@dataclass
class Evaluation:
    case_id: str
    score: Score
    results: list[CheckResult]

    def failures(self) -> list[CheckResult]:
        return [r for r in self.results if not r.passed]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BULLET_LINE = re.compile(r"^[-*\u2022]\s+\S")
NUMBERED_LINE = re.compile(r"^\d+[.)]\s+\S")


def word_count(text: str) -> int:
    """Count words as runs of non-whitespace characters."""
    return len(text.split())


def contains_phrase(text: str, phrase: str) -> bool:
    """Case-insensitive match on whole words, so 'Smith' won't match 'Smithfield'."""
    pattern = r"(?<!\w)" + re.escape(phrase) + r"(?!\w)"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.strip().splitlines() if line.strip()]


def _list_items(text: str) -> list[str]:
    return [l for l in _lines(text) if BULLET_LINE.match(l) or NUMBERED_LINE.match(l)]


# ---------------------------------------------------------------------------
# Checks: each takes (output, rule_value) and returns a CheckResult
# ---------------------------------------------------------------------------

def check_max_words(output: str, limit: int) -> CheckResult:
    n = word_count(output)
    return CheckResult("max_words", n <= limit, f"{n} words (limit {limit})")


def check_min_words(output: str, minimum: int) -> CheckResult:
    n = word_count(output)
    return CheckResult("min_words", n >= minimum, f"{n} words (minimum {minimum})")


def check_must_contain(output: str, phrases: list[str]) -> CheckResult:
    missing = [p for p in phrases if not contains_phrase(output, p)]
    detail = f"missing {missing}" if missing else "all required phrases present"
    return CheckResult("must_contain", not missing, detail)


def check_must_not_contain(output: str, phrases: list[str]) -> CheckResult:
    found = [p for p in phrases if contains_phrase(output, p)]
    detail = f"found banned {found}" if found else "no banned phrases"
    return CheckResult("must_not_contain", not found, detail)


def check_format(output: str, fmt: str) -> CheckResult:
    text = output.strip()
    lines = _lines(text)

    if fmt == "bullets":
        ok = bool(lines) and all(BULLET_LINE.match(l) for l in lines)
    elif fmt == "numbered":
        ok = bool(lines) and all(NUMBERED_LINE.match(l) for l in lines)
    elif fmt == "single_sentence":
        # Sentence enders followed by whitespace or end of text.
        # Known limit: abbreviations like "Dr." would count as an ender.
        enders = re.findall(r"[.!?](?=\s|$)", text)
        ok = len(enders) == 1 and text[-1] in ".!?"
    elif fmt == "json":
        try:
            ok = isinstance(json.loads(text), dict)
        except json.JSONDecodeError:
            ok = False
    else:
        raise ValueError(f"Unknown format: {fmt!r}")

    return CheckResult("format", ok, f"expected {fmt}")


def check_json_keys(output: str, keys: list[str]) -> CheckResult:
    try:
        data = json.loads(output.strip())
    except json.JSONDecodeError:
        return CheckResult("json_keys", False, "output is not valid JSON")
    if not isinstance(data, dict):
        return CheckResult("json_keys", False, "JSON is not an object")
    missing = [k for k in keys if k not in data]
    detail = f"missing keys {missing}" if missing else "all keys present"
    return CheckResult("json_keys", not missing, detail)


def check_list_items(output: str, expected: int) -> CheckResult:
    n = len(_list_items(output))
    return CheckResult("list_items", n == expected, f"{n} items (expected {expected})")


DATE_PATTERN = re.compile(
    r"\b(January|February|March|April|May|June|July|August|"
    r"September|October|November|December) (\d{1,2}), (\d{4})\b"
)


def find_dates(text: str) -> list[datetime]:
    """Find every date written like 'March 3, 2026', in the order it appears."""
    dates = []
    for match in DATE_PATTERN.finditer(text):
        month, day, year = match.groups()
        dates.append(datetime.strptime(f"{month} {day} {year}", "%B %d %Y"))
    return dates


def check_dates_in_order(output: str, required: bool) -> CheckResult:
    """A chronology must list dates from oldest to newest."""
    dates = find_dates(output)
    if len(dates) < 2:
        return CheckResult("dates_in_order", False, f"found {len(dates)} date(s), need at least 2")
    for earlier, later in zip(dates, dates[1:]):
        if later < earlier:
            return CheckResult(
                "dates_in_order", False,
                f"{later:%B} {later.day}, {later.year} appears after "
                f"{earlier:%B} {earlier.day}, {earlier.year}",
            )
    return CheckResult("dates_in_order", True, f"{len(dates)} dates in order")


CHECKS: dict[str, Callable[[str, Any], CheckResult]] = {
    "dates_in_order": check_dates_in_order,
    "max_words": check_max_words,
    "min_words": check_min_words,
    "must_contain": check_must_contain,
    "must_not_contain": check_must_not_contain,
    "format": check_format,
    "json_keys": check_json_keys,
    "list_items": check_list_items,
}


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score_results(results: list[CheckResult], critical: list[str]) -> Score:
    failed = [r for r in results if not r.passed]
    if not failed:
        return Score.PASS
    if any(r.rule in critical for r in failed):
        return Score.FAIL
    pass_ratio = (len(results) - len(failed)) / len(results)
    return Score.PARTIAL if pass_ratio >= 0.5 else Score.FAIL


def evaluate_case(case: dict) -> Evaluation:
    output = case["output"]
    results = []
    for rule, value in case["rules"].items():
        if rule not in CHECKS:
            raise ValueError(f"{case['id']}: unknown rule {rule!r}")
        results.append(CHECKS[rule](output, value))
    score = score_results(results, case.get("critical", []))
    return Evaluation(case["id"], score, results)


def quality_rate(evaluations: list[Evaluation]) -> float:
    """PASS counts 1, PARTIAL counts 0.5, FAIL counts 0."""
    if not evaluations:
        return 0.0
    points = {Score.PASS: 1.0, Score.PARTIAL: 0.5, Score.FAIL: 0.0}
    return sum(points[e.score] for e in evaluations) / len(evaluations)


def load_cases(path: str | Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)
