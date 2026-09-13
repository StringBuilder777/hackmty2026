"""Run held-out estates and write the exact official Results table shape."""
from __future__ import annotations

import argparse
import csv
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from app.services.forensic import run_forensic_audit
from evaluation.benchmark import (
    HELD_OUT_SEEDS,
    TUNING_SEEDS,
    DecoyLabel,
    SchemeLabel,
    create_held_out_estate,
    expected_decoys,
    expected_schemes,
)


FIELDNAMES = [
    'seed', 'schemes_planted', 'schemes_found', 'recall_pct',
    'decoys_planted', 'decoys_accused', 'false_accusation_rate_pct',
    'peso_claimed', 'peso_actual', 'peso_reconciles',
    'llm_calls', 'mxn_cost', 'wall_clock_s',
]


@dataclass(frozen=True)
class MatchResult:
    matches: tuple[tuple[object, SchemeLabel], ...]
    unmatched_predictions: tuple[object, ...]
    unmatched_labels: tuple[SchemeLabel, ...]


def finding_key(finding: object) -> tuple[str, tuple[str, ...]]:
    return finding.scheme_type, tuple(sorted(finding.entities))


def match_one_to_one(predictions: Sequence[object], labels: Sequence[SchemeLabel]) -> MatchResult:
    """Match exact scheme/entity keys once without collapsing duplicates into a set."""
    used_labels = [False] * len(labels)
    matches: list[tuple[object, SchemeLabel]] = []
    unmatched_predictions: list[object] = []
    for prediction in predictions:
        key = finding_key(prediction)
        match_index = next(
            (index for index, label in enumerate(labels) if not used_labels[index] and label.key == key),
            None,
        )
        if match_index is None:
            unmatched_predictions.append(prediction)
            continue
        used_labels[match_index] = True
        matches.append((prediction, labels[match_index]))
    unmatched_labels = tuple(label for index, label in enumerate(labels) if not used_labels[index])
    return MatchResult(tuple(matches), tuple(unmatched_predictions), unmatched_labels)


def _decoys_accused(predictions: Sequence[object], decoys: Sequence[DecoyLabel]) -> int:
    return sum(
        any(prediction.scheme_type == decoy.signal and decoy.entity in prediction.entities for prediction in predictions)
        for decoy in decoys
    )


def _within_two_percent(claimed: float, actual: float) -> bool:
    if actual == 0:
        return claimed == 0
    return abs(claimed - actual) / abs(actual) <= 0.02


def score_submission(submission: object, labels: Sequence[SchemeLabel], decoys: Sequence[DecoyLabel]) -> dict[str, object]:
    """Score one run while retaining duplicate and unmatched accusations."""
    predictions = tuple(submission.findings)
    matched = match_one_to_one(predictions, labels)
    schemes_found = len(matched.matches)
    decoys_accused = _decoys_accused(predictions, decoys)
    peso_claimed = round(sum(float(finding.peso_amount) for finding in predictions), 2)
    peso_actual = round(sum(label.peso_amount for label in labels), 2)
    every_amount_reconciles = all(
        _within_two_percent(float(prediction.peso_amount), label.peso_amount)
        for prediction, label in matched.matches
    )
    peso_reconciles = (
        not matched.unmatched_predictions
        and not matched.unmatched_labels
        and every_amount_reconciles
        and _within_two_percent(peso_claimed, peso_actual)
    )
    recall = schemes_found / len(labels) * 100 if labels else 100.0
    false_accusation_rate = decoys_accused / len(decoys) * 100 if decoys else 0.0
    return {
        'schemes_planted': len(labels),
        'schemes_found': schemes_found,
        'recall_pct': f'{recall:.1f}',
        'decoys_planted': len(decoys),
        'decoys_accused': decoys_accused,
        'false_accusation_rate_pct': f'{false_accusation_rate:.1f}',
        'peso_claimed': f'{peso_claimed:.2f}',
        'peso_actual': f'{peso_actual:.2f}',
        'peso_reconciles': 'YES' if peso_reconciles else 'NO',
        'llm_calls': submission.run_metadata.llm_calls,
        'mxn_cost': f'{submission.run_metadata.mxn_cost:.2f}',
        'wall_clock_s': f'{submission.run_metadata.wall_clock_seconds:.6f}',
    }


def _total_row(rows: Sequence[dict[str, object]]) -> dict[str, object]:
    schemes_planted = sum(int(row['schemes_planted']) for row in rows)
    schemes_found = sum(int(row['schemes_found']) for row in rows)
    decoys_planted = sum(int(row['decoys_planted']) for row in rows)
    decoys_accused = sum(int(row['decoys_accused']) for row in rows)
    peso_claimed = sum(float(row['peso_claimed']) for row in rows)
    peso_actual = sum(float(row['peso_actual']) for row in rows)
    return {
        'seed': 'TOTAL',
        'schemes_planted': schemes_planted,
        'schemes_found': schemes_found,
        'recall_pct': f'{(schemes_found / schemes_planted * 100 if schemes_planted else 100):.1f}',
        'decoys_planted': decoys_planted,
        'decoys_accused': decoys_accused,
        'false_accusation_rate_pct': f'{(decoys_accused / decoys_planted * 100 if decoys_planted else 0):.1f}',
        'peso_claimed': f'{peso_claimed:.2f}',
        'peso_actual': f'{peso_actual:.2f}',
        'peso_reconciles': 'YES' if all(row['peso_reconciles'] == 'YES' for row in rows) and _within_two_percent(peso_claimed, peso_actual) else 'NO',
        'llm_calls': sum(int(row['llm_calls']) for row in rows),
        'mxn_cost': f'{sum(float(row["mxn_cost"]) for row in rows):.2f}',
        'wall_clock_s': f'{sum(float(row["wall_clock_s"]) for row in rows):.6f}',
    }


def run_benchmark(output: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix='forensic-benchmark-') as directory:
        for seed in HELD_OUT_SEEDS:
            estate = Path(directory) / f'estate-{seed}.db'
            create_held_out_estate(estate, seed)
            submission = run_forensic_audit(str(estate), seed)
            row = {'seed': seed}
            row.update(score_submission(submission, expected_schemes(seed), expected_decoys(seed)))
            rows.append(row)
    rows.append(_total_row(rows))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, extrasaction='raise', lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path('evaluation/results.csv'))
    args = parser.parse_args()
    run_benchmark(args.output)
    print(f'tuning_seeds={",".join(map(str, TUNING_SEEDS))}')
    print(f'held_out_seeds={",".join(map(str, HELD_OUT_SEEDS))}')
    print(args.output.resolve())


if __name__ == '__main__':
    main()
