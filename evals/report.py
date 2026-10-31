"""Print a readable scorecard: python -m evals.report"""

from pathlib import Path

from evals.checks import evaluate_case, load_cases, quality_rate

CASES_PATH = Path(__file__).resolve().parent.parent / "data" / "cases.json"


def main() -> None:
    cases = load_cases(CASES_PATH)
    evaluations = [evaluate_case(c) for c in cases]

    print(f"{'CASE':<26}{'SCORE':<10}FAILED RULES")
    print("-" * 70)
    for ev in evaluations:
        failed = "; ".join(f"{r.rule} ({r.detail})" for r in ev.failures()) or "-"
        print(f"{ev.case_id:<26}{ev.score.value:<10}{failed}")

    counts = {s: sum(e.score.value == s for e in evaluations) for s in ("PASS", "PARTIAL", "FAIL")}
    print("-" * 70)
    print(f"PASS {counts['PASS']}  PARTIAL {counts['PARTIAL']}  FAIL {counts['FAIL']}  "
          f"quality rate {quality_rate(evaluations):.0%}")


if __name__ == "__main__":
    main()
