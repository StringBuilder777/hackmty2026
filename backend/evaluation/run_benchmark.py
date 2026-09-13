"""Run five held-out, reproducible estates and write reviewer-readable metrics."""
from __future__ import annotations

import argparse
import csv
import tempfile
from pathlib import Path

from app.services.forensic import run_forensic_audit
from evaluation.benchmark import BENCHMARK_VERSION, HELD_OUT_SEEDS, create_held_out_estate, expected_findings


def finding_key(finding: object) -> tuple[str, tuple[str, ...]]:
    return (finding.scheme_type, tuple(sorted(finding.entities)))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path('evaluation/results.csv'))
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix='forensic-benchmark-') as directory:
        for seed in HELD_OUT_SEEDS:
            estate = Path(directory) / f'estate-{seed}.db'
            create_held_out_estate(estate, seed)
            predicted = {finding_key(finding) for finding in run_forensic_audit(str(estate), seed).findings}
            labels = expected_findings(seed)
            true_positive = len(predicted & labels)
            false_positive = len(predicted - labels)
            false_negative = len(labels - predicted)
            precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 1.0
            recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 1.0
            rows.append({'benchmark_version': BENCHMARK_VERSION, 'partition': 'held_out', 'seed': seed, 'true_positive': true_positive, 'false_positive': false_positive,
                         'false_negative': false_negative, 'precision': f'{precision:.3f}', 'recall': f'{recall:.3f}'})
    with args.output.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=['benchmark_version', 'partition', 'seed', 'true_positive', 'false_positive', 'false_negative', 'precision', 'recall'])
        writer.writeheader()
        writer.writerows(rows)
    print(args.output.resolve())


if __name__ == '__main__':
    main()
