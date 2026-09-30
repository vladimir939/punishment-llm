"""Convert Google Forms exports into data/humans.csv (long format).

    python survey/import_forms.py --v1 responses_v1.csv --v2 responses_v2.csv \
        --out data/humans.csv

Output columns, exactly what analysis/analyze.py expects:

    respondent_id, cost, damage, choice, order_version, attention_passed

`choice` is 1 for pay, 0 for nothing. `respondent_id` is an arbitrary sequential
integer. Nothing that could identify a respondent is carried through — the
Google Forms timestamp and any email column are dropped deliberately.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

# Condition id -> (cost, damage), matching spec.json condition_sets.core.
CONDITIONS = {
    "c1": (5, 15),
    "c2": (10, 20),
    "c3": (15, 15),
    "c4": (20, 10),
}

PAY = "заплатить"
NOTHING = "ничего"

IDENTIFYING = ("timestamp", "отметка времени", "email", "адрес электронной почты")


def classify(answer: str) -> int | None:
    """1 = pay, 0 = nothing, None = unrecognised."""
    text = (answer or "").strip().lower()
    if not text:
        return None
    if text.startswith(NOTHING) or NOTHING in text:
        return 0
    if text.startswith(PAY) or PAY in text:
        return 1
    return None


def find_condition(header: str) -> str | None:
    """Map a Google Forms column header back to a condition id by its numbers."""
    amounts = [int(n) for n in re.findall(r"\$(\d+)", header)]
    if len(amounts) < 2:
        return None
    cost, damage = amounts[0], amounts[1]
    for cid, (c, d) in CONDITIONS.items():
        if (c, d) == (cost, damage):
            return cid
    return None


def is_attention_column(header: str) -> bool:
    lowered = header.lower()
    return "вниматель" in lowered or "attention" in lowered


def load(path: Path, version: int) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise SystemExit(f"{path} has no responses")

    headers = list(rows[0].keys())
    condition_cols: dict[str, str] = {}
    attention_col: str | None = None
    for header in headers:
        if any(marker in header.lower() for marker in IDENTIFYING):
            continue
        if is_attention_column(header):
            attention_col = header
            continue
        cid = find_condition(header)
        if cid:
            condition_cols[cid] = header

    missing = set(CONDITIONS) - set(condition_cols)
    if missing:
        raise SystemExit(
            f"{path}: could not match column(s) for condition(s) {sorted(missing)}.\n"
            f"Headers seen: {headers}\n"
            f"Each item's wording must contain the two dollar amounts, e.g. "
            f"'Заплатить $5, чтобы участник A потерял $15.'"
        )
    if attention_col is None:
        raise SystemExit(
            f"{path}: no attention-check column found. Its wording must contain "
            f"'вниматель'."
        )

    out = []
    for row in rows:
        answers = {cid: classify(row[col]) for cid, col in condition_cols.items()}
        out.append(
            {
                "answers": answers,
                "attention_passed": classify(row[attention_col]) == 0,
                "order_version": version,
            }
        )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v1", required=True, help="ascending-order export")
    parser.add_argument("--v2", required=True, help="descending-order export")
    parser.add_argument("--out", default="data/humans.csv")
    parser.add_argument(
        "--start-id",
        type=int,
        default=1,
        help="first respondent_id; raise it to append a new wave without collision",
    )
    args = parser.parse_args(argv)

    respondents = load(Path(args.v1), 1) + load(Path(args.v2), 2)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    skipped_incomplete = 0
    failed_attention = 0
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "respondent_id",
                "cost",
                "damage",
                "choice",
                "order_version",
                "attention_passed",
            ]
        )
        rid = args.start_id
        for person in respondents:
            if any(v is None for v in person["answers"].values()):
                skipped_incomplete += 1
                continue
            if not person["attention_passed"]:
                failed_attention += 1
            for cid in ("c1", "c2", "c3", "c4"):
                cost, damage = CONDITIONS[cid]
                writer.writerow(
                    [
                        rid,
                        cost,
                        damage,
                        person["answers"][cid],
                        person["order_version"],
                        "true" if person["attention_passed"] else "false",
                    ]
                )
                written += 1
            rid += 1

    total = rid - args.start_id
    print(f"wrote {written} rows for {total} respondent(s) -> {out_path}")
    print(f"  attention-check failures retained for reporting: {failed_attention}")
    if skipped_incomplete:
        print(f"  skipped {skipped_incomplete} incomplete response(s)")
    print(
        "\nReport the attention-check exclusion count in the paper. "
        "analyze.py excludes them and prints the number."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
