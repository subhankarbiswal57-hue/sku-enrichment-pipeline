"""
Stage — Evaluation.

Scores pipeline output against sample_data/eval_set.csv, which we
hand-verified ourselves against the real manufacturer pages (we do not
have Unilog's actual 200-item ground truth — see project plan §0).

Reports simple, honest counts rather than a formal precision/recall
calculation, per the audit's guidance to keep evaluation proportional to
a hackathon MVP: category accuracy, attribute accuracy, and unsupported-
claim count (values we produced that the ground truth says are wrong or
that we produced when we should have said UNKNOWN).
"""

import csv
from collections import defaultdict

from enrich import enrich
from ingest import load_and_clean


def load_eval_set(path: str) -> dict:
    expected = defaultdict(dict)
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            expected[row["mfg_part_num"]][row["attribute_label"]] = {
                "value": row["expected_value"] or None,
                "uom": row["expected_uom"] or None,
                "notes": row["notes"],
            }
    return expected


def run_eval(input_path: str, eval_path: str):
    raw_rows = {r.mfg_part_num: r for r in load_and_clean(input_path)}
    expected = load_eval_set(eval_path)

    total = 0
    correct = 0
    unsupported_claims = 0
    misses = []

    for part_num, expected_attrs in expected.items():
        if part_num not in raw_rows:
            continue
        enriched = enrich(raw_rows[part_num])
        actual_by_label = {a.label: a for a in enriched.attributes}

        for label, exp in expected_attrs.items():
            total += 1
            actual = actual_by_label.get(label)
            actual_value = actual.value if actual and actual.state == "FOUND" else None

            if exp["value"] is None and actual_value is None:
                correct += 1  # both correctly say UNKNOWN
            elif exp["value"] == actual_value:
                correct += 1
            elif exp["value"] is None and actual_value is not None:
                unsupported_claims += 1
                misses.append((part_num, label, "we said a value, ground truth says UNKNOWN", actual_value, exp["value"]))
            else:
                misses.append((part_num, label, "value mismatch or missed", actual_value, exp["value"]))

    print(f"Attribute accuracy: {correct}/{total} ({100*correct/total:.0f}%)")
    print(f"Unsupported claims (we guessed, ground truth says UNKNOWN): {unsupported_claims}")
    print()
    if misses:
        print("Misses / gaps:")
        for part_num, label, reason, actual, expected_val in misses:
            print(f"  {part_num} | {label}: got={actual!r} expected={expected_val!r} ({reason})")


if __name__ == "__main__":
    run_eval("sample_data/input_slice.csv", "sample_data/eval_set.csv")
