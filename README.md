# llm-output-eval

![tests](https://github.com/johnathan-clore/llm-output-eval/actions/workflows/tests.yml/badge.svg)

An automated test suite that scores AI (LLM) outputs against rules, rates each one **Pass / Partial / Fail**, and fails the build if overall quality regresses. It runs on every push with GitHub Actions.

The test cases are modeled on legal work: summarizing court orders, building medical chronologies, pulling filing deadlines, drafting client emails, redacting personal data, and answering only from a source document.

## What it tests

`data/cases.json` holds 19 cases. Each one has:

- **input**: the prompt given to the AI
- **output**: a real AI answer
- **rules**: what a correct answer must and must not do
- **critical**: which rules are deal-breakers
- **expected_score**: my own human rating, used to check the grader

| Rule | What it checks |
| --- | --- |
| `max_words` / `min_words` | Length limits |
| `must_contain` | Required facts are present (dates, names, amounts) |
| `must_not_contain` | Banned content is absent (made-up facts, promises to clients, an SSN) |
| `format` | Output shape: `bullets`, `numbered`, `single_sentence`, or `json` |
| `json_keys` | Required keys exist in a JSON answer |
| `list_items` | A list has the exact number of items asked for |
| `dates_in_order` | A medical chronology lists dates oldest to newest |

The set deliberately includes bad outputs: a dropped date, a hallucinated legal deadline, an email that promises the client a result, a medical chronology with visits out of order, and an answer that isn't valid JSON. A suite where everything passes proves nothing.

## How the rating scale works

| Score | Meaning |
| --- | --- |
| **Pass** | Every rule passes |
| **Partial** | No critical rule fails, and at least half of the rules pass |
| **Fail** | A critical rule fails, or fewer than half of the rules pass |

The rating works like a quality inspection scale: a cosmetic issue (wrong format, a few words over) is Partial; anything that would mislead a client or a court (a missing date, an invented fact, a leaked SSN) is a Fail no matter what else is right.

## How the tests are organized

1. **Grader accuracy** (`test_grader_matches_human_label`): the automated score must agree with my human label on every case. This proves the checks themselves work.
2. **Output quality** (`test_output_meets_all_rules`): one test per case. Known-bad outputs are marked `xfail(strict=True)`, so they show as expected failures, and the suite alerts if one unexpectedly starts passing.
3. **Regression guard** (`test_regression_quality_rate_above_threshold`): Pass counts 1, Partial 0.5, Fail 0. The suite fails if the quality rate drops below 65%. Today it is 66%, so turning a single passing output into a failing one breaks the build.
4. **Unit tests** (`tests/test_checks.py`): each check function and the scoring logic tested on its own, including edge cases.

## How to run it

```bash
pip install -r requirements.txt
pytest -v                # run the full suite
python -m evals.report   # print a scorecard of every case
```

Sample scorecard:

```
CASE                      SCORE     FAILED RULES
summary-date-02           FAIL      must_contain (missing ['March 3, 2026'])
deadline-extract-02       PARTIAL   format (expected bullets)
...
PASS 11  PARTIAL 3  FAIL 5  quality rate 66%
```

## Project layout

```
data/cases.json              test cases and human labels
evals/checks.py              rule checks and scoring
evals/report.py              scorecard printer
tests/test_outputs.py        per-case, grader and regression tests
tests/test_checks.py         unit tests for the checks
.github/workflows/tests.yml  CI: runs pytest on every push
```

## What I'd add next

- Call a live model API so the suite tests fresh outputs instead of saved ones
- LLM-as-judge scoring for qualities rules can't catch, like tone or faithfulness
- Track the quality rate over time and chart it per commit
- Semantic matching, so "3/3/2026" counts as "March 3, 2026"

## How it was built

I built this with AI-assisted development, using AI as a tutor and pair programmer. I reviewed, tested, and can explain all of the code.
